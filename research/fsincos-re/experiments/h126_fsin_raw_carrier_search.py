#!/usr/bin/env python3
"""Search fixed-grid carriers behind the remaining FSIN sine misses.

The h110/h122 schedules express every intermediate as a normalized
floating-point materialization.  P5 hardware instead has fixed-width
multiplier/add lanes.  A raw product can therefore retain a fixed slice of
the full product before normalization, and a Horner add can retain a grid
anchored to the coefficient rather than to the normalized sum.

This pass keeps every already-selected width and rounding rule, changing
only that carrier interpretation.  Every accepted change must improve both
deterministic halves of the complete direct or reduced dataset.
"""

from __future__ import annotations

import argparse
import dataclasses
from collections.abc import Iterable

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h122_fsin_reduced_sine as h122


PRODUCT_STYLES = ("normalized", "raw-high", "raw-low")
SUM_STYLES = ("normalized", "coefficient", "coefficient-high", "coefficient-low")


@dataclasses.dataclass(frozen=True)
class RawSchedule:
    base: h110.Schedule
    square_style: str = "normalized"
    product_styles: tuple[str, ...] = ("normalized",) * 5
    sum_styles: tuple[str, ...] = ("normalized",) * 5
    m_style: str = "normalized"
    correction_style: str = "normalized"

    def short(self) -> str:
        return (
            f"square={self.square_style}/"
            f"products={','.join(self.product_styles)}/"
            f"sums={','.join(self.sum_styles)}/"
            f"m={self.m_style}/correction={self.correction_style}"
        )


def grid_quantize(
    value: h58.FP,
    target_scale: int,
    mode: str,
) -> h58.FP:
    sign, significand, scale = value
    shift = target_scale - scale
    if not significand or shift <= 0:
        return value
    top = significand >> shift
    remainder = significand & ((1 << shift) - 1)
    if mode == "odd":
        if remainder:
            top |= 1
    else:
        increment = False
        if mode == "rn":
            half = 1 << (shift - 1)
            increment = remainder > half or (
                remainder == half and bool(top & 1)
            )
        elif mode == "away":
            increment = bool(remainder)
        elif mode != "chop":
            raise ValueError(mode)
        if increment:
            top += 1
    if not top:
        return h58.ZERO
    return sign, top, target_scale


def product_quantize(
    left: h58.FP,
    right: h58.FP,
    quant: h110.Quant,
    style: str,
) -> h58.FP:
    exact = h58.mul_exact(left, right)
    if quant.bits == 0 or style == "normalized":
        return h110.quantize(exact, quant)
    nominal_width = left[1].bit_length() + right[1].bit_length()
    if style == "raw-high":
        target_scale = exact[2] + nominal_width - quant.bits
    elif style == "raw-low":
        target_scale = exact[2] + nominal_width - 1 - quant.bits
    else:
        raise ValueError(style)
    return grid_quantize(exact, target_scale, quant.mode)


def sum_quantize(
    product: h58.FP,
    constant: h58.FP,
    quant: h110.Quant,
    style: str,
) -> h58.FP:
    exact = h58.add_exact(product, constant)
    if style == "normalized":
        return h110.quantize(exact, quant)
    if quant.bits == 0:
        return exact
    offset = {
        "coefficient": 0,
        "coefficient-high": 1,
        "coefficient-low": -1,
    }[style]
    target_scale = (
        constant[2] + constant[1].bit_length() - quant.bits + offset
    )
    return grid_quantize(exact, target_scale, quant.mode)


