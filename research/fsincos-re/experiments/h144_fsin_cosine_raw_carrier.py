#!/usr/bin/env python3
"""Search raw fixed-point carriers in FSIN's internal cosine producer.

h121 leaves 66 one-ulp mode misses in the odd-quadrant polynomial path after
searching normalized floating-point materializations.  P5 FADD/FMUL instead
move fixed-width carriers.  This pass keeps every selected h121 width and
rounding rule, changing only whether a product or sum is materialized on its
normalized grid or on the adjacent raw grid implied by its operands.

Every accepted coordinate must be no worse on both deterministic halves of
the complete 12,249-point odd-quadrant sweep.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h119_fcos_standalone as h119
import h121_fsin_internal_cosine as h121
import h126_fsin_raw_carrier_search as h126


@dataclasses.dataclass(frozen=True)
class Schedule:
    base: h119.Schedule
    square_style: str = "normalized"
    product_styles: tuple[str, ...] = ("normalized",) * 5
    sum_styles: tuple[str, ...] = ("normalized",) * 5
    tail_style: str = "normalized"
    final_style: str = "normalized"

    def short(self) -> str:
        return (
            f"square={self.square_style}/"
            f"products={','.join(self.product_styles)}/"
            f"sums={','.join(self.sum_styles)}/"
            f"tail={self.tail_style}/final={self.final_style}"
        )


CURRENT = Schedule(h121.FSIN_INTERNAL_COSINE)


def hidden_value(point: h121.Point, schedule: Schedule) -> h58.FP:
    observed = point.observed
    magnitude: h58.FP = (
        0,
        observed.raw.sig,
        observed.raw.exponent - 63,
    )
    square = h126.product_quantize(
        magnitude,
        magnitude,
        schedule.base.square,
        schedule.square_style,
    )
    value = h119.coefficient(h58.C6[0], schedule.base, 0)
    for index, row in enumerate(h58.C6[1:]):
        product = h126.product_quantize(
            value,
            square,
            schedule.base.products[index],
            schedule.product_styles[index],
        )
        value = h126.sum_quantize(
            product,
            h119.coefficient(row, schedule.base, index + 1),
            schedule.base.sums[index],
            schedule.sum_styles[index],
        )
    tail = h126.product_quantize(
        value,
        square,
        schedule.base.tail,
        schedule.tail_style,
    )
    result = h126.sum_quantize(
        tail,
        h58.ONE,
        schedule.base.final_sum,
        schedule.final_style,
    )
    return h58.neg(result) if point.negate else result


def score(
    points: Iterable[h121.Point], schedule: Schedule
) -> h110.Score:
    result = h110.Score()
    for point in points:
        hidden = hidden_value(point, schedule)
        result.total += 1
        any_miss = False
        for index, rc in enumerate(h58.RCS):
            expected = point.observed.outputs[index]
            predicted = h58.x87_round(hidden, rc)
            mismatch = predicted != expected
            result.mode_misses += mismatch
            any_miss |= mismatch
            if not mismatch:
                predicted_c1 = (
                    h110.compare_magnitude(expected, hidden) > 0
                )
                result.c1_misses += (
                    predicted_c1 != point.observed.c1[index]
                )
        result.output_misses += any_miss
    return result


def replace(
    values: tuple[str, ...], index: int, value: str
) -> tuple[str, ...]:
    changed = list(values)
    changed[index] = value
    return tuple(changed)


def coordinates(
    schedule: Schedule,
) -> Iterable[tuple[str, Iterable[Schedule]]]:
    yield (
        "square",
        (
            dataclasses.replace(schedule, square_style=style)
            for style in h126.PRODUCT_STYLES
        ),
    )
    for index in range(5):
        yield (
            f"product-{index + 1}",
            (
                dataclasses.replace(
                    schedule,
                    product_styles=replace(
                        schedule.product_styles, index, style
                    ),
                )
                for style in h126.PRODUCT_STYLES
            ),
        )
        yield (
            f"sum-{index + 1}",
            (
                dataclasses.replace(
                    schedule,
                    sum_styles=replace(
                        schedule.sum_styles, index, style
                    ),
                )
                for style in h126.SUM_STYLES
            ),
        )
    yield (
        "tail",
        (
            dataclasses.replace(schedule, tail_style=style)
            for style in h126.PRODUCT_STYLES
        ),
    )
    yield (
        "final",
        (
            dataclasses.replace(schedule, final_style=style)
            for style in h126.SUM_STYLES
        ),
    )


def optimize(
    train: list[h121.Point],
    heldout: list[h121.Point],
    start: Schedule,
) -> Schedule:
    current = start
    for pass_index in range(4):
        print(f"carrier pass {pass_index + 1}")
        changed = False
        for name, candidates in coordinates(current):
            train_base = score(train, current)
            heldout_base = score(heldout, current)
            ranked = sorted(
                (
                    score(train, candidate).rank(),
                    candidate.short(),
                    candidate,
                )
                for candidate in set(candidates)
            )
            accepted = None
            for _, _, candidate in ranked:
                train_score = score(train, candidate)
                heldout_score = score(heldout, candidate)
                if (
                    h110.no_worse(train_score, train_base)
                    and h110.no_worse(heldout_score, heldout_base)
                    and (
                        train_score.rank() < train_base.rank()
                        or heldout_score.rank() < heldout_base.rank()
                    )
                ):
                    accepted = candidate, train_score, heldout_score
                    break
            if accepted is None:
                continue
            current, train_score, heldout_score = accepted
            changed = True
            print(
                f"  {name:10s} train {train_score.describe()}; "
                f"heldout {heldout_score.describe()}"
            )
            print(f"    {current.short()}")
        if not changed:
            break
    return current


def main() -> None:
    points = h121.load_points()
    train = [point for point in points if h121.is_train(point)]
    heldout = [point for point in points if not h121.is_train(point)]
    print(
        f"h144: {len(points)} internal-cosine points; "
        f"{len(train)} train, {len(heldout)} held out"
    )
    print(f"baseline {score(points, CURRENT).describe()}")
    winner = optimize(train, heldout, CURRENT)
    print("validated raw-carrier survivor")
    print(f"  {winner.short()}")
    print(f"  train    {score(train, winner).describe()}")
    print(f"  heldout  {score(heldout, winner).describe()}")
    print(f"  complete {score(points, winner).describe()}")


if __name__ == "__main__":
    main()
