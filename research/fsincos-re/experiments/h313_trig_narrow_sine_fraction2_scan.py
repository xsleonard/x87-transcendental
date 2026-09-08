#!/usr/bin/env python3
"""Refine the second narrow carrier coordinate on a 1/256-ulp grid."""

from __future__ import annotations

import collections

import h79_table_state_bias as h79
import h207_tang_literal_fadd as h207
import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h291_trig_sine_bias_coordinate_scan as h291
import h309_trig_narrow_sine_fractional_rule as h309


NUMERATORS = tuple(range(9, 41))
CURRENT_NUMERATOR = 32
TARGET_COORDINATE = (-8, 19)


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


def main() -> None:
    datasets = []
    for name in ("dense", "sweep"):
        points = [
            point
            for point in h228.points(name)
            if point.prepared.joint.observed.family == "narrow"
        ]
        for split in ("train", "held"):
            datasets.append(
                (
                    f"{name}-narrow-{split}",
                    [
                        point
                        for point in points
                        if h207.h131.is_train(
                            point.prepared.joint.observed
                        ) == (split == "train")
                    ],
                )
            )

    baseline = []
    records = []
    for dataset_index, (_, points) in enumerate(datasets):
        total = h226.ZERO_JOINT
        for point in points:
            current_metric = h226.metric_for(
                point, h309.hidden_values(point)
            )
            total = h226.add_metric(total, current_metric)
            coord, rn64 = h291.coordinate(point)
            if coord == TARGET_COORDINATE:
                records.append(
                    (dataset_index, point, rn64, current_metric)
                )
        baseline.append(total)
    baseline_tuple = tuple(baseline)

    ranked = []
    for numerator in NUMERATORS:
        if numerator == CURRENT_NUMERATOR:
            continue
        candidate = list(baseline_tuple)
        changed = 0
        for dataset_index, point, rn64, old_metric in records:
            sine = h79.bias_toward_zero(rn64, numerator, 8)
            new_metric = h226.metric_for(
                point, h291.hidden_values(point, sine)
            )
            if new_metric == old_metric:
                continue
            changed += 1
            candidate[dataset_index] = add_delta(
                candidate[dataset_index],
                subtract_metric(new_metric, old_metric),
            )
        candidate_tuple = tuple(candidate)
        ranked.append(
            (
                h226.regressions(candidate_tuple, baseline_tuple),
                h226.objective(candidate_tuple),
                numerator,
                changed,
            )
        )
    ranked.sort()
    print(
        "h313 second narrow fractional scan: "
        f"datasets={len(datasets)} population={len(records)} "
        f"baseline={h226.objective(baseline_tuple)}"
    )
    for regressions, objective, numerator, changed in ranked:
        print(
            f"  bias={numerator}/256 objective={objective} "
            f"regressions={regressions} changed={changed}"
        )


if __name__ == "__main__":
    main()
