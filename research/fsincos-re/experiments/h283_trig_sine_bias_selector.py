#!/usr/bin/env python3
"""Search a physical selector for the h282 wide-sine bias near-miss.

With h275's corrected FMUL schedule, changing the wide shared-sine proxy from
5/32 to 3/32 ulp removes most residuals but creates a small regression set.
This pass extracts alignment, retained, guard, round, sticky, and producer
bits at the ``a + P*a^3`` FADD and tests one-term predicates that select bias
3 while leaving bias 5 elsewhere.  Input identity is not a feature.
"""

from __future__ import annotations

import collections
import dataclasses

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h200_p5_fadd_bitvector as h200
import h206_p5_fadd_complete as h206
import h218_fadd_residual_programs as h218
import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230


BIAS3 = dataclasses.replace(h228.CANDIDATE, sine_bias=3)


def state_inputs(point):
    observed = point.prepared.joint.observed
    base = point.prepared.base
    a = observed.point.a
    candidate = h228.CANDIDATE
    square = h230.quantize(h58.mul_exact(a, a), candidate.square)
    p = h230.horner(
        h58.S4,
        square,
        base.p_coefficients,
        candidate.p_horner_product,
        candidate.p_horner_sum,
    )
    p_square = h230.quantize(
        h58.mul_exact(p, square), candidate.p_square
    )
    p_times_a = h230.quantize(
        h58.mul_exact(p_square, a), candidate.p_times_a
    )
    exact_sum = h58.add_exact(a, p_times_a)
    rn64 = h230.quantize(exact_sum, "rn64")
    return a, square, p, p_square, p_times_a, exact_sum, rn64


def bit_features(result, prefix: str, value: h58.FP, count: int = 12):
    sig = value[1]
    width = sig.bit_length()
    result[f"{prefix}.width"] = width
    result[f"{prefix}.top-exponent"] = value[2] + width - 1
    for bit in range(count):
        result[f"{prefix}.bit{bit}"] = (sig >> bit) & 1


def features(point):
    observed = point.prepared.joint.observed
    a, square, p, p_square, p_times_a, exact_sum, rn64 = state_inputs(point)
    result = {
        "route.reduced": int(observed.source == "reduced"),
        "route.quadrant0": observed.signed_n & 1,
        "route.quadrant1": (observed.signed_n >> 1) & 1,
        "table.cell": observed.point.cell,
        "input.sign": observed.point.raw.sign,
    }
    bit_features(result, "a", a, 10)
    bit_features(result, "square", square, 10)
    bit_features(result, "p", p, 10)
    bit_features(result, "p-square", p_square, 10)
    bit_features(result, "p-times-a", p_times_a, 16)
    bit_features(result, "sine-rn64", rn64, 10)
    for width in (65, 66, 67, 68, 69, 70, 71, 72):
        value = h110.quantize(exact_sum, h110.Quant(width, "chop"))
        for bit in range(min(8, width - 63)):
            result[f"sum-chop{width}.bit{bit}"] = (value[1] >> bit) & 1

    a_bus = h200.normalized_bus(a)
    p_bus = h200.normalized_bus(p_times_a)
    difference = abs(a_bus.exponent - p_bus.exponent)
    result["align.difference"] = difference
    big, small = (
        (a_bus, p_bus)
        if a_bus.exponent >= p_bus.exponent
        else (p_bus, a_bus)
    )
    shifted, discarded = h200.shift_right(
        small.word << 1, big.exponent - small.exponent
    )
    result["align.discarded"] = int(discarded)
    for bit in range(16):
        result[f"align.shifted.bit{bit}"] = (shifted >> bit) & 1
    for mode in h206.MODES:
        bus, trace = h206.fadd(a_bus, p_bus, mode, normalize=True)
        result[f"bus.{mode}.operation"] = trace.operation
        for bit in range(10):
            result[f"bus.{mode}.bit{bit}"] = (bus.word >> bit) & 1
    return result


def add_delta(value, delta):
    return tuple(
        tuple(old_item + change for old_item, change in zip(old, lane_delta))
        for old, lane_delta in zip(value, delta)
    )


def subtract_metric(left, right):
    return tuple(
        tuple(new - old for new, old in zip(new_lane, old_lane))
        for new_lane, old_lane in zip(left, right)
    )


def joint_no_worse(value, baseline):
    return all(
        all(new <= old for new, old in zip(new_lane, old_lane))
        for new_lane, old_lane in zip(value, baseline)
    )


def main() -> None:
    datasets = h218.datasets()
    baseline = h230.score(datasets, h228.CANDIDATE)
    alternative = h230.score(datasets, BIAS3)
    records = []
    oracle = list(baseline)
    classes = collections.Counter()
    for dataset_index, (name, points) in enumerate(datasets):
        for point in points:
            old = h226.metric_for(
                point, h230.hidden_values(point, h228.CANDIDATE)
            )
            new = h226.metric_for(point, h230.hidden_values(point, BIAS3))
            if old == new:
                continue
            delta = subtract_metric(new, old)
            if joint_no_worse(new, old):
                classes["pointwise-improves"] += 1
                oracle[dataset_index] = add_delta(oracle[dataset_index], delta)
            elif joint_no_worse(old, new):
                classes["pointwise-regresses"] += 1
            else:
                classes["mixed"] += 1
            records.append((dataset_index, delta, features(point)))

    print(
        "h283 bias selector: "
        f"differing-points={len(records)} classes={dict(classes)}"
    )
    print(
        f"  bias5={h226.objective(baseline)} "
        f"bias3={h226.objective(alternative)} "
        f"point-oracle={h226.objective(tuple(oracle))}"
    )

    predicates = collections.defaultdict(list)
    for index, (_, _, values) in enumerate(records):
        for name, value in values.items():
            predicates[name, value].append(index)

    ranked = []
    for (feature, value), indexes in predicates.items():
        candidate = list(baseline)
        for index in indexes:
            dataset_index, delta, _ = records[index]
            candidate[dataset_index] = add_delta(
                candidate[dataset_index], delta
            )
        candidate_tuple = tuple(candidate)
        ranked.append(
            (
                h226.regressions(candidate_tuple, baseline),
                h226.objective(candidate_tuple),
                feature,
                value,
                len(indexes),
            )
        )
    ranked.sort()
    print("regression leaders:")
    for item in ranked[:30]:
        print(
            f"  regressions={item[0]} objective={item[1]} "
            f"active={item[4]} {item[2]}={item[3]}"
        )
    print("objective leaders:")
    for item in sorted(ranked, key=lambda item: (item[1], item[0], item[2]))[:20]:
        print(
            f"  objective={item[1]} regressions={item[0]} "
            f"active={item[4]} {item[2]}={item[3]}"
        )


if __name__ == "__main__":
    main()
