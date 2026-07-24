#!/usr/bin/env python3
"""Synthesize constrained low-bit rules for FSIN's internal cosine path.

h144 and h145 reject uniform raw-grid and terminal-FMUL replacements.  This
pass asks the narrower remaining question: can one already-enumerated h119
materialization be selected by a single physically meaningful datapath bit?

Eligible predicates are limited to sign, product normalization, retained
LSB, guard, sticky, low operand bits, trailing-zero thresholds, and the
output-negation path.  A conditional candidate must be componentwise no
worse than h121 on both complete deterministic halves.
"""

from __future__ import annotations

import dataclasses
from collections import defaultdict

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h119_fcos_standalone as h119
import h121_fsin_internal_cosine as h121


Metric = tuple[int, int, int]


def trailing_zeros(value: int) -> int:
    return (value & -value).bit_length() - 1 if value else 0


def rounded_features(
    prefix: str,
    value: h58.FP,
    quant: h110.Quant,
    left: h58.FP | None = None,
    right: h58.FP | None = None,
) -> dict[str, int]:
    bits = quant.bits or 64
    significand = value[1]
    shift = significand.bit_length() - bits
    top = significand >> shift if shift > 0 else significand << -shift
    remainder = (
        significand & ((1 << shift) - 1) if shift > 0 else 0
    )
    guard = (remainder >> (shift - 1)) & 1 if shift > 0 else 0
    sticky = int(
        bool(remainder & ((1 << (shift - 1)) - 1))
    ) if shift > 1 else 0
    result = {
        f"{prefix}.sign": value[0],
        f"{prefix}.lsb": top & 1,
        f"{prefix}.guard": guard,
        f"{prefix}.sticky": sticky,
        f"{prefix}.discarded": int(bool(remainder)),
    }
    if left is not None and right is not None:
        left_width = left[1].bit_length()
        right_width = right[1].bit_length()
        result[f"{prefix}.norm2"] = int(
            significand.bit_length() == left_width + right_width
        )
        result[f"{prefix}.left-low3"] = left[1] & 7
        result[f"{prefix}.right-low3"] = right[1] & 7
        tzsum = trailing_zeros(left[1]) + trailing_zeros(right[1])
        for threshold in (3, 4, 5, 6):
            result[f"{prefix}.tz>={threshold}"] = int(
                tzsum >= threshold
            )
    return result


def trace(
    point: h121.Point,
    schedule: h119.Schedule | None = None,
) -> dict[str, int]:
    observed = point.observed
    schedule = schedule or h121.FSIN_INTERNAL_COSINE
    magnitude: h58.FP = (
        0,
        observed.raw.sig,
        observed.raw.exponent - 63,
    )
    result = {
        "global.negate": int(point.negate),
        "global.exponent": observed.raw.exponent,
        "global.input-low3": observed.raw.sig & 7,
    }
    square_exact = h58.mul_exact(magnitude, magnitude)
    result.update(
        rounded_features(
            "square",
            square_exact,
            schedule.square,
            magnitude,
            magnitude,
        )
    )
    square = h110.quantize(square_exact, schedule.square)
    value = h119.coefficient(h58.C6[0], schedule, 0)
    for index, row in enumerate(h58.C6[1:], 1):
        product_exact = h58.mul_exact(value, square)
        result.update(
            rounded_features(
                f"product-{index}",
                product_exact,
                schedule.products[index - 1],
                value,
                square,
            )
        )
        product = h110.quantize(
            product_exact, schedule.products[index - 1]
        )
        constant = h119.coefficient(row, schedule, index)
        sum_exact = h58.add_exact(product, constant)
        result.update(
            rounded_features(
                f"sum-{index}",
                sum_exact,
                schedule.sums[index - 1],
            )
        )
        value = h110.quantize(sum_exact, schedule.sums[index - 1])
    tail_exact = h58.mul_exact(value, square)
    result.update(
        rounded_features(
            "tail",
            tail_exact,
            schedule.tail,
            value,
            square,
        )
    )
    tail = h110.quantize(tail_exact, schedule.tail)
    final_exact = h58.add_exact(h58.ONE, tail)
    result.update(
        rounded_features("final-sum", final_exact, h110.Quant(64, "rn"))
    )
    return result


def hidden_value(
    point: h121.Point, schedule: h119.Schedule
) -> h58.FP:
    value = h119.hidden_value(point.observed, schedule)
    return h58.neg(value) if point.negate else value


