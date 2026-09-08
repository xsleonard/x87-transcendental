#!/usr/bin/env python3
"""Search shared wide-table terminal edges against both output lanes.

h181 rejects every individual Q Horner coordinate.  This pass tests the
remaining producer edges that feed both Tang lanes: square, P*square,
P*square*a, a+correction, Q*square, and 1+tail.  Candidate ranking uses
small deterministic samples; acceptance requires componentwise
non-regression for sine and cosine separately on complete dense/sweep
train/heldout partitions.
"""

from __future__ import annotations

import dataclasses

import h58_constraint_search as h58
import h60_round16_parity as h60
import h79_table_state_bias as h79
import h104_table_final_partial_search as h104
import h110_fsin_standalone as h110
import h131_fsin_table_c1_search as h131
import h134_fsin_table_per_edge_search as h134
import h135_fsin_table_terminal_discriminator as h135
import h170_fsin_table_correction_search as h170
import h173_fsin_table_fadd_topology as h173
import h177_table_sibling_triangulation as h177


Metric = h173.Metric
RN64 = h110.Quant(64, "rn")


@dataclasses.dataclass(frozen=True)
class Point:
    observed: h131.Observed
    cosine_outputs: tuple[tuple[int, int], ...]
    cosine_c1: tuple[bool, ...]


@dataclasses.dataclass(frozen=True)
class Candidate:
    edge: str
    quant: h110.Quant

    def short(self) -> str:
        return f"{self.edge}={self.quant.short()}"


CURRENT = Candidate("current", RN64)
EDGES = (
    "square",
    "p-square",
    "p-a",
    "sine-sum",
    "q-square",
    "one-plus-tail",
)


def dataset(name: str) -> list[Point]:
    input_path = h131.INPUTS / (
        "dense_qn.txt" if name == "dense" else "sweep_inputs.txt"
    )
    observed = h131.load_dataset(name, input_path)
    paired = {
        rc: h177.parse_pair(
            h177.PAIRED / f"{name}_fsincos_{rc}_status.txt"
        )
        for rc in h58.RCS
    }
    return [
        Point(
            point,
            tuple(
                paired[rc][point.index][1] for rc in h58.RCS
            ),
            tuple(
                paired[rc][point.index][2] for rc in h58.RCS
            ),
        )
        for point in observed
        if point.family == "wide"
    ]


def quantize(
    value: h58.FP,
    edge: str,
    current_edge: str,
    candidate: Candidate,
) -> h58.FP:
    quant = candidate.quant if candidate.edge == edge else (
        h110.EXACT if edge == "one-plus-tail" else RN64
    )
    if current_edge != edge:
        raise AssertionError((current_edge, edge))
    return h110.quantize(value, quant)


def values(
    point: Point, candidate: Candidate
) -> tuple[h58.FP, h58.FP]:
    observed = point.observed
    prepared = observed.point
    schedule = h135.path_candidate(observed)
    square = quantize(
        h58.mul_exact(prepared.a, prepared.a),
        "square",
        "square",
        candidate,
    )
    p = h134.horner(
        h58.S6,
        square,
        schedule.p_coefficients,
        schedule.p_products,
        schedule.p_sums,
    )
    q = h134.horner(
        h58.C6,
        square,
        schedule.q_coefficients,
        schedule.q_products,
        schedule.q_sums,
    )
    m = quantize(
        h58.mul_exact(p, square),
        "p-square",
        "p-square",
        candidate,
    )
    correction = quantize(
        h58.mul_exact(m, prepared.a),
        "p-a",
        "p-a",
        candidate,
    )
    sine_a = quantize(
        h58.add_exact(prepared.a, correction),
        "sine-sum",
        "sine-sum",
        candidate,
    )
    sine_a = h79.bias_toward_zero(sine_a, 5)
    tail = quantize(
        h58.mul_exact(q, square),
        "q-square",
        "q-square",
        candidate,
    )
    one_plus_tail = quantize(
        h58.add_exact(h58.ONE, tail),
        "one-plus-tail",
        "one-plus-tail",
        candidate,
    )
    sine = h104.lane_value(
        prepared.sin_t,
        prepared.cos_t,
        one_plus_tail,
        sine_a,
        False,
        h134.VARIANT,
    )
    cosine = h104.lane_value(
        prepared.cos_t,
        prepared.sin_t,
        one_plus_tail,
        sine_a,
        True,
        h134.VARIANT,
    )
    if prepared.raw.sign:
        sine = h58.neg(sine)
    return h60.rotate((sine, cosine), observed.signed_n)


