#!/usr/bin/env python3
"""Freeze the hardware-validated Round-47 shared-sine carrier rule."""

from __future__ import annotations

import functools

import h79_table_state_bias as h79
import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230
import h283_trig_sine_bias_selector as h283
import h291_trig_sine_bias_coordinate_scan as h291
import h309_trig_narrow_sine_fractional_rule as h309


NARROW_FRACTIONAL_COORDINATE = (-8, 19)


@functools.lru_cache(maxsize=None)
def coordinate(point):
    return h291.coordinate(point)[0]


def hidden_values(point):
    observed = point.prepared.joint.observed
    if (
        observed.family == "narrow"
        and coordinate(point) == NARROW_FRACTIONAL_COORDINATE
    ):
        rn64 = h283.state_inputs(point)[-1]
        sine = h79.bias_toward_zero(rn64, 30, 8)
        return h291.hidden_values(point, sine)
    return h309.hidden_values(point)


def score(datasets):
    totals = []
    for _, points in datasets:
        total = h226.ZERO_JOINT
        for point in points:
            total = h226.add_metric(
                total,
                h226.metric_for(point, hidden_values(point)),
            )
        totals.append(total)
    return tuple(totals)


def main() -> None:
    # The full narrow train/held comparison is frozen by h312-h313.
    dense_sweep = []
    for name in ("dense", "sweep"):
        dense_sweep.append(
            (
                name,
                [
                    point
                    for point in h228.points(name)
                    if point.prepared.joint.observed.family == "narrow"
                ],
            )
        )
    baseline = []
    for _, points in dense_sweep:
        total = h226.ZERO_JOINT
        for point in points:
            total = h226.add_metric(
                total,
                h226.metric_for(
                    point,
                    h230.hidden_values(point, h228.CANDIDATE),
                ),
            )
        baseline.append(total)
    candidate = score(dense_sweep)
    print(
        "narrow dense/sweep: "
        f"baseline={h226.objective(tuple(baseline))} "
        f"round47={h226.objective(candidate)} "
        f"regressions={h226.regressions(candidate, tuple(baseline))}"
    )


if __name__ == "__main__":
    main()
