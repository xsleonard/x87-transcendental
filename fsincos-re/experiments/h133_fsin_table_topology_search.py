#!/usr/bin/env python3
"""Reconstruct standalone FSIN's table producer with value plus C1.

The standalone status capture shows that the shared FSINCOS table model is
close but does not reproduce FSIN's hidden table value.  h131 and h132 rule
out final-combine materialization and small state-bias replacements.  This
pass therefore varies the producer itself:

* square and coefficient materialization;
* separate P and Q Horner product/sum widths;
* P-to-S tail product, correction product, and final S sum;
* Q-to-(1+t) tail product.

Each coordinate spans 64..72 bits with RN, chop, away, and odd rounding;
Horner products may also remain exact.  A change is accepted only when it is
no worse on all complete dense-direct and full-sweep train/heldout
partitions for that table family.
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
EXACT = h110.EXACT
VARIANT = h104.Variant("delta-correction", 67, "rn")


@dataclasses.dataclass(frozen=True)
class Schedule:
    square: Quant = Quant(64, "rn")
    coefficient: Quant = Quant(67, "rn")
    p_product: Quant = Quant(64, "rn")
    p_sum: Quant = Quant(64, "rn")
    q_product: Quant = Quant(64, "rn")
    q_sum: Quant = Quant(64, "rn")
    m: Quant = Quant(64, "rn")
    correction: Quant = Quant(64, "rn")
    sine_sum: Quant = Quant(64, "rn")
    tail: Quant = Quant(64, "rn")

    def short(self) -> str:
        return (
            f"sq={self.square.short()} c={self.coefficient.short()} "
            f"P={self.p_product.short()}+{self.p_sum.short()} "
            f"Q={self.q_product.short()}+{self.q_sum.short()} "
            f"S={self.m.short()}*{self.correction.short()}"
            f"+{self.sine_sum.short()} t={self.tail.short()}"
        )


CURRENT = Schedule()


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
    coefficient_quant: Quant,
    product_quant: Quant,
    sum_quant: Quant,
    last_delta: int = 0,
) -> h58.FP:
    value = coefficient(rows[0], coefficient_quant)
    for index, row in enumerate(rows[1:], 1):
        product = h110.quantize(
            h58.mul_exact(value, square), product_quant
        )
        constant = coefficient(
            row,
            coefficient_quant,
            last_delta if index == len(rows) - 1 else 0,
        )
        value = h110.quantize(
            h58.add_exact(product, constant), sum_quant
        )
    return value


def hidden_value(
    observed: h131.Observed, schedule: Schedule
) -> h58.FP:
    original = observed.point
    square = h110.quantize(
        h58.mul_exact(original.a, original.a), schedule.square
    )
    p_rows = h58.S6 if original.wide else h58.S4
    q_rows = h58.C6 if original.wide else h58.C4
    p = horner(
        p_rows,
        square,
        schedule.coefficient,
        schedule.p_product,
        schedule.p_sum,
        0 if original.wide else 7168,
    )
    q = horner(
        q_rows,
        square,
        schedule.coefficient,
        schedule.q_product,
        schedule.q_sum,
    )
    m = h110.quantize(h58.mul_exact(p, square), schedule.m)
    correction = h110.quantize(
        h58.mul_exact(m, original.a), schedule.correction
    )
    sine_a = h110.quantize(
        h58.add_exact(original.a, correction), schedule.sine_sum
    )
    sine_a = h79.bias_toward_zero(
        sine_a, 5 if original.wide else 4
    )
    tail = h110.quantize(
        h58.mul_exact(q, square), schedule.tail
    )
    one_plus_tail = h58.add_exact(h58.ONE, tail)

    quadrant = observed.signed_n & 3
    if quadrant & 1:
        value = h104.lane_value(
            original.cos_t,
            original.sin_t,
            one_plus_tail,
            sine_a,
            True,
            VARIANT,
        )
    else:
        value = h104.lane_value(
            original.sin_t,
            original.cos_t,
            one_plus_tail,
            sine_a,
            False,
            VARIANT,
        )
        if original.raw.sign:
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


def coordinate_candidates(
    schedule: Schedule,
) -> tuple[tuple[str, Iterable[Schedule]], ...]:
    result = []
    for name, exact in (
        ("square", False),
        ("coefficient", False),
        ("p_product", True),
        ("p_sum", False),
        ("q_product", True),
        ("q_sum", False),
        ("m", True),
        ("correction", True),
        ("sine_sum", False),
        ("tail", True),
    ):
        result.append(
            (
                name,
                (
                    dataclasses.replace(schedule, **{name: value})
                    for value in quant_options(exact)
                ),
            )
        )
    return tuple(result)


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
        (name, h131.sample(points, 1500))
        for name, points in partitions
    ]
    current = CURRENT
    baseline = [score(points, current) for _, points in partitions]
    print(f"\n{family}:")
    print(f"  current {current.short()}")
    for (name, points), result in zip(partitions, baseline):
        print(
            f"    {name:11s} {h131.describe(result, len(points))}"
        )

    for pass_index in range(3):
        changed = False
        print(f"  coordinate pass {pass_index + 1}")
        for name, candidates in coordinate_candidates(current):
            sample_baseline = [
                score(points, current) for _, points in samples
            ]
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
            complete_baseline = [
                score(points, current) for _, points in partitions
            ]
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
                print(f"    {name:11s}: no transferable change")
                continue
            current, results = accepted
            changed = True
            print(f"    {name:11s}: {current.short()}")
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
