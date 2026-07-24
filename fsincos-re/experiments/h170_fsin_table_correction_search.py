#!/usr/bin/env python3
"""Search conditional materialization of the Tang correction accumulator.

h169 maps 226 remaining table inputs to small mixed-direction errors around
the current RN67 correction.  This pass preserves h135 terminal states and
h143's narrow P5 C*p route, varying only the final Tang correction over the
64..72-bit/exact grid.  Selectors use at most two local accumulator,
product, operand-low-bit, path, quadrant, or table-cell predicates.

Rules must be componentwise no worse on dense/sweep train and heldout
partitions plus h135 and h140.  Survivors remain hypotheses pending a fresh
hardware-blind discriminator.
"""

from __future__ import annotations

import collections
import dataclasses
import itertools

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h131_fsin_table_c1_search as h131
import h135_fsin_table_terminal_discriminator as h135
import h136_tang_reconstruction_search as h136
import h139_p5_fmul_route_search as h139
import h140_p5_fmul_discriminator as h140
import h143_p5_fmul_c_parity as h143
import h146_fsin_cosine_boolean_search as h146
import h169_fsin_table_round33_tomography as h169


Metric = tuple[int, int, int]
CURRENT = h110.Quant(67, "rn")


@dataclasses.dataclass(frozen=True)
class Pipeline:
    point: h131.Observed
    lead: h58.FP
    correction: h58.FP


@dataclasses.dataclass
class Dataset:
    name: str
    points: list[h131.Observed]
    pipelines: list[Pipeline]
    features: list[dict[str, int]]
    metrics: list[Metric]
    baseline: Metric


def pipeline(point: h131.Observed) -> Pipeline:
    state, lead, cross, subtract, route = h169.lane_state(
        point
    )
    linear = h58.mul_exact(cross, state.residual)
    p_product = (
        h139.p5_fmul(
            cross, state.sine_correction, route
        )
        if route is not None
        else h58.mul_exact(cross, state.sine_correction)
    )
    if subtract:
        linear = h58.neg(linear)
        p_product = h58.neg(p_product)
    q_product = h58.mul_exact(
        lead, state.cosine_tail
    )
    correction = h58.add_exact(
        linear, h58.add_exact(q_product, p_product)
    )
    return Pipeline(point, lead, correction)


def hidden(
    prepared: Pipeline, quant: h110.Quant
) -> h58.FP:
    correction = h110.quantize(
        prepared.correction, quant
    )
    value = h58.add_exact(prepared.lead, correction)
    point = prepared.point
    quadrant = point.signed_n & 3
    if not (quadrant & 1) and point.point.raw.sign:
        value = h58.neg(value)
    return h58.neg(value) if quadrant & 2 else value


def point_metric(
    point: h131.Observed, value: h58.FP
) -> Metric:
    mode_misses = 0
    c1_misses = 0
    for index, rc in enumerate(h58.RCS):
        output = h58.x87_round(value, rc)
        mismatch = output != point.outputs[index]
        mode_misses += mismatch
        if not mismatch:
            c1 = (
                h110.compare_magnitude(output, value) > 0
            )
            c1_misses += c1 != point.c1[index]
    return mode_misses, int(bool(mode_misses)), c1_misses


def add(left: Metric, right: Metric) -> Metric:
    return tuple(
        a + b for a, b in zip(left, right)
    )  # type: ignore[return-value]


def make_dataset(
    name: str, points: list[h131.Observed]
) -> Dataset:
    pipelines = [pipeline(point) for point in points]
    values = [
        point_metric(point, hidden(prepared, CURRENT))
        for point, prepared in zip(points, pipelines)
    ]
    baseline: Metric = (0, 0, 0)
    for value in values:
        baseline = add(baseline, value)
    feature_rows = [h169.features(point) for point in points]
    return Dataset(
        name,
        points,
        pipelines,
        feature_rows,
        values,
        baseline,
    )


