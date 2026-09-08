#!/usr/bin/env python3
"""Project the Round-48 sine proxy onto the finite P6 TMP carrier.

An architectural extended significand occupies internal carrier bits 66:3;
bits 2:0 are the three additional numerical positions.  A finite normalized
TMP value therefore has at most 67 significant numerical bits.  Round 48's
fractions are output-equivalent analysis proxies and can contain more bits.

This pass tests whether the proxy survives a single coherent 67-bit TMP
materialization before its two reconstruction products.  It does not alter
any upstream operation or downstream arithmetic class.
"""

from __future__ import annotations

import collections

import h79_table_state_bias as h79
import h110_fsin_standalone as h110
import h218_fadd_residual_programs as h218
import h226_p6_full_sine_graph as h226
import h283_trig_sine_bias_selector as h283
import h287_trig_sine_bias_cegis as h287
import h291_trig_sine_bias_coordinate_scan as h291
import h322_trig_narrow_sine_fraction3_rule as h322


PROJECTIONS = {
    "rn67": h110.Quant(67, "rn"),
    "chop67": h110.Quant(67, "chop"),
    "away67": h110.Quant(67, "away"),
    "odd67": h110.Quant(67, "odd"),
    "rn68": h110.Quant(68, "rn"),
    "chop68": h110.Quant(68, "chop"),
    "away68": h110.Quant(68, "away"),
    "odd68": h110.Quant(68, "odd"),
    "rn69": h110.Quant(69, "rn"),
    "rn70": h110.Quant(70, "rn"),
    "rn71": h110.Quant(71, "rn"),
    "rn72": h110.Quant(72, "rn"),
}


def numerator(point) -> int:
    observed = point.prepared.joint.observed
    coordinate = h291.coordinate(point)[0]
    if observed.family == "wide":
        if coordinate == (-5, 13):
            return 24
        if coordinate == (-6, 15):
            return 21
        return 40
    if coordinate == (-6, 15):
        return 29
    if coordinate == (-8, 19):
        return 30
    if coordinate == (-7, 17):
        return 34
    return 32


def proxy_sine(point):
    rn64 = h283.state_inputs(point)[-1]
    return h79.bias_toward_zero(rn64, numerator(point), 8)


def hidden_values(point, projection: str | None):
    if projection is None:
        return h322.hidden_values(point)
    sine = h110.quantize(proxy_sine(point), PROJECTIONS[projection])
    return h291.hidden_values(point, sine)


def canonical_width(value) -> int:
    significand = value[1]
    if not significand:
        return 0
    trailing_zeroes = (significand & -significand).bit_length() - 1
    return significand.bit_length() - trailing_zeroes


def score(datasets, projection: str | None):
    totals = []
    profiles = []
    widths = collections.Counter()
    changed = 0
    for _, points in datasets:
        total = h226.ZERO_JOINT
        profile = []
        for point in points:
            if projection is not None:
                widths[canonical_width(proxy_sine(point))] += 1
            values = hidden_values(point, projection)
            baseline_values = h322.hidden_values(point)
            changed += values != baseline_values
            metric = h226.metric_for(point, values)
            total = h226.add_metric(total, metric)
            profile.append(metric)
        totals.append(total)
        profiles.append(tuple(profile))
    return tuple(totals), tuple(profiles), widths, changed


def main() -> None:
    datasets = [*h218.datasets(), ("h285", h287.fresh_points())]
    baseline, baseline_profile, _, _ = score(datasets, None)
    point_count = sum(len(points) for _, points in datasets)
    print(
        "h326 P6 TMP sine projection: "
        f"datasets={len(datasets)} points={point_count} "
        f"baseline={h226.objective(baseline)}"
    )
    for name in PROJECTIONS:
        values, profile, widths, changed = score(datasets, name)
        exact_profiles = sum(
            new == old
            for new_dataset, old_dataset in zip(profile, baseline_profile)
            for new, old in zip(new_dataset, old_dataset)
        )
        print(
            f"  {name}: objective={h226.objective(values)} "
            f"regressions={h226.regressions(values, baseline)} "
            f"changed-values={changed}/{point_count} "
            f"same-metric={exact_profiles}/{point_count}"
        )
        print(f"    pre-projection significant widths={dict(sorted(widths.items()))}")
        for (dataset, _), old, new in zip(datasets, baseline, values):
            if new != old:
                print(f"    {dataset}: {old} -> {new}")


if __name__ == "__main__":
    main()
