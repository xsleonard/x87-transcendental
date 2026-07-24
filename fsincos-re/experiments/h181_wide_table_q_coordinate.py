#!/usr/bin/env python3
"""Recover the wide table cosine-tail Horner schedule.

h180 localizes roughly 104k dense cosine mode misses to the wide family,
while all final reconstruction graphs remain tied.  This pass keeps each
direct/reduced path's validated P schedule and searches only the six-term Q
coefficient, product, and sum coordinates.  Paired FSINCOS cosine results
from h177 provide dense and sweep train/heldout gates.
"""

from __future__ import annotations

import dataclasses

import h58_constraint_search as h58
import h79_table_state_bias as h79
import h104_table_final_partial_search as h104
import h110_fsin_standalone as h110
import h131_fsin_table_c1_search as h131
import h134_fsin_table_per_edge_search as h134
import h135_fsin_table_terminal_discriminator as h135
import h170_fsin_table_correction_search as h170
import h173_fsin_table_fadd_topology as h173
import h177_table_sibling_triangulation as h177


Quant = h110.Quant
Metric = h173.Metric


@dataclasses.dataclass(frozen=True)
class Overrides:
    coefficients: tuple[Quant | None, ...] = (None,) * 6
    products: tuple[Quant | None, ...] = (None,) * 5
    sums: tuple[Quant | None, ...] = (None,) * 5

    def short(self) -> str:
        rows = []
        for prefix, values in (
            ("Qc", self.coefficients),
            ("Qp", self.products),
            ("Qs", self.sums),
        ):
            for index, value in enumerate(values):
                if value is not None:
                    rows.append(
                        f"{prefix}{index + 1}={value.short()}"
                    )
        return " ".join(rows) if rows else "current"


CURRENT = Overrides()


@dataclasses.dataclass(frozen=True)
class Prepared:
    point: h131.Observed
    base: h134.Schedule
    square: h58.FP
    sine_a: h58.FP


def replace(
    values: tuple[Quant | None, ...],
    index: int,
    value: Quant,
) -> tuple[Quant | None, ...]:
    result = list(values)
    result[index] = value
    return tuple(result)


def cosine_dataset(name: str) -> list[h131.Observed]:
    path = h131.INPUTS / (
        "dense_qn.txt" if name == "dense" else "sweep_inputs.txt"
    )
    points = h131.load_dataset(name, path)
    paired = {
        rc: h177.parse_pair(
            h177.PAIRED / f"{name}_fsincos_{rc}_status.txt"
        )
        for rc in h58.RCS
    }
    result = []
    for point in points:
        outputs = tuple(
            paired[rc][point.index][1] for rc in h58.RCS
        )
        c1 = tuple(
            paired[rc][point.index][2] for rc in h58.RCS
        )
        result.append(
            dataclasses.replace(
                point,
                signed_n=point.signed_n + 1,
                outputs=outputs,
                c1=c1,
            )
        )
    return result


def prepare(point: h131.Observed) -> Prepared:
    base = h135.path_candidate(point)
    square = h58.fmul(point.point.a, point.point.a, 64, "rn")
    p = h134.horner(
        h58.S6,
        square,
        base.p_coefficients,
        base.p_products,
        base.p_sums,
    )
    m = h58.fmul(p, square, 64, "rn")
    correction = h58.fmul(m, point.point.a, 64, "rn")
    sine_a = h58.fadd(point.point.a, correction, 64, "rn")
    sine_a = h79.bias_toward_zero(sine_a, 5)
    return Prepared(point, base, square, sine_a)


def schedule(
    prepared: Prepared, overrides: Overrides
) -> h134.Schedule:
    base = prepared.base
    return dataclasses.replace(
        base,
        q_coefficients=tuple(
            value if value is not None else old
            for value, old in zip(
                overrides.coefficients,
                base.q_coefficients,
            )
        ),
        q_products=tuple(
            value if value is not None else old
            for value, old in zip(
                overrides.products, base.q_products
            )
        ),
        q_sums=tuple(
            value if value is not None else old
            for value, old in zip(
                overrides.sums, base.q_sums
            )
        ),
    )


