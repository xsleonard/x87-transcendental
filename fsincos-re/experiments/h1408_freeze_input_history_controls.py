#!/usr/bin/env python3
"""Freeze same-carry negative controls for the h1406 history effect."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from h1400_microcontrol_state_recurrence import read_rows, reconstruct
from h1406_freeze_input_history import VARIANTS


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("harness", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()
    manifest = args.output_directory / "input-history-controls.tsv"
    inputs = args.output_directory / "input-history-control-inputs.txt"
    freeze = args.output_directory / "FREEZE.json"
    for path in (manifest, inputs, freeze):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")

    source_rows = read_rows(args.features)
    _, _, _, joint = reconstruct(source_rows)
    groups = defaultdict(list)
    for row, carry in zip(source_rows, joint["carry"]):
        groups[row["branch"], carry].append(row)

    controls = []
    mixed_groups = 0
    for members in groups.values():
        positives = [row for row in members if row["label"] == "POS"]
        negatives = [row for row in members if row["label"] == "NEG"]
        if not positives or not negatives:
            continue
        mixed_groups += 1
        # Stable lexical choice, made without consulting any new hardware.
        selected = min(negatives, key=lambda row: (row["op"], row["mode"]))
        if selected["hw"] != selected["model"]:
            raise RuntimeError(f"negative control is not model-exact: {selected['op']}")
        controls.append((selected, len(positives), len(negatives)))
    if mixed_groups != 8 or len(controls) != 8:
        raise RuntimeError(
            f"expected eight mixed carry groups, got {mixed_groups}/{len(controls)}"
        )

    rows = []
    for source, positive_count, negative_count in controls:
        for variant, producer_relation in VARIANTS:
            rows.append({
                "case_id": f"C{len(rows) + 1:04d}",
                "instruction": "fcos",
                "target_mode": source["mode"],
                "producer_mode": "rn",
                "producer_precision": "pc64",
                "producer": variant,
                "producer_relation": producer_relation,
                "operand": source["op"],
                "expected_visible_producer_result": source["op"],
                "known_direct_hardware": source["hw"],
                "current_model": source["model"],
                "branch": source["branch"],
                "mixed_group_positive_rows": str(positive_count),
                "mixed_group_negative_rows": str(negative_count),
                "selection": "lexical_first_negative_in_exact_carry_collision_group",
                "capture_state": "FROZEN_UNOPENED",
            })
    identities = [
        (row["instruction"], row["target_mode"], row["operand"], row["producer"])
        for row in rows
    ]
    if len(identities) != len(set(identities)):
        raise RuntimeError("duplicate control history identity")

    args.output_directory.mkdir(parents=True, exist_ok=True)
    with manifest.open("x", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=tuple(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    with inputs.open("x") as target:
        target.write("# case mode variant se sig\n")
        for row in rows:
            se, sig = row["operand"].split()
            target.write(
                f"{row['case_id']} {row['target_mode']} {row['producer']} "
                f"{se} {sig}\n"
            )

    record = {
        "schema": "fsincos-h1408-input-history-controls-v1",
        "capture_state": "FROZEN_UNOPENED",
        "hardware_execution": "none",
        "identity": "instruction+target_mode+operand+producer",
        "selection": "one_cached_model_exact_negative_from_each_exact_carry_stream_collision_group",
        "direct_load_baseline_policy": "not_recaptured_use_cached_feature_label",
        "producer": "PC64_RN_FADD_to_same_visible_80_bit_operand",
        "rows": len(rows),
        "controls": len(controls),
        "mixed_carry_groups": mixed_groups,
        "one_observation_policy": "one execution per frozen history-context identity",
        "source": {"path": str(args.features), "sha256": sha256(args.features)},
        "sha256": {
            "input-history-controls.tsv": sha256(manifest),
            "input-history-control-inputs.txt": sha256(inputs),
            "harness": sha256(args.harness),
        },
    }
    with freeze.open("x") as target:
        json.dump(record, target, indent=2, sort_keys=True)
        target.write("\n")
    print(
        f"froze {len(rows)} contexts over {len(controls)} exact-carry controls",
        flush=True,
    )


if __name__ == "__main__":
    main()
