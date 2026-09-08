#!/usr/bin/env python3
"""Freeze fresh FCOS producer-class contexts from h1406/h1408 legs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


VARIANTS = (
    ("sub_zero", "exact_arithmetic_subtract"),
    ("mul_one", "exact_arithmetic_multiply"),
    ("div_one", "exact_arithmetic_divide"),
    ("chs_twice", "nonarithmetic_sign_roundtrip"),
    ("copy_pop", "nonarithmetic_register_copy"),
    ("fxch_roundtrip", "nonarithmetic_stack_exchange"),
    ("add_zero_store_reload", "arithmetic_then_m80_memory_roundtrip"),
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

    manifest = args.output_directory / "producer-class.tsv"
    inputs = args.output_directory / "producer-class-inputs.txt"
    freeze = args.output_directory / "FREEZE.json"
    for path in (manifest, inputs, freeze):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")

    legs = (
        unique_legs(args.frontier_manifest, "frontier")
        + unique_legs(args.control_manifest, "same_carry_control")
    )
    leg_keys = [(row["target_mode"], row["operand"]) for row in legs]
    if len(legs) != 19 or len(leg_keys) != len(set(leg_keys)):
        raise RuntimeError("expected 11 frontier plus 8 disjoint control legs")
    if sum(row["population"] == "frontier" for row in legs) != 11:
        raise RuntimeError("expected exactly 11 frontier legs")
    if sum(row["population"] == "same_carry_control" for row in legs) != 8:
        raise RuntimeError("expected exactly eight control legs")

    rows = []
    for leg in legs:
        for variant, producer_class in VARIANTS:
            rows.append({
                "case_id": f"C{len(rows) + 1:04d}",
                "instruction": "fcos",
                "target_mode": leg["target_mode"],
                "producer_mode": "rn",
                "producer_precision": "pc64",
                "producer": variant,
                "producer_class": producer_class,
                "population": leg["population"],
                "operand": leg["operand"],
                "expected_visible_producer_result": leg["operand"],
                "known_direct_hardware": leg["known_direct_hardware"],
                "current_model": leg["current_model"],
                "capture_state": "FROZEN_UNOPENED",
            })

    identities = [
        (row["instruction"], row["target_mode"], row["operand"], row["producer"])
        for row in rows
    ]
    if len(identities) != len(set(identities)):
        raise RuntimeError("duplicate producer-context identity")

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
        "schema": "fsincos-h1410-producer-class-v1",
        "capture_state": "FROZEN_UNOPENED",
        "hardware_execution": "none",
        "identity": "instruction+target_mode+operand+producer_sequence",
        "repeat_exclusions": [
            "direct_fldt",
            "add_zero",
            "add_plus_quarter",
            "add_minus_quarter",
        ],
        "rows": len(rows),
        "legs": len(legs),
        "frontier_legs": 11,
        "same_carry_control_legs": 8,
        "variants": [variant for variant, _ in VARIANTS],
        "one_observation_policy": "one execution per frozen producer context",
        "sources": {
            str(args.frontier_manifest): sha256(args.frontier_manifest),
            str(args.control_manifest): sha256(args.control_manifest),
        },
        "sha256": {
            "producer-class.tsv": sha256(manifest),
            "producer-class-inputs.txt": sha256(inputs),
            "harness": sha256(args.harness),
        },
    }
    with freeze.open("x") as target:
        json.dump(record, target, indent=2, sort_keys=True)
        target.write("\n")

    print(
        f"froze {len(rows)} fresh producer contexts over {len(legs)} legs "
        f"under {args.output_directory}",
        flush=True,
    )


if __name__ == "__main__":
    main()

