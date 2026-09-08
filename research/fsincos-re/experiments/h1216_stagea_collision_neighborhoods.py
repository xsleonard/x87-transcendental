#!/usr/bin/env python3
"""Extract exact-state neighborhoods around the stage-A carry flips.

The dense target-cell bank is too large for the expensive Booth/CSA feature
families.  This pass keeps only constraining rows sharing both the complete
R59 digit cell and the fixed twelve-operation rounding-class tuple with one
of the ten observed carry flips.  Selection is structural; labels are used
only to identify which occupied state neighborhoods must be retained.
"""

from __future__ import annotations

import argparse
import csv
import gzip
from pathlib import Path

from h1178_round_history_state_audit import CELL, row_states


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("selected", type=Path)
    parser.add_argument("labels", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    target_groups = set()
    target_operands = set()
    with gzip.open(args.selected, "rt", newline="") as selected_source, \
            args.labels.open(newline="") as label_source:
        selected_rows = csv.DictReader(selected_source, delimiter="\t")
        label_rows = csv.DictReader(label_source, delimiter="\t")
        for row, label in zip(selected_rows, label_rows):
            if row["op"] != label["op"]:
                raise RuntimeError("selected/label desynchronization")
            if (label["selector_status"] == "constraining"
                    and label["target_flip"] == "1"):
                cell = tuple(int(row[field]) for field in CELL)
                state = row_states(row)["schedule.class_tuple"]
                target_groups.add(cell + (state,))
                target_operands.add(row["op"])

    retained = 0
    retained_targets = set()
    group_counts = {}
    with gzip.open(args.selected, "rt", newline="") as selected_source, \
            args.labels.open(newline="") as label_source:
        selected_rows = csv.DictReader(selected_source, delimiter="\t")
        label_rows = csv.DictReader(label_source, delimiter="\t")
        source_columns = tuple(selected_rows.fieldnames or ())
        columns = (
            "label", "physical_status", "physical_label", "target_flip",
        ) + tuple(column for column in source_columns if column != "label")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", newline="") as target:
            writer = csv.DictWriter(
                target, columns, delimiter="\t", extrasaction="ignore"
            )
            writer.writeheader()
            for row, label in zip(selected_rows, label_rows):
                if row["op"] != label["op"]:
                    raise RuntimeError("selected/label desynchronization")
                if label["selector_status"] != "constraining":
                    continue
                cell = tuple(int(row[field]) for field in CELL)
                state = row_states(row)["schedule.class_tuple"]
                group = cell + (state,)
                if group not in target_groups:
                    continue
                output = dict(row)
                output.update({
                    "label": "POS" if label["target_flip"] == "1" else "NEG",
                    "physical_status": "constraining",
                    "physical_label": label["allowed_carry"],
                    "target_flip": label["target_flip"],
                })
                writer.writerow(output)
                retained += 1
                group_counts[group] = group_counts.get(group, 0) + 1
                if label["target_flip"] == "1":
                    retained_targets.add(row["op"])

    if retained_targets != target_operands:
        raise RuntimeError("not every target survived neighborhood extraction")
    print(
        f"wrote {args.output} groups={len(target_groups)} rows={retained} "
        f"targets={len(retained_targets)} min_group={min(group_counts.values())} "
        f"max_group={max(group_counts.values())}"
    )


if __name__ == "__main__":
    main()
