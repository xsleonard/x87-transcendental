#!/usr/bin/env python3
"""Freeze the hardware-validated Round-44 shared-sine carrier rule."""

from __future__ import annotations

import functools

import h218_fadd_residual_programs as h218
import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230
import h283_trig_sine_bias_selector as h283
import h287_trig_sine_bias_cegis as h287


BIAS3_COORDINATES = frozenset(((-5, 13), (-6, 15)))


@functools.lru_cache(maxsize=None)
def selected(point) -> bool:
    values = h283.features(point)
    coordinate = (
        values["a.top-exponent"],
        values["align.difference"],
    )
    return (
        point.prepared.joint.observed.family == "wide"
        and coordinate in BIAS3_COORDINATES
    )


def hidden_values(point):
    candidate = h283.BIAS3 if selected(point) else h228.CANDIDATE
    return h230.hidden_values(point, candidate)


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
        f"round44={h226.objective(candidate)} "
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
