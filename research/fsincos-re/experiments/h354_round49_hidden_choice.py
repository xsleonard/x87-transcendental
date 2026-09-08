#!/usr/bin/env python3
"""Infer result-compatible hidden-unit choices for h349 residual inputs."""

from __future__ import annotations

import argparse
import collections
import pathlib

import h58_constraint_search as h58
import h230_p6_microop_materialization_search as h230
import h286_ingest_trig_sine_bias_capture as h286
import h337_round49_causal_localization as h337
import h353_round49_broad_residuals as h353


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_CAPTURE = ROOT / "capture-kit-captures" / "skylake-trig-h349"
DELTAS = tuple(range(-8, 9))


def hardware(capture: pathlib.Path, indexes):
    selected = set(indexes)
    result = {}
    for rc in h58.RCS:
        path = capture / f"fsincos_{rc}_status.txt"
        with path.open() as stream:
            for index, line in enumerate(stream):
                if index not in selected:
                    continue
                record = h286.parse_pair(line)
                result[index, rc] = record[:2]
    if len(result) != len(selected) * len(h58.RCS):
        raise SystemExit("h354 did not recover every selected hardware row")
    return result


def compatible(point, lane: int, node: str, delta: int, outputs):
    value = h337.hidden_values(point, node, delta)[lane]
    return all(
        h58.x87_round(value, rc) == outputs[rc]
        for rc in h58.RCS
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", type=pathlib.Path, default=DEFAULT_CAPTURE)
    args = parser.parse_args()

    residuals = h353.load(args.capture / "residuals.tsv")
    by_lane = {}
    for record in residuals:
        by_lane.setdefault(
            (record.index, record.lane), record
        )
    captured = hardware(
        args.capture, {index for index, _ in by_lane}
    )
    counts = collections.Counter()
    feature_labels = collections.defaultdict(collections.Counter)
    for item_index, ((index, lane_name), record) in enumerate(sorted(by_lane.items())):
        point = h353.point_from_input(record)
        lane = int(lane_name == "cos")
        outputs = {
            rc: captured[index, rc][lane]
            for rc in h58.RCS
        }
        allowed = {}
        for node in h337.NODES:
            allowed[node] = tuple(
                delta
                for delta in DELTAS
                if compatible(point, lane, node, delta, outputs)
            )
            counts[node, allowed[node]] += 1
        p_allowed = allowed["p_product"]
        canonical = (
            min(p_allowed, key=lambda value: (abs(value), value))
            if p_allowed else None
        )
        counts["canonical-p", canonical] += 1
        values = h353.geometry(point, record)
        for name in (
            "source/family", "cell", "quadrant", "producer", "coordinate",
            "proxy", "span", "cross-low3", "lead-low3", "q-low3",
            "fadd-rem-sign",
        ):
            feature_labels[name, values[name]][canonical] += 1
        if item_index % 256 == 0:
            h230.state.cache_clear()

    print(
        f"h354 hidden choice: affected-lanes={len(by_lane)} "
        f"affected-inputs={len({index for index, _ in by_lane})}"
    )
    for node in h337.NODES:
        selected = {
            key[1]: value
            for key, value in counts.items()
            if key[0] == node
        }
        print(f"  {node}: {dict(sorted(selected.items(), key=lambda item: str(item[0])))}")
    canonical = {
        key[1]: value
        for key, value in counts.items()
        if key[0] == "canonical-p"
    }
    print(f"  canonical-p: {dict(sorted(canonical.items(), key=lambda item: str(item[0])))}")
    print("  feature/choice cross-tabs:")
    for (name, value), distribution in sorted(
        feature_labels.items(), key=lambda item: (item[0][0], str(item[0][1]))
    ):
        print(
            f"    {name}={value}: "
            f"{dict(sorted(distribution.items(), key=lambda item: str(item[0])))}"
        )


if __name__ == "__main__":
    main()