def metric(point: h121.Point, hidden: h58.FP) -> Metric:
    mode_misses = 0
    c1_misses = 0
    for index, rc in enumerate(h58.RCS):
        expected = point.observed.outputs[index]
        predicted = h58.x87_round(hidden, rc)
        mismatch = predicted != expected
        mode_misses += mismatch
        if not mismatch:
            predicted_c1 = (
                h110.compare_magnitude(expected, hidden) > 0
            )
            c1_misses += (
                predicted_c1 != point.observed.c1[index]
            )
    return mode_misses, int(bool(mode_misses)), c1_misses


def add(left: Metric, right: Metric) -> Metric:
    return tuple(a + b for a, b in zip(left, right))  # type: ignore[return-value]


def relevant_features(
    coordinate: str, features: dict[str, int]
) -> tuple[str, ...]:
    prefixes = ("global.",)
    if coordinate == "final-sum":
        prefixes += ("final-sum.", "tail.")
    elif coordinate.startswith(
        ("square", "product-", "sum-", "tail")
    ):
        prefixes += (coordinate + ".",)
    return tuple(
        key for key in features
        if any(key.startswith(prefix) for prefix in prefixes)
    )


def no_worse(left: Metric, right: Metric) -> bool:
    return all(a <= b for a, b in zip(left, right))


def main() -> None:
    points = h121.load_points()
    current = h121.FSIN_INTERNAL_COSINE
    traces = {
        point.observed.raw.index: trace(point) for point in points
    }
    base_metrics = {
        point.observed.raw.index: metric(
            point, hidden_value(point, current)
        )
        for point in points
    }
    train_base: Metric = (0, 0, 0)
    held_base: Metric = (0, 0, 0)
    for point in points:
        point_metric = base_metrics[point.observed.raw.index]
        if h121.is_train(point):
            train_base = add(train_base, point_metric)
        else:
            held_base = add(held_base, point_metric)
    print(
        f"h146 baseline train={train_base} heldout={held_base}"
    )

    survivors = []
    tested = 0
    first_trace = traces[points[0].observed.raw.index]
    for coordinate in h119.coordinates():
        if coordinate.name.startswith("coefficient"):
            continue
        candidates = tuple(
            candidate
            for candidate in dict.fromkeys(
                coordinate.candidates(current)
            )
            if candidate != current
        )
        feature_names = relevant_features(
            coordinate.name, first_trace
        )
        for candidate in candidates:
            tested += 1
            deltas: dict[
                tuple[str, int], list[Metric]
            ] = defaultdict(lambda: [(0, 0, 0), (0, 0, 0)])
            for point in points:
                index = point.observed.raw.index
                candidate_metric = metric(
                    point, hidden_value(point, candidate)
                )
                base_metric = base_metrics[index]
                delta: Metric = tuple(
                    a - b
                    for a, b in zip(candidate_metric, base_metric)
                )  # type: ignore[assignment]
                half = 0 if h121.is_train(point) else 1
                for feature in feature_names:
                    key = (feature, traces[index][feature])
                    deltas[key][half] = add(deltas[key][half], delta)
            for (feature, value), (train_delta, held_delta) in deltas.items():
                train_score = add(train_base, train_delta)
                held_score = add(held_base, held_delta)
                if (
                    no_worse(train_score, train_base)
                    and no_worse(held_score, held_base)
                    and (
                        train_score != train_base
                        or held_score != held_base
                    )
                ):
                    survivors.append(
                        (
                            train_score[0] + held_score[0],
                            train_score[2] + held_score[2],
                            train_score[1] + held_score[1],
                            coordinate.name,
                            feature,
                            value,
                            candidate.short(),
                            train_score,
                            held_score,
                            candidate,
                        )
                    )
    survivors.sort()
    print(
        f"h146 tested {tested} one-coordinate schedules; "
        f"{len(survivors)} conditional rules survive"
    )
    for entry in survivors[:30]:
        (
            _,
            _,
            _,
            coordinate,
            feature,
            value,
            label,
            train_score,
            held_score,
            _,
        ) = entry
        print(
            f"  {coordinate} if {feature}={value}: "
            f"train={train_score} heldout={held_score}"
        )
        print(f"    {label}")


if __name__ == "__main__":
    main()
