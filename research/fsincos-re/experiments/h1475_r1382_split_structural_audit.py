#!/usr/bin/env python3
"""Audit named structural wires against the H1472 8/8 hardware split.

H1472 falsifies the s4-only R1382 refinement: among sixteen exact s4=66
endpoint separators, silicon retains the incumbent hard-3x merge eight times
and suppresses it eight times.  This script reconstructs the current internal
rows without executing x87, adds the two independently established anchors
(d0d0 suppresses the merge and d800 retains it), and exhausts literals plus
AND/OR/XOR pairs over the already-defined terminal, multiplier-tree, and P5
carry-select feature families.

An exact expression here is a hypothesis generator, not a validated selector.
The labels selected the expression, so any survivor must face a fresh frozen
disagreement bank before it can change emulator behavior.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from h1210_stagea_residual_reframe import parse_dump, run
from h1398_branch_two_wire_gate import named_features, search_truth


ANCHORS = (
    ("d0d0", "rd", "3ffc d0d000000cc0b3f8", 0),
    ("d800", "ru", "3ffc d80000000b15da62", 1),
)
MODES = ("rn", "rd", "ru")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def hardware_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    if len(rows) != 16:
        raise RuntimeError(f"expected 16 H1472 rows, got {len(rows)}")
    if {row["endpoint"] for row in rows} != {"incumbent", "r1382"}:
        raise RuntimeError("H1472 endpoint alphabet changed")
    if sum(row["endpoint"] == "incumbent" for row in rows) != 8:
        raise RuntimeError("H1472 is not the frozen 8/8 split")
    if any(row["actual_merge_gate"] != "1" for row in rows):
        raise RuntimeError("H1472 contains a row outside the exact merge gate")
    return rows


def replay_h1472(model: Path, rows: list[dict[str, str]]):
    records = []
    for mode in MODES:
        selected = [row for row in rows if row["mode"] == mode]
        operands = [row["operand"].lower() for row in selected]
        _, stderr = run(model, mode, operands, dump=True)
        dumps = parse_dump(stderr, operands)
        for source, dump in zip(selected, dumps):
            if dump["s4"] != "66" or dump["theta"] != "0" \
                    or dump["low3"] != "3":
                raise RuntimeError(
                    f"{source['case_id']}: no longer in R1382 parent state"
                )
            records.append({
                "name": source["case_id"],
                "operand": source["operand"],
                "mode": mode,
                "merge": int(source["endpoint"] == "incumbent"),
                "provenance": "h1472_one_shot_hardware",
                "row": dump,
            })
    return records


def replay_anchors(model: Path):
    records = []
    for name, mode, operand, merge in ANCHORS:
        _, stderr = run(model, mode, [operand], dump=True)
        dump = parse_dump(stderr, [operand])[0]
        if dump["theta"] != "0" or dump["low3"] != "3":
            raise RuntimeError(f"{name}: anchor left the hard-3x parent state")
        records.append({
            "name": name,
            "operand": operand,
            "mode": mode,
            "merge": merge,
            "provenance": "previously_established_hardware_anchor",
            "row": dump,
        })
    return records


def encode_gate(item: tuple) -> dict[str, object]:
    (
        placement, separation, complements, expression_length,
        lexical_gate, gate, left, right, left_equivalents, right_equivalents,
    ) = item
    if lexical_gate != gate:
        raise AssertionError("gate ranking tuple changed")
    return {
        "placement_rank": placement,
        "column_separation": separation,
        "complements": complements,
        "expression_length": expression_length,
        "gate": gate,
        "left": left,
        "right": right,
        "left_equivalent_names": left_equivalents,
        "right_equivalent_names": right_equivalents,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("h1472_score", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    rows = hardware_rows(args.h1472_score)
    records = replay_h1472(args.model, rows) + replay_anchors(args.model)
    columns: dict[str, int] = defaultdict(int)
    truth = 0
    schema = None
    per_row = []
    for index, record in enumerate(records):
        features = named_features(record["row"])
        if schema is None:
            schema = set(features)
        elif set(features) != schema:
            raise RuntimeError("named feature schema changed")
        for name, value in features.items():
            columns[name] |= int(bool(value)) << index
        truth |= int(record["merge"]) << index
        per_row.append({
            key: record[key]
            for key in ("name", "operand", "mode", "merge", "provenance")
        })
    if schema is None:
        raise RuntimeError("empty structural feature schema")

    all_mask = (1 << len(records)) - 1
    exact_literals = []
    literals: dict[int, list[str]] = defaultdict(list)
    for name, pattern in columns.items():
        literals[pattern].append(name)
        literals[pattern ^ all_mask].append("!" + name)
        if pattern == truth:
            exact_literals.append(name)
        if (pattern ^ all_mask) == truth:
            exact_literals.append("!" + name)
    exact_gates = search_truth(truth, all_mask, literals)
    encoded_gates = [encode_gate(item) for item in exact_gates]

    expected_lead = {
        "gate": "xor",
        "left": "product.R.l1_4.sum.+0",
        "right": "product.R.l2_1.carry.-3",
    }
    if not encoded_gates or any(
        encoded_gates[0][key] != value for key, value in expected_lead.items()
    ):
        raise RuntimeError(f"leading structural coincidence changed: {encoded_gates[:1]}")

    report = {
        "experiment": "h1475_r1382_split_structural_audit",
        "status": "HYPOTHESIS_GENERATION_ONLY",
        "hardware_policy": "cached_h1472_and_prior_anchor_labels_no_x87_execution",
        "rows": len(records),
        "h1472_rows": len(rows),
        "anchor_rows": len(ANCHORS),
        "merge_ones": truth.bit_count(),
        "named_features": len(columns),
        "literal_patterns_with_complements": len(literals),
        "exact_literals": sorted(exact_literals),
        "exact_two_wire_gates": len(encoded_gates),
        "leading_hypothesis": encoded_gates[0],
        "all_exact_two_wire_gates": encoded_gates,
        "labeled_rows": per_row,
        "claim_boundary": (
            "Every exact gate was selected using these eighteen labels. "
            "None is a validated selector; a fresh frozen disagreement bank "
            "is mandatory before any source promotion."
        ),
        "emulator_change": "none",
        "paper_change": "none",
        "sha256": {
            "model": digest(args.model),
            "h1472_score": digest(args.h1472_score),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps({
        "output": str(args.output),
        "rows": len(records),
        "features": len(columns),
        "exact_literals": len(exact_literals),
        "exact_two_wire_gates": len(encoded_gates),
        "leading_hypothesis": encoded_gates[0],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
