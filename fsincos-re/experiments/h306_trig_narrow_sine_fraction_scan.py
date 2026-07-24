#!/usr/bin/env python3
"""Scan fractional shared-sine carrier coordinates in the narrow table."""

from __future__ import annotations

import collections

import h79_table_state_bias as h79
import h207_tang_literal_fadd as h207
import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230
import h283_trig_sine_bias_selector as h283
import h291_trig_sine_bias_coordinate_scan as h291


NUMERATORS = tuple(range(9, 41))
DENOMINATOR_BITS = 8
CURRENT_NUMERATOR = 32
TARGET_COORDINATE = (-6, 15)


def coordinate(point):
    return h291.coordinate(point)[0]


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
    records = collections.defaultdict(list)
    populations = collections.Counter()
    for dataset_index, (_, points) in enumerate(datasets):
        total = h226.ZERO_JOINT
        for point in points:
            current = h230.hidden_values(point, h228.CANDIDATE)
            current_metric = h226.metric_for(point, current)
            total = h226.add_metric(total, current_metric)
            observed = point.prepared.joint.observed
            if observed.family != "narrow":
                continue
            coord = coordinate(point)
            if coord != TARGET_COORDINATE:
                continue
            populations[coord] += 1
            records[coord].append((dataset_index, point, current_metric))
        baseline.append(total)
    baseline_tuple = tuple(baseline)

    ranked = []
    for coord, points in records.items():
        for numerator in NUMERATORS:
            if numerator == CURRENT_NUMERATOR:
                continue
            candidate = list(baseline_tuple)
            changed = 0
            for dataset_index, point, old_metric in points:
                rn64 = h283.state_inputs(point)[-1]
                sine = h79.bias_toward_zero(
                    rn64, numerator, DENOMINATOR_BITS
                )
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
                    coord,
                    numerator,
                    populations[coord],
                    changed,
                    candidate_tuple,
                )
            )
    ranked.sort()
    print(
        "h306 narrow fractional scan: "
        f"datasets={len(datasets)} bins={len(records)} "
        f"candidates={len(ranked)} baseline={h226.objective(baseline_tuple)}"
    )
    print("regression leaders:")
    for item in ranked[:40]:
        print(
            f"  regressions={item[0]} objective={item[1]} "
            f"coord={item[2]} bias={item[3]}/256 "
            f"population={item[4]} changed={item[5]}"
        )
    print("objective leaders:")
    for item in sorted(ranked, key=lambda item: (item[1], item[0], item[2]))[:24]:
        print(
            f"  objective={item[1]} regressions={item[0]} "
            f"coord={item[2]} bias={item[3]}/256 "
            f"population={item[4]} changed={item[5]}"
        )


if __name__ == "__main__":
    main()
