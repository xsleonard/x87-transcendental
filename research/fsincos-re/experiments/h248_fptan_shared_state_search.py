#!/usr/bin/env python3
"""Use FPTAN to constrain the shared P6 table-state producer."""

from __future__ import annotations

import dataclasses

import h218_fadd_residual_programs as h218
import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230
import h245_fptan_shared_state as h245
import h246_fptan_operation_search as h246


RECONSTRUCTION = h246.Candidate("away67", "chop67")


def expand(candidate: h230.Candidate):
    result = {candidate}
    for field in h230.FIELDS:
        for action in h230.ACTIONS:
            result.add(dataclasses.replace(candidate, **{field: action}))
    for bias in h230.BIAS_ACTIONS:
        result.add(dataclasses.replace(candidate, sine_bias=bias))
    return result


def fsincos_score(points, candidate):
    total = h226.ZERO_JOINT
    for point in points:
        total = h226.add_metric(
            total,
            h226.metric_for(point, h230.hidden_values(point, candidate)),
        )
    return total


def no_worse(value, baseline):
    return all(
        all(new <= old for new, old in zip(lane, old_lane))
        for lane, old_lane in zip(value, baseline)
    )


def main() -> None:
    datasets = []
    for name in ("dense", "sweep"):
        hardware = h245.captures(name)
        points = h228.points(name)
        selected = h246.sample(points, hardware, 2400)
        datasets.append((name, points, selected, hardware))

    ranked = []
    for candidate in expand(h228.CANDIDATE):
        results = tuple(
            h246.score(
                selected, hardware, RECONSTRUCTION, candidate
            )
            for _, _, selected, hardware in datasets
        )
        objective = tuple(
            sum(value[i] for value in results) for i in (0, 2, 1)
        )
        ranked.append((objective, candidate.short(), candidate, results))
    ranked.sort()
    print(f"single-coordinate candidates={len(ranked)}")
    for item in ranked[:16]:
        print(f"  selected {item[0]} {item[1]} {item[3]}")

    baselines = {
        name: fsincos_score(points, h228.CANDIDATE)
        for name, points, _, _ in datasets
    }
    complete = []
    for _, _, candidate, _ in ranked[:16]:
        fptan = tuple(
            h246.score(points, hardware, RECONSTRUCTION, candidate)
            for _, points, _, hardware in datasets
        )
        fsincos = tuple(
            fsincos_score(points, candidate)
            for _, points, _, _ in datasets
        )
        gate = all(
            no_worse(value, baselines[name])
            for (name, _, _, _), value in zip(datasets, fsincos)
        )
        objective = tuple(
            sum(value[i] for value in fptan) for i in (0, 2, 1)
        )
        complete.append(
            (not gate, objective, candidate.short(), fptan, fsincos)
        )
    print("complete leaders (gate false sorts first):")
    for item in sorted(complete):
        print(f"  {item}")


if __name__ == "__main__":
    main()