def datasets() -> list[Dataset]:
    dense = h131.load_dataset(
        "dense", h131.INPUTS / "dense_qn.txt"
    )
    sweep = h131.load_dataset(
        "sweep", h131.INPUTS / "sweep_inputs.txt"
    )
    result = []
    for name, points in (("dense", dense), ("sweep", sweep)):
        result.extend(
            (
                make_dataset(
                    f"{name}-train",
                    [point for point in points if h131.is_train(point)],
                ),
                make_dataset(
                    f"{name}-held",
                    [
                        point
                        for point in points
                        if not h131.is_train(point)
                    ],
                ),
            )
        )
    fresh135 = h135.load_capture(
        h135.DEFAULT_OUTPUT,
        h135.DEFAULT_METADATA,
        h135.ROOT
        / "capture-kit-captures"
        / "skylake-fsin-h135",
    )
    result.append(
        make_dataset(
            "h135",
            [
                point
                for points in fresh135.values()
                for point in points
            ],
        )
    )
    result.append(
        make_dataset(
            "h140",
            h140.load_capture(
                h140.DEFAULT_OUTPUT,
                h140.ROOT
                / "capture-kit-captures"
                / "skylake-fsin-h140",
            ),
        )
    )
    return result


def eligible_features(
    features: dict[str, int],
) -> tuple[tuple[str, int], ...]:
    prefixes = (
        "correction.",
        "p-product.",
        "q-product.",
        "nonlinear.",
    )
    names = (
        "cell",
        "wide",
        "reduced",
        "quadrant",
        "a.low3",
        "lead.low3",
        "cross.low3",
        "pstate.low3",
        "qstate.low3",
    )
    return tuple(
        (name, value)
        for name, value in features.items()
        if name in names or name.startswith(prefixes)
    )


def no_worse(value: Metric, baseline: Metric) -> bool:
    return all(
        candidate <= old
        for candidate, old in zip(value, baseline)
    )


def main() -> None:
    values = datasets()
    for dataset in values:
        print(
            f"h170 baseline {dataset.name:11s} "
            f"n={len(dataset.points):6d} {dataset.baseline}"
        )
    survivors = []
    tested = 0
    for quant in h110.quant_options(exact=True):
        if quant == CURRENT:
            continue
        tested += 1
        deltas: dict[
            tuple[tuple[str, int], ...],
            list[Metric],
        ] = collections.defaultdict(
            lambda: [(0, 0, 0) for _ in values]
        )
        for dataset_index, dataset in enumerate(values):
            for point, prepared, features, old_metric in zip(
                dataset.points,
                dataset.pipelines,
                dataset.features,
                dataset.metrics,
            ):
                new_metric = point_metric(
                    point, hidden(prepared, quant)
                )
                delta: Metric = tuple(
                    new - old
                    for new, old in zip(
                        new_metric, old_metric
                    )
                )  # type: ignore[assignment]
                if delta == (0, 0, 0):
                    continue
                terms = eligible_features(features)
                for count in (1, 2):
                    for rule in itertools.combinations(
                        terms, count
                    ):
                        deltas[rule][dataset_index] = add(
                            deltas[rule][dataset_index],
                            delta,
                        )
        for rule, rule_deltas in deltas.items():
            scores = tuple(
                add(dataset.baseline, delta)
                for dataset, delta in zip(
                    values, rule_deltas
                )
            )
            if not all(
                no_worse(score, dataset.baseline)
                for score, dataset in zip(scores, values)
            ):
                continue
            if not (
                scores[2] != values[2].baseline
                or scores[3] != values[3].baseline
            ):
                continue
            sweep = tuple(
                scores[2][index] + scores[3][index]
                for index in range(3)
            )
            dense = tuple(
                scores[0][index] + scores[1][index]
                for index in range(3)
            )
            fresh = tuple(
                sum(score[index] for score in scores[4:])
                for index in range(3)
            )
            survivors.append(
                (
                    sweep[0],
                    sweep[2],
                    sweep[1],
                    dense[0],
                    dense[2],
                    dense[1],
                    fresh[0],
                    fresh[2],
                    fresh[1],
                    quant.short(),
                    rule,
                    scores,
                )
            )
    survivors.sort()
    print(
        f"h170: {len(survivors)} rules survive from "
        f"{tested} correction materializations"
    )
    for entry in survivors[:40]:
        *_, quant, rule, scores = entry
        label = " & ".join(
            f"{name}={value}" for name, value in rule
        )
        print(f"  correction={quant} if {label}")
        for dataset, score in zip(values, scores):
            if score != dataset.baseline:
                print(
                    f"    {dataset.name:11s} "
                    f"{dataset.baseline}->{score}"
                )


if __name__ == "__main__":
    main()
