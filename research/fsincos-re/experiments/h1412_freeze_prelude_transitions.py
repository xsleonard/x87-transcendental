#!/usr/bin/env python3
"""Freeze the h1412 FCOS prelude-transition discriminator matrix."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


VARIANTS = (
    ("init_load", "minimal_after_fninit"),
    ("init_clex_load", "fnclex_before_load"),
    ("init_load_clex", "fnclex_after_load"),
    ("init_load_nop", "integer_nop_after_load"),
    ("init_load_lfence", "lfence_after_load"),
    ("init_load_fwait", "fwait_after_load"),
    ("init_load_status", "fnstsw_after_load"),
    ("init_load_cw", "same_fldcw_after_load"),
    ("init_load_wait_status_cw", "h1406_common_status_control_prelude"),
    ("init_load_fxam", "read_only_x87_fxam_after_load"),
    ("init_fchs2_nostatus", "value_roundtrip_without_status_read"),
    ("init_add0_nostatus", "exact_fadd_without_status_read"),
    (
        "init_add0_store_reload_nostatus",
        "exact_fadd_memory_roundtrip_without_status_read",
    ),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def unique_legs(path: Path, population: str) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        source_rows = list(csv.DictReader(source, delimiter="\t"))
    required = {
        "target_mode", "operand", "known_direct_hardware", "current_model",
    }
    if not source_rows or not required.issubset(source_rows[0]):
        raise RuntimeError(f"{path}: incompatible source manifest")
    result = []
    seen = set()
    for row in source_rows:
        key = row["target_mode"].lower(), row["operand"].lower()
        if key in seen:
            continue
        seen.add(key)
        result.append({
            "population": population,
            "target_mode": key[0],
            "operand": key[1],
            "known_direct_hardware": row["known_direct_hardware"].lower(),
            "current_model": row["current_model"].lower(),
        })
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("frontier_manifest", type=Path)
    parser.add_argument("control_manifest", type=Path)
    parser.add_argument("harness", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()

    manifest = args.output_directory / "prelude-transitions.tsv"
    inputs = args.output_directory / "prelude-transition-inputs.txt"
    freeze = args.output_directory / "FREEZE.json"
    for path in (manifest, inputs, freeze):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")

    legs = (
        unique_legs(args.frontier_manifest, "frontier")
        + unique_legs(args.control_manifest, "same_carry_control")
    )
    keys = [(row["target_mode"], row["operand"]) for row in legs]
    if len(legs) != 19 or len(keys) != len(set(keys)):
        raise RuntimeError("expected 11 frontier plus 8 disjoint control legs")

    rows = []
    for leg in legs:
        for variant, transition_class in VARIANTS:
            rows.append({
                "case_id": f"D{len(rows) + 1:04d}",
                "instruction": "fcos",
                "target_mode": leg["target_mode"],
                "prelude": variant,
                "transition_class": transition_class,
                "population": leg["population"],
                "operand": leg["operand"],
                "known_direct_hardware": leg["known_direct_hardware"],
                "current_model": leg["current_model"],
                "capture_state": "FROZEN_UNOPENED",
            })

    identities = [
        (row["instruction"], row["target_mode"], row["operand"], row["prelude"])
        for row in rows
    ]
    if len(identities) != len(set(identities)):
        raise RuntimeError("duplicate prelude-context identity")

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
                f"{row['case_id']} {row['target_mode']} {row['prelude']} "
                f"{se} {sig}\n"
            )

    record = {
        "schema": "fsincos-h1412-prelude-transitions-v1",
        "capture_state": "FROZEN_UNOPENED",
        "hardware_execution": "none",
        "identity": "instruction+target_mode+operand+complete_prelude_sequence",
        "rows": len(rows),
        "legs": len(legs),
        "frontier_legs": 11,
        "same_carry_control_legs": 8,
        "variants": [variant for variant, _ in VARIANTS],
        "one_observation_policy": "one execution per frozen prelude context",
        "repeat_exclusions": "all direct-batch and h1406/h1410 sequences",
        "sources": {
            str(args.frontier_manifest): sha256(args.frontier_manifest),
            str(args.control_manifest): sha256(args.control_manifest),
        },
        "sha256": {
            "prelude-transitions.tsv": sha256(manifest),
            "prelude-transition-inputs.txt": sha256(inputs),
            "harness": sha256(args.harness),
        },
    }
    with freeze.open("x") as target:
        json.dump(record, target, indent=2, sort_keys=True)
        target.write("\n")
    print(
        f"froze {len(rows)} fresh prelude contexts over {len(legs)} legs "
        f"under {args.output_directory}",
        flush=True,
    )


if __name__ == "__main__":
    main()