def point_metric(
    outputs: tuple[tuple[int, int], ...],
    c1: tuple[bool, ...],
    hidden: h58.FP,
) -> Metric:
    mode = 0
    c1_misses = 0
    for index, rc in enumerate(h58.RCS):
        output = h58.x87_round(hidden, rc)
        mismatch = output != outputs[index]
        mode += mismatch
        if not mismatch:
            increment = (
                h110.compare_magnitude(output, hidden) > 0
            )
            c1_misses += increment != c1[index]
    return mode, int(bool(mode)), c1_misses


def score(
    points: list[Point], candidate: Candidate
) -> tuple[Metric, Metric]:
    sine: Metric = (0, 0, 0)
    cosine: Metric = (0, 0, 0)
    for point in points:
        sine_value, cosine_value = values(point, candidate)
        sine = h170.add(
            sine,
            point_metric(
                point.observed.outputs,
                point.observed.c1,
                sine_value,
            ),
        )
        cosine = h170.add(
            cosine,
            point_metric(
                point.cosine_outputs,
                point.cosine_c1,
                cosine_value,
            ),
        )
    return sine, cosine


def options(edge: str) -> tuple[Candidate, ...]:
    return tuple(
        Candidate(edge, quant)
        for quant in (
            h110.EXACT,
            *(
                h110.Quant(bits, mode)
                for bits in range(64, 73)
                for mode in ("rn", "chop", "away", "odd")
            ),
        )
    )


def no_worse(
    value: tuple[Metric, Metric],
    baseline: tuple[Metric, Metric],
) -> bool:
    return all(
        h173.no_worse(candidate, old)
        for candidate, old in zip(value, baseline)
    )


def sample(points: list[Point], count: int) -> list[Point]:
    def key(point: Point) -> int:
        observed = point.observed
        return (
            observed.point.raw.sig
            ^ (observed.point.raw.sig >> 19)
            ^ (observed.point.raw.sig >> 43)
            ^ observed.index
            ^ observed.signed_n
        )

    constrained = []
    controls = []
    for point in points:
        current = score([point], CURRENT)
        target = constrained if current != ((0, 0, 0), (0, 0, 0)) else controls
        target.append(point)
    constrained.sort(key=key)
    controls.sort(key=key)
    selected = constrained[: count // 2]
    selected.extend(controls[: count - len(selected)])
    if len(selected) < count:
        selected.extend(
            constrained[len(selected) : count]
        )
    return selected


def main() -> None:
    dense = dataset("dense")
    sweep = dataset("sweep")
    raw_partitions = []
    for name, points in (("dense", dense), ("sweep", sweep)):
        raw_partitions.extend(
            (
                (
                    f"{name}-train",
                    [p for p in points if h131.is_train(p.observed)],
                ),
                (
                    f"{name}-held",
                    [p for p in points if not h131.is_train(p.observed)],
                ),
            )
        )
    samples = [
        (name, sample(points, 250))
        for name, points in raw_partitions
    ]
    baseline = [
        score(points, CURRENT) for _, points in raw_partitions
    ]
    sample_baseline = [
        score(points, CURRENT) for _, points in samples
    ]
    print(f"h182 loaded dense={len(dense)} sweep={len(sweep)}")
    for (name, points), value in zip(raw_partitions, baseline):
        print(
            f"  baseline {name:11s} sine={value[0]} "
            f"cosine={value[1]} n={len(points)}"
        )

    survivors = []
    for edge in EDGES:
        ranked = []
        for candidate in options(edge):
            values = [
                score(points, candidate) for _, points in samples
            ]
            ranked.append(
                (
                    sum(
                        lane[0]
                        for value in values
                        for lane in value
                    ),
                    sum(
                        lane[1]
                        for value in values
                        for lane in value
                    ),
                    sum(
                        lane[2]
                        for value in values
                        for lane in value
                    ),
                    candidate.short(),
                    candidate,
                    values,
                )
            )
        ranked.sort()
        accepted = []
        for *_, candidate, sample_values in ranked[:12]:
            if not all(
                no_worse(value, old)
                for value, old in zip(
                    sample_values, sample_baseline
                )
            ):
                continue
            if not any(
                value != old
                for value, old in zip(
                    sample_values, sample_baseline
                )
            ):
                continue
            values = [
                score(points, candidate)
                for _, points in raw_partitions
            ]
            if (
                all(
                    no_worse(value, old)
                    for value, old in zip(values, baseline)
                )
                and any(
                    value != old
                    for value, old in zip(values, baseline)
                )
            ):
                accepted.append((candidate, values))
        print(f"h182 {edge}: {len(accepted)} survivors")
        for candidate, values in accepted[:8]:
            print(f"  {candidate.short()}")
            for (name, _), old, value in zip(
                raw_partitions, baseline, values
            ):
                if value != old:
                    print(
                        f"    {name:11s} {old}->{value}"
                    )
            survivors.append((candidate, values))
    print(f"h182 complete survivors: {len(survivors)}")


if __name__ == "__main__":
    main()