def hidden_value(
    point: h110.Observed,
    schedule: RawSchedule,
) -> h58.FP:
    raw = point.raw
    magnitude: h58.FP = (0, raw.sig, raw.exponent - 63)
    square = product_quantize(
        magnitude,
        magnitude,
        schedule.base.square,
        schedule.square_style,
    )
    value = h110.coefficient(h58.S6[0], schedule.base, 0)
    for index, row in enumerate(h58.S6[1:]):
        product = product_quantize(
            value,
            square,
            schedule.base.products[index],
            schedule.product_styles[index],
        )
        constant = h110.coefficient(row, schedule.base, index + 1)
        value = sum_quantize(
            product,
            constant,
            schedule.base.sums[index],
            schedule.sum_styles[index],
        )
    m = product_quantize(
        value,
        square,
        schedule.base.m,
        schedule.m_style,
    )
    if schedule.base.topology != "direct":
        raise ValueError("raw-carrier search requires direct topology")
    correction = product_quantize(
        m,
        magnitude,
        schedule.base.correction,
        schedule.correction_style,
    )
    result = h58.add_exact(magnitude, correction)
    return h58.neg(result) if raw.sign else result


def score(
    points: Iterable[h110.Observed],
    schedule: RawSchedule,
) -> h110.Score:
    result = h110.Score()
    for point in points:
        hidden = hidden_value(point, schedule)
        result.total += 1
        any_miss = False
        for index, rc in enumerate(h58.RCS):
            predicted = h58.x87_round(hidden, rc)
            expected = point.outputs[index]
            mismatch = predicted != expected
            result.mode_misses += mismatch
            any_miss |= mismatch
            if not mismatch:
                predicted_c1 = (
                    h110.compare_magnitude(expected, hidden) > 0
                )
                result.c1_misses += (
                    predicted_c1 != point.c1[index]
                )
        result.output_misses += any_miss
    return result


def replace_style(
    values: tuple[str, ...],
    index: int,
    replacement: str,
) -> tuple[str, ...]:
    changed = list(values)
    changed[index] = replacement
    return tuple(changed)


def neighbors(
    schedule: RawSchedule,
) -> Iterable[tuple[str, RawSchedule]]:
    for style in PRODUCT_STYLES:
        yield "square", dataclasses.replace(
            schedule, square_style=style
        )
    for index in range(5):
        for style in PRODUCT_STYLES:
            yield f"product-{index + 1}", dataclasses.replace(
                schedule,
                product_styles=replace_style(
                    schedule.product_styles, index, style
                ),
            )
        for style in SUM_STYLES:
            yield f"sum-{index + 1}", dataclasses.replace(
                schedule,
                sum_styles=replace_style(
                    schedule.sum_styles, index, style
                ),
            )
    for style in PRODUCT_STYLES:
        yield "m", dataclasses.replace(schedule, m_style=style)
        yield "correction", dataclasses.replace(
            schedule, correction_style=style
        )


def optimize(
    train: list[h110.Observed],
    heldout: list[h110.Observed],
    start: RawSchedule,
    passes: int,
) -> RawSchedule:
    current = start
    for pass_index in range(passes):
        print(f"\ncarrier pass {pass_index + 1}")
        changed = False
        grouped: dict[str, list[RawSchedule]] = {}
        for name, candidate in neighbors(current):
            grouped.setdefault(name, []).append(candidate)
        for name, candidates in grouped.items():
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
                f"  {name:12s} train {train_score.describe()}; "
                f"heldout {heldout_score.describe()}"
            )
            print(f"    {current.short()}")
        if not changed:
            break
    return current


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--path", choices=("direct", "reduced"), default="direct"
    )
    parser.add_argument("--passes", type=int, default=4)
    args = parser.parse_args()
    if args.path == "direct":
        points = h110.load_observed()
        base = h110.FSIN_SURVIVOR
        split = h110.is_train
    else:
        points = h122.load_points()
        base = h122.FSIN_REDUCED_SINE
        split = h122.is_train
    train = [point for point in points if split(point)]
    heldout = [point for point in points if not split(point)]
    start = RawSchedule(base)
    print(
        f"loaded {len(points)} {args.path} sine points: "
        f"{len(train)} train, {len(heldout)} held out"
    )
    print(f"normalized {score(points, start).describe()}")
    winner = optimize(train, heldout, start, args.passes)
    print("\nvalidated raw-carrier survivor")
    print(f"  {winner.short()}")
    print(f"  train    {score(train, winner).describe()}")
    print(f"  heldout  {score(heldout, winner).describe()}")
    print(f"  complete {score(points, winner).describe()}")


if __name__ == "__main__":
    main()
