#!/usr/bin/env python3
"""Recompute internal-cosine tomography after Rounds 30 through 33.

The solved square, tail, fifth-sum, and fifth-product selectors are frozen.
RN/RD/RU again bound the hidden positive cosine state.  This pass reports
the remaining correction directions and ranks one- and two-bit partitions
only from the adjacent product-5, sum-5, tail, final, square, and global
trace state.
"""

from __future__ import annotations

import collections
import fractions
import itertools

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h119_fcos_standalone as h119
import h121_fsin_internal_cosine as h121
import h146_fsin_cosine_boolean_search as h146
import h155_fsin_cosine_state_tomography as h155
import h162_fsin_cosine_round32_residual_search as h162
import h163_fsin_cosine_product_discriminator as h163


Fraction = fractions.Fraction
P67_ODD = next(
    candidate
    for candidate in h163.CANDIDATES
    if candidate.name == "product5-67o"
)
LOCAL_PREFIXES = (
    "global.",
    "square.",
    "product-5.",
    "sum-5.",
    "tail.",
    "final-sum.",
)


def schedule(point: h121.Point) -> h119.Schedule:
    return h162.variant_schedule(point, P67_ODD.variant)


def state(
    point: h121.Point, value_schedule: h119.Schedule
) -> tuple[h58.FP, h58.FP]:
    observed = point.observed
    magnitude: h58.FP = (
        0,
        observed.raw.sig,
        observed.raw.exponent - 63,
    )
    square = h110.quantize(
        h58.mul_exact(magnitude, magnitude),
        value_schedule.square,
    )
    value = h119.coefficient(
        h58.C6[0], value_schedule, 0
    )
    for index, row in enumerate(h58.C6[1:]):
        product = h110.quantize(
            h58.mul_exact(value, square),
            value_schedule.products[index],
        )
        value = h110.quantize(
            h58.add_exact(
                product,
                h119.coefficient(
                    row, value_schedule, index + 1
                ),
            ),
            value_schedule.sums[index],
        )
    return value, square


def positive_hidden(
    point: h121.Point, value_schedule: h119.Schedule
) -> Fraction:
    value = h146.hidden_value(point, value_schedule)
    result = h155.fp_fraction(value)
    return -result if point.negate else result


def local_features(
    point: h121.Point, value_schedule: h119.Schedule
) -> dict[str, int]:
    return {
        name: value
        for name, value in h146.trace(
            point, value_schedule
        ).items()
        if name != "global.exponent"
        and name.startswith(LOCAL_PREFIXES)
    }


def report(points: list[h121.Point]) -> None:
    rows = []
    relations: collections.Counter[str] = collections.Counter()
    hidden_delta: collections.Counter[int] = collections.Counter()
    q_delta: collections.Counter[int] = collections.Counter()
    for point in points:
        value_schedule = schedule(point)
        q_value, square_value = state(point, value_schedule)
        low, high = h155.hidden_interval(point)
        current = positive_hidden(point, value_schedule)
        kind = h155.relation(current, low, high)
        relations[kind] += 1
        midpoint = (low + high) / 2
        hidden_delta[
            h155.rounded_scaled(midpoint - current, 72)
        ] += 1
        square = h155.fp_fraction(square_value)
        required_q = (midpoint - 1) / square
        q_delta[
            h155.rounded_scaled(
                required_q - h155.fp_fraction(q_value), 72
            )
        ] += 1
        rows.append(
            (
                point,
                kind,
                local_features(point, value_schedule),
            )
        )
    print(
        f"h166 old Round-33: n={len(points)} "
        f"relations={dict(relations)}"
    )
    print(
        "  hidden midpoint delta, units 2^-72: "
        + " ".join(
            f"{value:+d}:{count}"
            for value, count in hidden_delta.most_common(16)
        )
    )
    print(
        "  effective q midpoint delta, units 2^-72: "
        + " ".join(
            f"{value:+d}:{count}"
            for value, count in q_delta.most_common(16)
        )
    )

    feature_names = tuple(sorted(rows[0][2]))
    predicates = tuple(
        (name, value)
        for name in feature_names
        for value in sorted(
            {features[name] for _, _, features in rows}
        )
    )
    ranked = []
    for count in (1, 2):
        for terms in itertools.combinations(predicates, count):
            if len({name for name, _ in terms}) != count:
                continue
            selected = [
                kind
                for _, kind, features in rows
                if all(
                    features[name] == value
                    for name, value in terms
                )
            ]
            if len(selected) < 4:
                continue
            counts = collections.Counter(selected)
            outside = counts["need-up"] + counts["need-down"]
            if outside < 2:
                continue
            dominant = max(
                counts["need-up"], counts["need-down"]
            )
            purity = dominant / outside
            outside_rate = outside / len(selected)
            coverage = dominant / (
                relations["need-up"]
                if counts["need-up"] >= counts["need-down"]
                else relations["need-down"]
            )
            ranked.append(
                (
                    -(purity * outside_rate * coverage),
                    -dominant,
                    len(selected),
                    terms,
                    counts,
                )
            )
    ranked.sort()
    print("  strongest adjacent-state partitions:")
    for _, _, selected, terms, counts in ranked[:30]:
        label = " & ".join(
            f"{name}={value}" for name, value in terms
        )
        print(
            f"    {label}: selected={selected} "
            f"{dict(counts)}"
        )


def main() -> None:
    report(h121.load_points())


if __name__ == "__main__":
    main()
