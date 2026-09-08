#!/usr/bin/env python3
"""Search wide shared-S schedules against h78+h95 tomography.

The combined Round-23 master residue is dominated by 133 wide-family table
cases.  This pass applies the h101 downstream search to the six-term family:
all 64..69-bit RN/chop direct, factored, fused, and full-fused S schedules
are ranked on exact paired-state intervals, with and without Round 21's
5/32-ulp equivalent state correction.  Finalists are then validated on the
complete wide capture, h59, h67, h78, h95, and the master.
"""

from __future__ import annotations

import h58_constraint_search as h58
import h59_discriminator as h59
import h60_round16_parity as h60
import h67_wide_producer_discriminator as h67
import h78_paired_table_tomography as h78
import h79_table_state_bias as h79
import h98_narrow_joint_fit as h98
import h99_narrow_candidate_crossvalidate as h99
import h101_narrow_s_schedule_tomography as h101
import h97_narrow_coefficient_discriminator as h97


BIASES = (0, 5)


def interval_rank(
    intervals: list[h98.Interval],
    schedule: h58.TailConfig,
    bias: int,
) -> tuple[int, float, float]:
    state_schedule = h79.StateSchedule(
        "candidate",
        schedule,
        schedule,
    )
    outside = 0
    total_distance = 0.0
    worst_distance = 0.0
    for record in intervals:
        baseline_s = h79.table_state(record.point, h79.BASE)[1]
        candidate_s = h79.table_state(
            record.point,
            state_schedule,
        )[1]
        candidate_s = h79.bias_toward_zero(candidate_s, bias)
        delta_s = h58.add_exact(candidate_s, h58.neg(baseline_s))
        value = h78.fp_fraction(delta_s)
        if value < record.low:
            distance = float((record.low - value) / record.ulp)
        elif value > record.high:
            distance = float((value - record.high) / record.ulp)
        else:
            distance = 0.0
        outside += distance != 0.0
        total_distance += distance
        worst_distance = max(worst_distance, distance)
    return outside, total_distance, worst_distance


def values(
    point: h58.PreparedPoint,
    schedule: h58.TailConfig,
    bias: int,
) -> tuple[h58.FP, h58.FP]:
    state_schedule = h79.StateSchedule(
        "candidate",
        schedule,
        schedule,
    )
    return h79.values(point, state_schedule, bias)


def score(
    points: list[h58.PreparedPoint],
    schedule: h58.TailConfig,
    bias: int,
) -> tuple[int, int, int]:
    mode_misses = 0
    output_misses = 0
    rn_misses = 0
    for point in points:
        predicted = values(point, schedule, bias)
        for side, value in enumerate(predicted):
            missed_output = False
            for rc_index, rc in enumerate(h58.RCS):
                mismatch = (
                    h58.x87_round(value, rc)
                    != point.raw.hw[rc_index][side]
                )
                mode_misses += mismatch
                rn_misses += mismatch if rc_index == 0 else 0
                missed_output |= mismatch
            output_misses += missed_output
    return mode_misses, output_misses, rn_misses


def master_score(
    points: list[
        tuple[
            tuple[int, h58.PreparedPoint, bool] | None,
            tuple[tuple[int, int], tuple[int, int]] | None,
        ]
    ],
    schedule: h58.TailConfig,
    bias: int,
) -> tuple[int, int, int]:
    misses = 0
    narrow = 0
    wide = 0
    for active, expected in points:
        if active is None:
            continue
        if expected is None:
            raise AssertionError("table-active master input returned C2")
        signed_n, point, _ = active
        if point.wide:
            predicted = values(point, schedule, bias)
        else:
            altered = h97.alter_p(point, 7168)
            predicted = h79.values(altered, h79.BASE, 4)
        actual = tuple(
            h58.x87_round(value, "rn")
            for value in h60.rotate(predicted, signed_n)
        )
        mismatch = actual != expected
        misses += mismatch
        narrow += mismatch if not point.wide else 0
        wide += mismatch if point.wide else 0
    return misses, narrow, wide


def main() -> None:
    intervals = h98.tight_intervals("wide")
    candidate_schedules = h101.schedules()
    print(
        f"h103: {len(intervals)} tight wide intervals; "
        f"{len(BIASES)} biases x {len(candidate_schedules)} schedules"
    )
    ranked = []
    for bias in BIASES:
        for schedule in candidate_schedules:
            rank = interval_rank(intervals, schedule, bias)
            ranked.append((rank, bias, schedule))
    ranked.sort(
        key=lambda item: (
            item[0],
            item[1],
            item[2].short(),
        )
    )

    dense = [
        h58.prepare(point)
        for point in h58.load_points(
            h99.ROOT / "capture-kit-captures" / "pentiumII"
        )
        if point.exponent == -1
    ]
    h59_raw = h59.load_score_points(
        h99.H59_CAPTURE / "wide_inputs.txt",
        h99.H59_CAPTURE,
        "wide",
    )
    h67_raw = h59.load_score_points(
        h79.H67_INPUTS,
        h79.H67_CAPTURE,
        "constraint_wide_producer",
    )
    h78_raw = [
        point
        for point in h59.load_score_points(
            h99.H78_INPUTS,
            h99.H78_CAPTURE,
            "constraint_paired_table",
        )
        if point.exponent == -1
    ]
    h95_raw = [
        point
        for point in h59.load_score_points(
            h99.H95_INPUTS,
            h99.H95_CAPTURE,
            "constraint_table_local",
        )
        if point.exponent == -1
    ]
    datasets = (
        ("h59", [h58.prepare(point) for point in h59_raw]),
        ("h67", [h58.prepare(point) for point in h67_raw]),
        ("h78", [h58.prepare(point) for point in h78_raw]),
        ("h95", [h58.prepare(point) for point in h95_raw]),
    )
    master = h99.master_points()
    print("tomography finalists with architectural validation:")
    for rank, bias, schedule in ranked[:24]:
        scores = tuple(
            score(points, schedule, bias)
            for _, points in datasets
        )
        dense_result = score(dense, schedule, bias)
        master_result = master_score(
            master,
            schedule,
            bias,
        )
        print(
            f"  bias={bias}/32 {schedule.short():46s}: "
            f"interval={rank[0]:3d}/{rank[1]:7.3f}/"
            f"{rank[2]:5.3f} "
            f"dense={dense_result[0]:4d} "
            f"master={master_result[0]:3d}"
            f"(N={master_result[1]:2d},W={master_result[2]:3d}); "
            + " ".join(
                f"{name}={result[0]}"
                for (name, _), result in zip(datasets, scores)
            )
        )


if __name__ == "__main__":
    main()
