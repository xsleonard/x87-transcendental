#!/usr/bin/env python3
"""Search downstream narrow-S schedules against exact tomography intervals.

h100 shows that changing product materialization before the final p
coefficient is observationally inert on the current captures.  The remaining
physical location is downstream: p*a^2, multiplication by a, and the final
addition of a.  This pass searches every 64..69-bit RN/chop schedule in the
direct, factored, fused, and full-fused topologies, using h78+h95's tight
shared-S intervals rather than final-output mismatch counts.

Only the best interval schedules are then evaluated on h59/h78/h95/h97, the
complete direct capture, and the independent master.  The cosine-tail U
chain stays at its baseline schedule because tomography localizes the
systematic correction to S.
"""

from __future__ import annotations

import dataclasses
import itertools

import h58_constraint_search as h58
import h78_paired_table_tomography as h78
import h79_table_state_bias as h79
import h98_narrow_joint_fit as h98
import h99_narrow_candidate_crossvalidate as h99
import h97_narrow_coefficient_discriminator as h97


DELTAS = (0, 7168, 8192)
BIASES = (0, 4)  # units of 1/32 ulp64(S)


def schedules() -> list[h58.TailConfig]:
    pm = h58.precision_modes()
    result = []
    for topology in ("direct", "factored"):
        for m, mid, sine in itertools.product(pm, repeat=3):
            result.append(
                h58.TailConfig(
                    topology=topology,
                    m_bits=m[0],
                    m_mode=m[1],
                    mid_bits=mid[0],
                    mid_mode=mid[1],
                    s_bits=sine[0],
                    s_mode=sine[1],
                )
            )
    for m, sine in itertools.product(pm, repeat=2):
        result.append(
            h58.TailConfig(
                topology="fma",
                m_bits=m[0],
                m_mode=m[1],
                s_bits=sine[0],
                s_mode=sine[1],
            )
        )
    for sine in pm:
        result.append(
            h58.TailConfig(
                topology="full-fma",
                s_bits=sine[0],
                s_mode=sine[1],
            )
        )
    return result


def interval_rank(
    intervals: list[h98.Interval],
    altered: list[h58.PreparedPoint],
    schedule: h58.TailConfig,
    bias: int,
) -> tuple[int, float, float]:
    outside = 0
    total_distance = 0.0
    worst_distance = 0.0
    for record, point in zip(intervals, altered):
        baseline_s = h79.table_state(record.point, h79.BASE)[1]
        candidate_s = h79.table_state(point, h79.StateSchedule(
            "candidate",
            schedule,
            schedule,
        ))[1]
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
    delta: int,
    schedule: h58.TailConfig,
    bias: int,
) -> tuple[h58.FP, h58.FP]:
    point = h97.alter_p(point, delta)
    state_schedule = h79.StateSchedule(
        "candidate",
        schedule,
        schedule,
    )
    return h79.values(point, state_schedule, bias)


def score(
    points: list[h58.PreparedPoint],
    delta: int,
    schedule: h58.TailConfig,
    bias: int,
) -> tuple[int, int, int]:
    mode_misses = 0
    output_misses = 0
    rn_misses = 0
    for point in points:
        predicted = values(point, delta, schedule, bias)
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
    delta: int,
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
            predicted = h79.values(point, h79.BASE, 5)
        else:
            predicted = values(point, delta, schedule, bias)
        actual = tuple(
            h58.x87_round(value, "rn")
            for value in h99.h60.rotate(predicted, signed_n)
        )
        mismatch = actual != expected
        misses += mismatch
        narrow += mismatch if not point.wide else 0
        wide += mismatch if point.wide else 0
    return misses, narrow, wide


def main() -> None:
    intervals = h98.tight_narrow_intervals()
    candidate_schedules = schedules()
    print(
        f"h101: {len(intervals)} tight intervals; "
        f"{len(DELTAS)} deltas x {len(BIASES)} biases x "
        f"{len(candidate_schedules)} schedules"
    )
    ranked = []
    for delta in DELTAS:
        altered = [
            h97.alter_p(record.point, delta)
            for record in intervals
        ]
        for bias in BIASES:
            for schedule in candidate_schedules:
                rank = interval_rank(
                    intervals,
                    altered,
                    schedule,
                    bias,
                )
                ranked.append((rank, delta, bias, schedule))
    ranked.sort(
        key=lambda item: (
            item[0],
            item[1],
            item[2],
            item[3].short(),
        )
    )

    raw_datasets = (
        (
            "h59",
            h99.load_narrow(
                h99.H59_INPUTS,
                h99.H59_CAPTURE,
                "narrow",
            ),
        ),
        (
            "h78",
            h99.load_narrow(
                h99.H78_INPUTS,
                h99.H78_CAPTURE,
                "constraint_paired_table",
            ),
        ),
        (
            "h95",
            h99.load_narrow(
                h99.H95_INPUTS,
                h99.H95_CAPTURE,
                "constraint_table_local",
            ),
        ),
        (
            "h97",
            h99.load_narrow(
                h99.H97_INPUTS,
                h99.H97_CAPTURE,
                "constraint_narrow_coefficient",
            ),
        ),
    )
    datasets = tuple(
        (name, [h58.prepare(item) for item in raw])
        for name, raw in raw_datasets
    )
    dense = [
        h58.prepare(point)
        for point in h58.load_points(
            h99.ROOT / "capture-kit-captures" / "pentiumII"
        )
        if point.exponent == -2
    ]
    master = h99.master_points()
    print("tomography finalists with architectural validation:")
    for rank, delta, bias, schedule in ranked[:24]:
        scores = tuple(
            score(points, delta, schedule, bias)
            for _, points in datasets
        )
        dense_result = score(dense, delta, schedule, bias)
        master_result = master_score(
            master,
            delta,
            schedule,
            bias,
        )
        print(
            f"  delta={delta:+5d} bias={bias}/32 "
            f"{schedule.short():46s}: "
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