def hidden(prepared: Prepared, overrides: Overrides) -> h58.FP:
    point = prepared.point
    model = schedule(prepared, overrides)
    q = h134.horner(
        h58.C6,
        prepared.square,
        model.q_coefficients,
        model.q_products,
        model.q_sums,
    )
    tail = h58.fmul(q, prepared.square, 64, "rn")
    one_plus_tail = h58.add_exact(h58.ONE, tail)
    quadrant = point.signed_n & 3
    if quadrant & 1:
        value = h104.lane_value(
            point.point.cos_t,
            point.point.sin_t,
            one_plus_tail,
            prepared.sine_a,
            True,
            h134.VARIANT,
        )
    else:
        value = h104.lane_value(
            point.point.sin_t,
            point.point.cos_t,
            one_plus_tail,
            prepared.sine_a,
            False,
            h134.VARIANT,
        )
        if point.point.raw.sign:
            value = h58.neg(value)
    return h58.neg(value) if quadrant & 2 else value


def score(
    points: list[Prepared], overrides: Overrides
) -> Metric:
    result: Metric = (0, 0, 0)
    for prepared in points:
        point = prepared.point
        value = hidden(prepared, overrides)
        result = h170.add(
            result, h170.point_metric(point, value)
        )
    return result


def options(exact: bool) -> tuple[Quant, ...]:
    values = tuple(
        Quant(bits, mode)
        for bits in range(64, 73)
        for mode in ("rn", "chop", "away", "odd")
    )
    return ((h110.EXACT,) + values) if exact else values


def coordinates(overrides: Overrides):
    for name, field, count, exact in (
        ("Qc", "coefficients", 6, False),
        ("Qp", "products", 5, True),
        ("Qs", "sums", 5, False),
    ):
        for index in range(count):
            yield (
                f"{name}{index + 1}",
                tuple(
                    dataclasses.replace(
                        overrides,
                        **{
                            field: replace(
                                getattr(overrides, field),
                                index,
                                value,
                            )
                        },
                    )
                    for value in options(exact)
                ),
            )


def main() -> None:
    dense = [
        point
        for point in cosine_dataset("dense")
        if point.family == "wide"
    ]
    sweep = [
        point
        for point in cosine_dataset("sweep")
        if point.family == "wide"
    ]
    raw_partitions = []
    for name, points in (("dense", dense), ("sweep", sweep)):
        raw_partitions.extend(
            (
                (
                    f"{name}-train",
                    [p for p in points if h131.is_train(p)],
                ),
                (
                    f"{name}-held",
                    [p for p in points if not h131.is_train(p)],
                ),
            )
        )
    partitions = [
        (name, [prepare(point) for point in points])
        for name, points in raw_partitions
    ]
    samples = [
        (
            name,
            [
                prepare(point)
                for point in h131.sample(points, 250)
            ],
        )
        for name, points in raw_partitions
    ]
    current = CURRENT
    complete_baseline = [
        score(points, current) for _, points in partitions
    ]
    sample_baseline = [
        score(points, current) for _, points in samples
    ]
    print(f"h181 loaded dense={len(dense)} sweep={len(sweep)}")
    for (name, points), value in zip(
        partitions, complete_baseline
    ):
        print(
            f"  baseline {name:11s} "
            f"{h131.describe(value, len(points))}"
        )

    for pass_index in range(3):
        changed = False
        print(f"h181 coordinate pass {pass_index + 1}")
        for name, candidates in coordinates(current):
            ranked = []
            for candidate in dict.fromkeys(candidates):
                values = [
                    score(points, candidate)
                    for _, points in samples
                ]
                ranked.append(
                    (
                        sum(value[0] for value in values),
                        sum(value[1] for value in values),
                        sum(value[2] for value in values),
                        candidate.short(),
                        candidate,
                        values,
                    )
                )
            ranked.sort()
            accepted = None
            for *_, candidate, sample_values in ranked[:12]:
                if not all(
                    h173.no_worse(value, baseline)
                    for value, baseline in zip(
                        sample_values, sample_baseline
                    )
                ):
                    continue
                if not any(
                    value != baseline
                    for value, baseline in zip(
                        sample_values, sample_baseline
                    )
                ):
                    continue
                values = [
                    score(points, candidate)
                    for _, points in partitions
                ]
                if (
                    all(
                        h173.no_worse(value, baseline)
                        for value, baseline in zip(
                            values, complete_baseline
                        )
                    )
                    and any(
                        value != baseline
                        for value, baseline in zip(
                            values, complete_baseline
                        )
                    )
                ):
                    accepted = candidate, values
                    break
            if accepted is None:
                continue
            current, complete_baseline = accepted
            sample_baseline = [
                score(points, current)
                for _, points in samples
            ]
            changed = True
            print(f"  {name}: {current.short()}")
            for (partition, points), value in zip(
                partitions, complete_baseline
            ):
                print(
                    f"    {partition:11s} "
                    f"{h131.describe(value, len(points))}"
                )
        if not changed:
            break
    print(f"h181 survivor: {current.short()}")


if __name__ == "__main__":
    main()
