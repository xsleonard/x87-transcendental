#!/usr/bin/env python3
"""Search non-uniform standalone-FSIN table Horner sequencing.

h133 rejects every uniform producer/tail width through 72 bits.  Intel's
direct FSIN polynomial path nevertheless uses non-uniform late Horner edges,
so this pass tests the analogous remaining table hypothesis.  It varies each
P and Q coefficient, product, and sum independently.  An exact product
followed by a rounded sum represents a fused multiply-add edge.

Every accepted change must improve at least one complete partition without
worsening dense-direct or full-sweep train/heldout partitions.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable

import h58_constraint_search as h58
import h79_table_state_bias as h79
import h104_table_final_partial_search as h104
import h110_fsin_standalone as h110
import h131_fsin_table_c1_search as h131


Quant = h110.Quant
RN64 = Quant(64, "rn")
RN67 = Quant(67, "rn")
EXACT = h110.EXACT
VARIANT = h104.Variant("delta-correction", 67, "rn")


@dataclasses.dataclass(frozen=True)
class Schedule:
    p_coefficients: tuple[Quant, ...] = (RN67,) * 6
    p_products: tuple[Quant, ...] = (RN64,) * 5
    p_sums: tuple[Quant, ...] = (RN64,) * 5
    q_coefficients: tuple[Quant, ...] = (RN67,) * 6
    q_products: tuple[Quant, ...] = (RN64,) * 5
    q_sums: tuple[Quant, ...] = (RN64,) * 5

    def short(self) -> str:
        def show(values: tuple[Quant, ...]) -> str:
            return ",".join(value.short() for value in values)

        return (
            f"Pc=[{show(self.p_coefficients)}] "
            f"Pp=[{show(self.p_products)}] "
            f"Ps=[{show(self.p_sums)}] "
            f"Qc=[{show(self.q_coefficients)}] "
            f"Qp=[{show(self.q_products)}] "
            f"Qs=[{show(self.q_sums)}]"
        )


CURRENT = Schedule()


def replace(
    values: tuple[Quant, ...], index: int, value: Quant
) -> tuple[Quant, ...]:
    changed = list(values)
    changed[index] = value
    return tuple(changed)


def coefficient(
    row: int, quant: Quant, delta: int = 0
) -> h58.FP:
    raw = h58.ROM[row]
    return h110.quantize(
        (raw[0], raw[1] + delta, raw[2]), quant
    )


def horner(
    rows: tuple[int, ...],
    square: h58.FP,
    coefficients: tuple[Quant, ...],
    products: tuple[Quant, ...],
    sums: tuple[Quant, ...],
    last_delta: int = 0,
) -> h58.FP:
    value = coefficient(rows[0], coefficients[0])
    for index, row in enumerate(rows[1:]):
        product = h110.quantize(
            h58.mul_exact(value, square), products[index]
        )
        constant = coefficient(
            row,
            coefficients[index + 1],
            last_delta if index + 2 == len(rows) else 0,
        )
        value = h110.quantize(
            h58.add_exact(product, constant), sums[index]
        )
    return value


def hidden_value(
    observed: h131.Observed, schedule: Schedule
) -> h58.FP:
    point = observed.point
    square = h58.fmul(point.a, point.a, 64, "rn")
    p_rows = h58.S6 if point.wide else h58.S4
    q_rows = h58.C6 if point.wide else h58.C4
    p = horner(
        p_rows,
        square,
        schedule.p_coefficients,
        schedule.p_products,
        schedule.p_sums,
        0 if point.wide else 7168,
    )
    q = horner(
        q_rows,
        square,
        schedule.q_coefficients,
        schedule.q_products,
        schedule.q_sums,
    )
    m = h58.fmul(p, square, 64, "rn")
    correction = h58.fmul(m, point.a, 64, "rn")
    sine_a = h58.fadd(point.a, correction, 64, "rn")
    sine_a = h79.bias_toward_zero(
        sine_a, 5 if point.wide else 4
    )
    tail = h58.fmul(q, square, 64, "rn")
    one_plus_tail = h58.add_exact(h58.ONE, tail)

    quadrant = observed.signed_n & 3
    if quadrant & 1:
        value = h104.lane_value(
            point.cos_t,
            point.sin_t,
            one_plus_tail,
            sine_a,
            True,
            VARIANT,
        )
    else:
        value = h104.lane_value(
            point.sin_t,
            point.cos_t,
            one_plus_tail,
            sine_a,
            False,
            VARIANT,
        )
        if point.raw.sign:
            value = h58.neg(value)
    return h58.neg(value) if quadrant & 2 else value


def score(
    points: list[h131.Observed], schedule: Schedule
) -> tuple[int, int, int]:
    mode_misses = 0
    input_misses = 0
    c1_misses = 0
    for point in points:
        hidden = hidden_value(point, schedule)
        missed_input = False
        for index, rc in enumerate(h58.RCS):
            predicted = h58.x87_round(hidden, rc)
            expected = point.outputs[index]
            mismatch = predicted != expected
            mode_misses += mismatch
            missed_input |= mismatch
            if not mismatch:
                predicted_c1 = (
                    h110.compare_magnitude(expected, hidden) > 0
                )
                c1_misses += predicted_c1 != point.c1[index]
        input_misses += missed_input
    return mode_misses, input_misses, c1_misses


def quant_options(exact: bool = False) -> tuple[Quant, ...]:
    values = tuple(
        Quant(bits, mode)
        for bits in range(64, 73)
        for mode in ("rn", "chop", "away", "odd")
    )
    return ((EXACT,) + values) if exact else values


def coordinates(
    schedule: Schedule, terms: int
) -> Iterable[tuple[str, Iterable[Schedule]]]:
    for prefix, field, count, exact in (
        ("Pc", "p_coefficients", terms, False),
        ("Pp", "p_products", terms - 1, True),
        ("Ps", "p_sums", terms - 1, False),
        ("Qc", "q_coefficients", terms, False),
        ("Qp", "q_products", terms - 1, True),
        ("Qs", "q_sums", terms - 1, False),
    ):
        for index in range(count):
            yield (
                f"{prefix}{index + 1}",
                (
                    dataclasses.replace(
                        schedule,
                        **{
                            field: replace(
                                getattr(schedule, field), index, value
                            )
                        },
                    )
                    for value in quant_options(exact)
                ),
            )


def search_family(
    family: str,
    dense: list[h131.Observed],
    sweep: list[h131.Observed],
) -> None:
    partitions = []
    for name, dataset in (("dense", dense), ("sweep", sweep)):
        selected = [point for point in dataset if point.family == family]
        partitions.extend(
            (
                (f"{name}-train", [p for p in selected if h131.is_train(p)]),
                (
                    f"{name}-held",
                    [p for p in selected if not h131.is_train(p)],
                ),
            )
        )
    samples = [
        (name, h131.sample(points, 1000))
        for name, points in partitions
    ]
    current = CURRENT
    terms = 6 if family == "wide" else 4
    print(f"\n{family}: {terms}-term P/Q chains")
    sample_baseline = [
        score(points, current) for _, points in samples
    ]
    complete_baseline = [
        score(points, current) for _, points in partitions
    ]

    for pass_index in range(3):
        changed = False
        print(f"  coordinate pass {pass_index + 1}")
        for name, candidates in coordinates(current, terms):
            ranked = []
            for candidate in dict.fromkeys(candidates):
                results = [
                    score(points, candidate) for _, points in samples
                ]
                ranked.append(
                    (
                        sum(result[0] for result in results),
                        sum(result[2] for result in results),
                        sum(result[1] for result in results),
                        candidate.short(),
                        candidate,
                        results,
                    )
                )
            ranked.sort()
            accepted = None
            for _, _, _, _, candidate, sample_results in ranked[:12]:
                if not all(
                    result <= base
                    for result, base in zip(
                        sample_results, sample_baseline
                    )
                ):
                    continue
                results = [
                    score(points, candidate)
                    for _, points in partitions
                ]
                if (
                    all(
                        result <= base
                        for result, base in zip(
                            results, complete_baseline
                        )
                    )
                    and any(
                        result < base
                        for result, base in zip(
                            results, complete_baseline
                        )
                    )
                ):
                    accepted = candidate, results
                    break
            if accepted is None:
                print(f"    {name:4s}: no transferable change")
                continue
            current, results = accepted
            changed = True
            complete_baseline = results
            sample_baseline = [
                score(points, current) for _, points in samples
            ]
            print(f"    {name:4s}: {current.short()}")
            for (partition, points), result in zip(partitions, results):
                print(
                    f"      {partition:11s} "
                    f"{h131.describe(result, len(points))}"
                )
        if not changed:
            break
    print(f"  survivor {current.short()}")
    for name, points in partitions:
        print(
            f"    {name:11s} "
            f"{h131.describe(score(points, current), len(points))}"
        )


def main() -> None:
    dense = h131.load_dataset("dense", h131.INPUTS / "dense_qn.txt")
    sweep = h131.load_dataset("sweep", h131.INPUTS / "sweep_inputs.txt")
    print(
        f"loaded {len(dense)} direct and {len(sweep)} sweep table inputs"
    )
    for family in ("narrow", "wide"):
        search_family(family, dense, sweep)


if __name__ == "__main__":
    main()
