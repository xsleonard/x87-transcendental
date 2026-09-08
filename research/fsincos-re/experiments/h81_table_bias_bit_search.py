#!/usr/bin/env python3
"""Search for a datapath bit that predicts the Round-21 S-state phase.

The constant family corrections repair many table-boundary failures but also
introduce new flips.  If the true extra S bits come from a rounded product or
sum, one of the retained or discarded operand bits may select the correction
phase.  This script performs a deliberately small decision-stump search:

* fit only on the even-index half of the complete dense capture;
* choose one S-bias numerator independently for feature bit 0 and 1;
* reject candidates unless they are non-worse on the odd dense half and every
  independent family capture (h59, h67, and h78 when available).

Features cover low retained bits of the reconstructed operands and the first
eight discarded bits at each product/sum boundary.  The search never consults
the master sweep.
"""

from __future__ import annotations

import dataclasses

import h58_constraint_search as h58
import h79_table_state_bias as h79


@dataclasses.dataclass(frozen=True)
class PointCosts:
    features: tuple[int, ...]
    costs: tuple[tuple[int, int, int], ...]


def mismatch_cost(
    point: h58.PreparedPoint,
    numerator: int,
) -> tuple[int, int, int]:
    values = h79.values(point, h79.BASE, numerator)
    mode_misses = 0
    output_misses = 0
    rn_misses = 0
    for side, value in enumerate(values):
        missed = False
        for rc_index, rc in enumerate(h58.RCS):
            mismatch = (
                h58.x87_round(value, rc)
                != point.raw.hw[rc_index][side]
            )
            mode_misses += mismatch
            rn_misses += mismatch if rc == "rn" else 0
            missed |= mismatch
        output_misses += missed
    return mode_misses, output_misses, rn_misses


def discarded_bits(value: h58.FP, count: int = 8) -> list[int]:
    shift = value[1].bit_length() - 64
    return [
        (
            (value[1] >> (shift - 1 - index)) & 1
            if shift > index
            else 0
        )
        for index in range(count)
    ]


def low_bits(value: h58.FP, count: int = 16) -> list[int]:
    rounded = h58.round_fp(value, 64, "rn")
    return [
        (rounded[1] >> index) & 1
        for index in range(count)
    ]


def feature_vector(point: h58.PreparedPoint) -> tuple[int, ...]:
    m_product = h58.mul_exact(point.p, point.asq)
    m = h58.round_fp(m_product, 64, "rn")
    correction_product = h58.mul_exact(m, point.a)
    correction = h58.round_fp(correction_product, 64, "rn")
    sine_sum = h58.add_exact(point.a, correction)
    sine_a = h58.round_fp(sine_sum, 64, "rn")
    tail_product = h58.mul_exact(point.q, point.asq)
    tail = h58.round_fp(tail_product, 64, "rn")
    retained = (
        point.a,
        point.asq,
        point.p,
        point.q,
        m,
        correction,
        sine_a,
        tail,
    )
    discarded = (
        m_product,
        correction_product,
        sine_sum,
        tail_product,
    )
    result: list[int] = []
    for value in retained:
        result.extend(low_bits(value))
    for value in discarded:
        result.extend(discarded_bits(value))
    result.append(point.a[0])
    return tuple(result)


def feature_names() -> tuple[str, ...]:
    names = []
    for carrier in (
        "a",
        "asq",
        "p",
        "q",
        "m",
        "correction",
        "S",
        "t",
    ):
        names.extend(
            f"{carrier}.retained.bit{index}" for index in range(16)
        )
    for carrier in (
        "p*asq",
        "m*a",
        "a+correction",
        "q*asq",
    ):
        names.extend(
            f"{carrier}.discarded.bit{index}"
            for index in range(8)
        )
    names.append("sign(a)")
    return tuple(names)


def prepare_costs(
    raw: list[h58.RawPoint],
) -> list[PointCosts]:
    result = []
    for item in raw:
        point = h58.prepare(item)
        result.append(
            PointCosts(
                features=feature_vector(point),
                costs=tuple(
                    mismatch_cost(point, numerator)
                    for numerator in range(9)
                ),
            )
        )
    return result


def sum_cost(
    points: list[PointCosts],
    feature: int | None,
    branch_bias: tuple[int, int],
) -> tuple[int, int, int]:
    total = [0, 0, 0]
    for point in points:
        branch = (
            0 if feature is None else point.features[feature]
        )
        cost = point.costs[branch_bias[branch]]
        for index in range(3):
            total[index] += cost[index]
    return tuple(total)


def best_branch_bias(
    points: list[PointCosts],
    feature: int,
) -> tuple[int, int]:
    choices = []
    for branch in (0, 1):
        branch_points = [
            point
            for point in points
            if point.features[feature] == branch
        ]
        ranked = [
            (
                sum_cost(branch_points, None, (numerator, numerator)),
                numerator,
            )
            for numerator in range(9)
        ]
        ranked.sort()
        choices.append(ranked[0][1])
    return choices[0], choices[1]


def non_worse(
    actual: tuple[int, int, int],
    baseline: tuple[int, int, int],
) -> bool:
    return actual <= baseline


def main() -> None:
    datasets = h79.load_datasets()
    names = feature_names()
    for family, fixed_bias in (("narrow", 4), ("wide", 5)):
        family_raw = [
            (name, raw)
            for name, actual_family, raw in datasets
            if actual_family == family
        ]
        dense_name, dense_raw = family_raw[0]
        train_raw = [
            point
            for index, point in enumerate(dense_raw)
            if index % 2 == 0
        ]
        heldout_raw = [
            point
            for index, point in enumerate(dense_raw)
            if index % 2
        ]
        scored = [
            ("dense-train", prepare_costs(train_raw)),
            ("dense-heldout", prepare_costs(heldout_raw)),
            *[
                (name, prepare_costs(raw))
                for name, raw in family_raw[1:]
            ],
        ]
        baselines = {
            name: sum_cost(points, None, (fixed_bias, fixed_bias))
            for name, points in scored
        }
        survivors = []
        for feature, feature_name in enumerate(names):
            branch_bias = best_branch_bias(scored[0][1], feature)
            if branch_bias[0] == branch_bias[1]:
                continue
            results = {
                name: sum_cost(points, feature, branch_bias)
                for name, points in scored
            }
            validation_names = [
                name for name, _ in scored if name != "dense-train"
            ]
            if not all(
                non_worse(results[name], baselines[name])
                for name in validation_names
            ):
                continue
            validation_total = tuple(
                sum(results[name][index] for name in validation_names)
                for index in range(3)
            )
            survivors.append(
                (
                    validation_total,
                    feature_name,
                    branch_bias,
                    results,
                )
            )
        survivors.sort(
            key=lambda row: (row[0], row[1], row[2])
        )
        print(
            f"{family}: fixed={fixed_bias}/32; "
            f"features={len(names)}; survivors={len(survivors)}"
        )
        for _, feature_name, branch_bias, results in survivors[:12]:
            print(
                f"  {feature_name}: bit0={branch_bias[0]}/32 "
                f"bit1={branch_bias[1]}/32"
            )
            for name, _ in scored:
                print(
                    f"    {name:14s} "
                    f"{results[name][0]}/{results[name][1]}/"
                    f"{results[name][2]} "
                    f"(fixed {baselines[name][0]}/"
                    f"{baselines[name][1]}/{baselines[name][2]})"
                )


if __name__ == "__main__":
    main()
