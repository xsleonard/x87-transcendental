#!/usr/bin/env python3
"""Cross-validate fractional Round-44 carrier offsets on every partition."""

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
import h297_trig_sine_bias_residual_selector as h297


COORDINATES = ((-5, 13), (-6, 15))
NUMERATORS = tuple(range(9, 33))
BASELINE_NUMERATOR = 24
DENOMINATOR_BITS = 8


@functools.lru_cache(maxsize=None)
def coordinate(point):
    if point.prepared.joint.observed.family != "wide":
        return None
    values = h283.features(point)
    return values["a.top-exponent"], values["align.difference"]


@functools.lru_cache(maxsize=None)
def rn64_state(point):
    return h283.state_inputs(point)[-1]


def hidden_values(point, numerators):
    coord = coordinate(point)
    numerator = numerators.get(coord)
    if numerator is None:
        return h230.hidden_values(point, h228.CANDIDATE)
    sine = h79.bias_toward_zero(
        rn64_state(point), numerator, DENOMINATOR_BITS
    )
    return h291.hidden_values(point, sine)


def main() -> None:
    h292 = h297.h292_points()
    datasets = [
        *h218.datasets(),
        ("h285", h287.fresh_points()),
        ("h292-train", h292[::2]),
        ("h292-held", h292[1::2]),
    ]
    baseline_map = {coord: BASELINE_NUMERATOR for coord in COORDINATES}
    baseline_values = []
    records = {coord: [] for coord in COORDINATES}
    for dataset_index, (_, points) in enumerate(datasets):
        total = h226.ZERO_JOINT
        for point in points:
            metric = h226.metric_for(
                point, hidden_values(point, baseline_map)
            )
            total = h226.add_metric(total, metric)
            coord = coordinate(point)
            if coord in records:
                records[coord].append((dataset_index, point, metric))
        baseline_values.append(total)
    baseline = tuple(baseline_values)
    print(
        "h300 fractional cross-validation: "
        f"datasets={len(datasets)} baseline={h226.objective(baseline)}"
    )
    for coord in COORDINATES:
        ranked = []
        for numerator in NUMERATORS:
            candidate_map = dict(baseline_map)
            candidate_map[coord] = numerator
            candidate_values = list(baseline)
            for dataset_index, point, old_metric in records[coord]:
                new_metric = h226.metric_for(
                    point, hidden_values(point, candidate_map)
                )
                candidate_values[dataset_index] = h283.add_delta(
                    candidate_values[dataset_index],
                    h283.subtract_metric(new_metric, old_metric),
                )
            candidate = tuple(candidate_values)
            ranked.append(
                (
                    h226.regressions(candidate, baseline),
                    h226.objective(candidate),
                    numerator,
                    candidate,
                )
            )
        ranked.sort()
        print(f"coordinate={coord} regression leaders:")
        for regressions, objective, numerator, candidate in ranked[:16]:
            changed = [
                (name, old, new)
                for (name, _), old, new in zip(datasets, baseline, candidate)
                if old != new
            ]
            print(
                f"  bias={numerator}/256 objective={objective} "
                f"regressions={regressions} changed={changed}"
            )


if __name__ == "__main__":
    main()
