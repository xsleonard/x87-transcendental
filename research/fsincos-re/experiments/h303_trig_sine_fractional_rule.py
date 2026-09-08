#!/usr/bin/env python3
"""Freeze the hardware-validated Round-45 shared-sine carrier rule."""

from __future__ import annotations

import functools

import h79_table_state_bias as h79
import h218_fadd_residual_programs as h218
import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230
import h283_trig_sine_bias_selector as h283
import h287_trig_sine_bias_cegis as h287
import h291_trig_sine_bias_coordinate_scan as h291


BIAS3_COORDINATE = (-5, 13)
FRACTIONAL_COORDINATE = (-6, 15)


@functools.lru_cache(maxsize=None)
def coordinate(point):
    values = h283.features(point)
    return values["a.top-exponent"], values["align.difference"]


def hidden_values(point):
    coord = coordinate(point)
    wide = point.prepared.joint.observed.family == "wide"
    if wide and coord == BIAS3_COORDINATE:
        return h230.hidden_values(point, h283.BIAS3)
    if wide and coord == FRACTIONAL_COORDINATE:
        rn64 = h283.state_inputs(point)[-1]
        sine = h79.bias_toward_zero(rn64, 21, 8)
        return h291.hidden_values(point, sine)
    return h230.hidden_values(point, h228.CANDIDATE)


def score(datasets, rule: bool):
    totals = []
    for _, points in datasets:
        total = h226.ZERO_JOINT
        for point in points:
            values = (
                hidden_values(point)
                if rule
                else h230.hidden_values(point, h228.CANDIDATE)
            )
            total = h226.add_metric(total, h226.metric_for(point, values))
        totals.append(total)
    return tuple(totals)


def report(name, datasets):
    baseline = score(datasets, False)
    candidate = score(datasets, True)
    print(
        f"{name}: baseline={h226.objective(baseline)} "
        f"round45={h226.objective(candidate)} "
        f"regressions={h226.regressions(candidate, baseline)}"
    )
    for (dataset, _), old, new in zip(datasets, baseline, candidate):
        if old != new:
            print(f"  {dataset}: {old} -> {new}")


def main() -> None:
    report("old", h218.datasets())
    report("fresh-h285", [("h285", h287.fresh_points())])


if __name__ == "__main__":
    main()
