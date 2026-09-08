#!/usr/bin/env python3
"""Invert FSIN observations into internal-cosine state intervals.

RN/RD/RU outputs bracket the pre-architectural-rounding result, and RN cuts
that directed interval at its midpoint.  For odd-quadrant FSIN this yields
an interval for the positive internal cosine value.  Dividing ``H-1`` by
the known Round 30 square then yields the effective q-state interval needed
by the final multiply.

This is diagnostic tomography: it reports correction distributions and
which physical trace bits separate states that must move up or down.  It
does not assume the final multiply is exact.
"""

from __future__ import annotations

import collections
import fractions

import h58_constraint_search as h58
import h121_fsin_internal_cosine as h121
import h146_fsin_cosine_boolean_search as h146
import h147_fsin_cosine_boolean_discriminator as h147
import h148_fsin_cosine_boolean_crossvalidate as h148
import h150_fsin_cosine_boolean_round30 as h150
import h151_fsin_cosine_tail_discriminator as h151
import h153_fsin_cosine_p5_tail_round30 as h153


Fraction = fractions.Fraction


def fp_fraction(value: h58.FP) -> Fraction:
    sign, significand, scale = value
    result = Fraction(significand) * Fraction(2) ** scale
    return -result if sign else result


def output_fraction(value: tuple[int, int]) -> Fraction:
    se, significand = value
    if not significand:
        return Fraction(0)
    exponent = (se & 0x7FFF) - 16383
    result = Fraction(significand) * Fraction(2) ** (
        exponent - 63
    )
    return -result if se >> 15 else result


def hidden_interval(
    point: h121.Point,
) -> tuple[Fraction, Fraction]:
    rn, rd, ru = (
        output_fraction(value)
        for value in point.observed.outputs
    )
    low, high = sorted((rd, ru))
    if low != high:
        midpoint = (low + high) / 2
        if rn == low:
            high = midpoint
        elif rn == high:
            low = midpoint
        else:
            raise ValueError(
                f"RN result {rn} does not bisect {rd}, {ru}"
            )
    if point.negate:
        low, high = -high, -low
    return low, high


def baseline_hidden(
    point: h121.Point, state: h153.State
) -> Fraction:
    value = h153.hidden(point, state, None)
    result = fp_fraction(value)
    return -result if point.negate else result


def relation(
    value: Fraction, low: Fraction, high: Fraction
) -> str:
    if value < low:
        return "need-up"
    if value > high:
        return "need-down"
    return "inside"


def rounded_scaled(
    value: Fraction, power: int
) -> int:
    scaled = value * (1 << power)
    quotient, remainder = divmod(
        scaled.numerator, scaled.denominator
    )
    if 2 * remainder > scaled.denominator or (
        2 * remainder == scaled.denominator
        and quotient & 1
    ):
        quotient += 1
    return quotient


def report(
    name: str, points: list[h121.Point]
) -> None:
    relations: collections.Counter[str] = collections.Counter()
    hidden_delta: collections.Counter[int] = collections.Counter()
    q_delta: collections.Counter[int] = collections.Counter()
    feature_counts: dict[
        tuple[str, int], collections.Counter[str]
    ] = collections.defaultdict(collections.Counter)
    widths: collections.Counter[int] = collections.Counter()
    for point in points:
        state = h153.state(point)
        q_value, square_value = state
        low, high = hidden_interval(point)
        current = baseline_hidden(point, state)
        kind = relation(current, low, high)
        relations[kind] += 1
        widths[rounded_scaled(high - low, 80)] += 1
        midpoint = (low + high) / 2
        hidden_delta[
            rounded_scaled(midpoint - current, 72)
        ] += 1
        square = fp_fraction(square_value)
        required_q = (midpoint - 1) / square
        q_delta[
            rounded_scaled(
                required_q - fp_fraction(q_value), 72
            )
        ] += 1
        schedule = h150.base_schedule(point)
        features = h146.trace(point, schedule)
        for feature, value in features.items():
            if feature == "global.exponent":
                continue
            feature_counts[(feature, value)][kind] += 1
    print(
        f"h155 {name}: n={len(points)} "
        f"relations={dict(relations)}"
    )
    print(
        "  hidden midpoint delta, units 2^-72: "
        + " ".join(
            f"{value:+d}:{count}"
            for value, count in hidden_delta.most_common(12)
        )
    )
    print(
        "  effective q midpoint delta, units 2^-72: "
        + " ".join(
            f"{value:+d}:{count}"
            for value, count in q_delta.most_common(12)
        )
    )
    print(
        "  interval widths, units 2^-80: "
        + " ".join(
            f"{value}:{count}"
            for value, count in widths.most_common(8)
        )
    )
    ranked = []
    for (feature, value), counts in feature_counts.items():
        selected = sum(counts.values())
        outside = (
            counts["need-up"] + counts["need-down"]
        )
        if outside == 0 or selected < 8:
            continue
        purity = max(
            counts["need-up"], counts["need-down"]
        ) / outside
        rate = outside / selected
        ranked.append(
            (
                purity * rate,
                purity,
                rate,
                outside,
                selected,
                feature,
                value,
                counts,
            )
        )
    ranked.sort(reverse=True)
    print("  strongest trace partitions:")
    for (
        _,
        purity,
        rate,
        outside,
        selected,
        feature,
        value,
        counts,
    ) in ranked[:16]:
        print(
            f"    {feature}={value}: "
            f"outside={outside}/{selected} "
            f"purity={purity:.3f} rate={rate:.3f} "
            f"{dict(counts)}"
        )


def main() -> None:
    old = h121.load_points()
    fresh147 = h147.load_capture(
        h147.DEFAULT_OUTPUT,
        h121.ROOT
        / "capture-kit-captures"
        / "skylake-fsin-h147",
    )
    fresh148 = h148.load_capture(
        h148.DEFAULT_OUTPUT,
        h121.ROOT
        / "capture-kit-captures"
        / "skylake-fsin-h148",
    )
    fresh151 = h151.load_capture(
        h151.DEFAULT_OUTPUT,
        h121.ROOT
        / "capture-kit-captures"
        / "skylake-fsin-h151",
    )
    report("old", old)
    report("h147", fresh147)
    report("h148", fresh148)
    report("h151", fresh151)


if __name__ == "__main__":
    main()
