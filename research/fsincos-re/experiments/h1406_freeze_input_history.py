#!/usr/bin/env python3
"""Freeze one-shot FCOS input-history discriminators for the 11-row frontier."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


VARIANTS = (
    ("add_zero", "exact"),
    ("add_plus_quarter", "rounded_down_to_visible_operand"),
    ("add_minus_quarter", "rounded_up_to_visible_operand"),
)


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def read_frontier(path: Path) -> list[dict[str, str]]:
    rows = []
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        fields = line.split()
        if len(fields) != 12 or fields[1] != "cos" or fields[6] != "OK" \
                or fields[9] != "OK":
            raise RuntimeError(f"{path}:{line_number}: unexpected row")
        rows.append({
            "corpus": fields[0],
            "mode": fields[2],
            "index": fields[3],
            "operand": f"{fields[4].lower()} {fields[5].lower()}",
            # Suite miss rows are emitted as operand, model, hardware.
            # h1400_causal_stage_localization.py uses the same field contract.
            "known_direct_hardware": f"{fields[10].lower()}:{fields[11].lower()}",
            "current_model": f"{fields[7].lower()}:{fields[8].lower()}",
        })
    keys = [(row["mode"], row["operand"]) for row in rows]
    if len(rows) != 11 or len(keys) != len(set(keys)):
        raise RuntimeError("expected exactly 11 unique mode/operand frontier rows")
    if len({row["operand"] for row in rows}) != 10:
        raise RuntimeError("expected ten frontier operands")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("frontier", type=Path)
    parser.add_argument("harness", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()
    manifest = args.output_directory / "input-history.tsv"
    inputs = args.output_directory / "input-history-inputs.txt"
    freeze = args.output_directory / "FREEZE.json"
    for path in (manifest, inputs, freeze):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")

    frontier = read_frontier(args.frontier)
    rows = []
    for source in frontier:
        for variant, producer_relation in VARIANTS:
            rows.append({
                "case_id": f"P{len(rows) + 1:04d}",
                "instruction": "fcos",
                "target_mode": source["mode"],
                "producer_mode": "rn",
                "producer_precision": "pc64",
                "producer": variant,
                "producer_relation": producer_relation,
                "operand": source["operand"],
                "expected_visible_producer_result": source["operand"],
                "known_direct_hardware": source["known_direct_hardware"],
                "current_model": source["current_model"],
                "source_corpus": source["corpus"],
                "source_index": source["index"],
                "capture_state": "FROZEN_UNOPENED",
            })
    identities = [
        (row["instruction"], row["target_mode"], row["operand"], row["producer"])
        for row in rows
    ]
    if len(identities) != len(set(identities)):
        raise RuntimeError("duplicate history-context identity")

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
        "schema": "fsincos-h1406-input-history-v1",
        "capture_state": "FROZEN_UNOPENED",
        "hardware_execution": "none",
        "identity": "instruction+target_mode+operand+producer",
        "direct_load_baseline_policy": "not_recaptured_use_frozen_source_label",
        "producer": "PC64_RN_FADD_to_same_visible_80_bit_operand",
        "rows": len(rows),
        "frontier_rows": len(frontier),
        "frontier_operands": len({row["operand"] for row in frontier}),
        "one_observation_policy": "one execution per frozen history-context identity",
        "source": {
            "path": str(args.frontier),
            "sha256": sha256(args.frontier),
        },
        "sha256": {
            "input-history.tsv": sha256(manifest),
            "input-history-inputs.txt": sha256(inputs),
            "harness": sha256(args.harness),
        },
    }
    with freeze.open("x") as target:
        json.dump(record, target, indent=2, sort_keys=True)
        target.write("\n")
    print(
        f"froze {len(rows)} contexts from {len(frontier)} frontier rows "
        f"under {args.output_directory}",
        flush=True,
    )


if __name__ == "__main__":
    main()
