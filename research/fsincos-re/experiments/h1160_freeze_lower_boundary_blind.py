#!/usr/bin/env python3
"""Freeze a disjoint, boundary-focused blind for the h1158 recurrence.

Only software models are evaluated here.  For each occupied discrete digit
cell, the closest unseen operands on both sides of the predicted integer-M
boundary are retained.  A mode leg is emitted only when the h1158 choice and
its physical one-unit counterfactual produce different architectural output.
The resulting manifest therefore freezes the exact candidate prediction
before any hardware label is read.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

from h1135_freeze_lower_binade import MODES, read_ties, run_model
from h1137_lower_binade_features import add_derived, dump_records


ONE = 1 << 66
CELL = ("theta", "ce", "s4", "side", "low3", "dist", "rsh", "b1", "b2")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def excluded_operands(paths: list[Path]) -> set[str]:
    result = set()
    for path in paths:
        with path.open(newline="") as source:
            reader = csv.DictReader(source, delimiter="\t")
            if reader.fieldnames is None or "op" not in reader.fieldnames:
                raise SystemExit(f"exclude manifest has no op column: {path}")
            result.update(row["op"].lower() for row in reader)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("ties", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("base", type=Path)
    parser.add_argument("force_minus1", type=Path)
    parser.add_argument("force_zero", type=Path)
    parser.add_argument("force_plus1", type=Path)
    parser.add_argument("output_prefix", type=Path)
    parser.add_argument("--exclude-manifest", action="append", default=[],
                        type=Path)
    parser.add_argument("--per-side", type=int, default=4)
    args = parser.parse_args()

    manifest_path = args.output_prefix.with_name(
        args.output_prefix.name + "_manifest.tsv")
    op_paths = {
        mode: args.output_prefix.with_name(
            args.output_prefix.name + f"_{mode}_ops.txt")
        for mode in MODES
    }
    for path in (manifest_path, *op_paths.values()):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")

    excluded = excluded_operands(args.exclude_manifest)
    ties = [row for row in read_ties(args.ties) if row["op"] not in excluded]
    if not ties:
        raise SystemExit("no unseen ties")
    records = dump_records(args.candidate, [row["op"] for row in ties])
    groups = defaultdict(lambda: {"below": [], "at_or_above": []})
    candidates = []
    for tie in ties:
        record = records[tie["op"]]
        add_derived(record)
        if record.get("branch") != "r1158":
            continue
        threshold = int(record["br_threshold"])
        mreg = int(record["mreg_signed"])
        margin = mreg - threshold * ONE
        key = tuple(int(record[field]) for field in CELL)
        item = {
            **tie,
            **{field: record[field] for field in CELL},
            "mreg_signed": str(mreg),
            "threshold": str(threshold),
            "margin": str(margin),
            "boundary_side": "below" if margin < 0 else "at_or_above",
            "candidate_fire": record["br_fire"],
            "candidate_delta": record["br_delta"],
            "cell": "/".join(map(str, key)),
        }
        groups[key][item["boundary_side"]].append(item)
        candidates.append(item)

    selected_by_op = {}
    cell_sides = Counter()
    for key, sides in groups.items():
        for side, items in sides.items():
            items.sort(key=lambda row: (abs(int(row["margin"])), row["op"]))
            for rank, item in enumerate(items[:args.per_side], 1):
                copy = dict(item)
                copy["boundary_rank"] = str(rank)
                selected_by_op[copy["op"]] = copy
                cell_sides[(side, key)] += 1
    selected = [selected_by_op[op] for op in sorted(selected_by_op)]
    if not selected:
        raise SystemExit("no boundary rows selected")

    model_paths = {
        "candidate": args.candidate,
        "base": args.base,
        "force_minus1": args.force_minus1,
        "force_zero": args.force_zero,
        "force_plus1": args.force_plus1,
    }
    predictions = {
        mode: {
            name: run_model(path, mode, selected)
            for name, path in model_paths.items()
        }
        for mode in MODES
    }
    output = []
    mode_counts = Counter()
    for mode in MODES:
        for index, row in enumerate(selected):
            values = {name: predictions[mode][name][index]
                      for name in model_paths}
            theta = int(row["theta"])
            fire = int(row["candidate_fire"])
            fire_name = "force_plus1" if theta < 0 else "force_minus1"
            physical_name = fire_name if fire else "force_zero"
            counter_name = "force_zero" if fire else fire_name
            if values["candidate"] != values[physical_name]:
                raise RuntimeError(
                    f"candidate/physical disagreement {mode} {row['op']}")
            if values["candidate"] == values[counter_name]:
                continue
            output.append({
                "insn": "cos",
                "mode": mode,
                **row,
                **values,
                "physical_choice": physical_name,
                "counterfactual": values[counter_name],
                "counterfactual_choice": counter_name,
            })
            mode_counts[mode] += 1
    if not output:
        raise SystemExit("no endpoint-visible legs")

    columns = (
        "insn", "mode", "op", "cell", "boundary_side", "boundary_rank",
        "mreg_signed", "threshold", "margin", "candidate_fire",
        "candidate_delta", "physical_choice", "counterfactual_choice",
        "candidate", "counterfactual", "base", "force_minus1",
        "force_zero", "force_plus1", "sig", "dist", "low3", "k", "rud",
        "t4hi12", "rdhi12", "terminal_r", "corr_e", "theta", "ce", "s4",
        "side", "rsh", "b1", "b2",
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", newline="") as target:
        writer = csv.DictWriter(target, columns, delimiter="\t",
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(output)
    for mode, path in op_paths.items():
        with path.open("w") as target:
            for row in output:
                if row["mode"] == mode:
                    target.write(row["op"] + "\n")

    print(f"ties_sha256={digest(args.ties)} ties={len(ties)} excluded={len(excluded)}")
    for name, path in model_paths.items():
        print(f"{name}_sha256={digest(path)}")
    print(f"candidate_rows={len(candidates)} occupied_cells={len(groups)}")
    print(f"selected_operands={len(selected)} manifest_legs={len(output)}")
    print(f"mode_counts={dict(mode_counts)}")
    print(f"selected_cell_sides={len(cell_sides)}")
    print(f"manifest_sha256={digest(manifest_path)}")
    for mode, path in op_paths.items():
        print(f"{mode}_ops_sha256={digest(path)} rows={mode_counts[mode]}")


if __name__ == "__main__":
    main()
