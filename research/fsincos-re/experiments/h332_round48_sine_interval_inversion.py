#!/usr/bin/env python3
"""Invert the remaining sweep outputs into shared-sine bias intervals.

Round 48 uses one of six coordinate-level fractions around the common P6
67-bit carrier.  For each of the 80 remaining paired residual points, this
pass scans the complete 0/256..64/256 local-ulp neighborhood and records all
numerators that satisfy both captured lanes and all RN/RD/RU+C1 constraints.
It also records the reconstructed sine-FADD exact remainder, so a numerical
relationship can be tested without selecting on input identity.
"""

from __future__ import annotations

import collections
import fractions

import h58_constraint_search as h58
import h79_table_state_bias as h79
import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h283_trig_sine_bias_selector as h283
import h291_trig_sine_bias_coordinate_scan as h291
import h322_trig_narrow_sine_fraction3_rule as h322
import h326_p6_tmp_sine_projection as h326


NUMERATORS = tuple(range(65))


def signed_integer(value: h58.FP, scale: int) -> int:
    sign, significand, value_scale = value
    if value_scale < scale:
        raise ValueError((value, scale))
    magnitude = significand << (value_scale - scale)
    return -magnitude if sign else magnitude


def exact_remainder_256(exact_sum: h58.FP, rn64: h58.FP):
    top = rn64[2] + rn64[1].bit_length() - 1
    unit_scale = top - 63 - 8
    scale = min(unit_scale, exact_sum[2], rn64[2])
    delta = signed_integer(exact_sum, scale) - signed_integer(rn64, scale)
    return fractions.Fraction(delta, 1 << (unit_scale - scale))


def ranges(values):
    if not values:
        return ()
    result = []
    start = previous = values[0]
    for value in values[1:]:
        if value != previous + 1:
            result.append((start, previous))
            start = value
        previous = value
    result.append((start, previous))
    return tuple(result)


def main() -> None:
    records = []
    lane_solvable = collections.Counter()
    joint_solvable = 0
    for point in h228.points("sweep"):
        baseline = h226.metric_for(point, h322.hidden_values(point))
        if baseline == h226.ZERO_JOINT:
            continue
        a, square, p, p_square, p_times_a, exact_sum, rn64 = (
            h283.state_inputs(point)
        )
        joint = []
        lane_values = [[], []]
        for numerator in NUMERATORS:
            sine = h79.bias_toward_zero(rn64, numerator, 8)
            metric = h226.metric_for(
                point, h291.hidden_values(point, sine)
            )
            if metric == h226.ZERO_JOINT:
                joint.append(numerator)
            for lane in (0, 1):
                if metric[lane] == (0, 0, 0):
                    lane_values[lane].append(numerator)
        residual_lanes = tuple(
            lane for lane in (0, 1) if baseline[lane] != (0, 0, 0)
        )
        for lane in residual_lanes:
            lane_solvable[lane] += bool(lane_values[lane])
        joint_solvable += bool(joint)
        observed = point.prepared.joint.observed
        records.append(
            (
                observed.family,
                observed.source,
                observed.point.cell,
                h291.coordinate(point)[0],
                h326.numerator(point),
                residual_lanes,
                ranges(joint),
                tuple(ranges(values) for values in lane_values),
                exact_remainder_256(exact_sum, rn64),
            )
        )
    print(
        "h332 sine interval inversion: "
        f"residual-points={len(records)} joint-solvable={joint_solvable} "
        f"lane-solvable={dict(lane_solvable)}"
    )
    grouped = collections.Counter(
        (
            family,
            source,
            cell,
            coordinate,
            current,
            residual_lanes,
            joint_ranges,
        )
        for (
            family,
            source,
            cell,
            coordinate,
            current,
            residual_lanes,
            joint_ranges,
            lane_ranges,
            remainder,
        ) in records
    )
    print("joint interval groups:")
    for key, count in sorted(grouped.items()):
        print(f"  count={count:2d} {key}")
    print("joint-solvable exact-remainder rows:")
    for record in records:
        if not record[6]:
            continue
        print(
            f"  {record[0]}/{record[1]}/cell{record[2]} "
            f"coord={record[3]} current={record[4]} "
            f"lanes={record[5]} joint={record[6]} "
            f"fadd-rem={record[8]}"
        )


if __name__ == "__main__":
    main()
