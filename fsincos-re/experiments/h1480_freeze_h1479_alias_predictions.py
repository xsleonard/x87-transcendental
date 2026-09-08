#!/usr/bin/env python3
"""Freeze H1479 alternate-representation predictions for H1477.

The H1477 operands were frozen before the H1479 topology audit.  This script
does not alter that capture manifest.  It evaluates the eleven label-only
single-signal aliases found by H1479 on the already-frozen operands and stores
their prediction classes before any H1477 hardware label is opened.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from h1210_stagea_residual_reframe import parse_dump, run
from h1400_p5_representation_audit import tree_variants
from h1479_r1475_topology_isomorphism import (
    normalized_operand,
    tree_features,
)


MODES = ("rn", "rd", "ru")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("h1476_bank", type=Path)
    parser.add_argument("h1477_manifest", type=Path)
    parser.add_argument("h1479_report", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    bank = json.loads(args.h1476_bank.read_text())
    selected = {
        normalized_operand(row["operand"]): row for row in bank["selected"]
    }
    with args.h1477_manifest.open(newline="") as source:
        manifest = list(csv.DictReader(source, delimiter="\t"))
    if len(manifest) != 10 or len(selected) != 10:
        raise RuntimeError("H1477/H1476 selected row count changed")
    if [row["case_id"] for row in manifest] != [f"X{i:03d}" for i in range(1, 11)]:
        raise RuntimeError("H1477 case order changed")
    if {row["operand"] for row in manifest} != set(selected):
        raise RuntimeError("H1477 operands differ from H1476 selection")

    dumps = {}
    for mode in MODES:
        mode_rows = [row for row in manifest if row["mode"] == mode]
        operands = [row["operand"] for row in mode_rows]
        _, stderr = run(args.model, mode, operands, dump=True)
        for row, dump in zip(mode_rows, parse_dump(stderr, operands)):
            dumps[row["case_id"]] = dump
    if len(dumps) != len(manifest):
        raise RuntimeError("diagnostic replay row count changed")

    h1479 = json.loads(args.h1479_report.read_text())
    aliases = h1479["alternate_single_signal_search"]["label_only_alias_details"]
    if len(aliases) != 11:
        raise RuntimeError("H1479 alternate alias census changed")
    layouts = {name: config for name, _, config in tree_variants()}
    feature_cache = {
        (row["case_id"], layout): tree_features(dumps[row["case_id"]], config)
        for layout, config in layouts.items()
        for row in manifest
    }

    classes: dict[str, list[str]] = defaultdict(list)
    for alias in aliases:
        full_name = alias["signal"]
        complemented = full_name.startswith("!")
        bare = full_name[1:] if complemented else full_name
        layout = next(
            (name for name in layouts if bare.startswith(name + ".")), None)
        if layout is None:
            raise RuntimeError(f"cannot parse H1479 alias {full_name}")
        feature = bare[len(layout) + 1:]
        pattern = "".join(str(
            feature_cache[row["case_id"], layout][feature]
            ^ int(complemented)
        ) for row in manifest)
        classes[pattern].append(full_name)

    r1475_pattern = "".join(row["r1475_merge"] for row in manifest)
    if r1475_pattern != "".join(
            str(selected[row["operand"]]["leading_merge"]) for row in manifest):
        raise RuntimeError("H1477 and H1476 R1475 predictions differ")
    if r1475_pattern in classes:
        raise RuntimeError("H1477 does not separate R1475 from an H1479 alias")
    if len(classes) != 5 or sorted(map(len, classes.values())) != [1, 2, 2, 2, 4]:
        raise RuntimeError("H1479 alias partition on H1477 changed")

    report = {
        "experiment": "h1480_freeze_h1479_alias_predictions",
        "status": "FROZEN_PREDICTIONS_H1477_UNOPENED",
        "hardware_execution": "none",
        "hardware_labels": "none",
        "manifest_unchanged": True,
        "rows": len(manifest),
        "case_order": [row["case_id"] for row in manifest],
        "r1475_pattern": r1475_pattern,
        "alternate_aliases": len(aliases),
        "alternate_prediction_classes": len(classes),
        "r1475_separated_from_all_alternate_classes": True,
        "classes": [
            {"pattern": pattern, "signals": sorted(signals)}
            for pattern, signals in sorted(classes.items())
        ],
        "claim_boundary": (
            "These are pre-label software predictions on the existing frozen "
            "H1477 tuples. They do not validate any selector."
        ),
        "paper_change": "none",
        "emulator_change": "none",
        "sha256": {
            "model": digest(args.model),
            "h1476_bank": digest(args.h1476_bank),
            "h1477_manifest": digest(args.h1477_manifest),
            "h1479_report": digest(args.h1479_report),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps({
        "output": str(args.output),
        "rows": len(manifest),
        "r1475_pattern": r1475_pattern,
        "alternate_aliases": len(aliases),
        "alternate_classes": len(classes),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
