#!/usr/bin/env python3
"""Freeze rows changed by the h1275 one-cell dcc threshold extension.

The selector under test is fixed before this extraction: QX final generate at
square column 61 AND the alternate legal 4:2-tree square-sum bit at column 61
extends the incumbent R60 threshold by one 2**66 cell.  This script writes
every constraining dense row on which that extension changes the endpoint,
so a follow-up structural search cannot omit collateral rows.  No hardware is
executed.
"""

from __future__ import annotations

import argparse
import csv
import gzip
from pathlib import Path

from h1275_dcc_dense_structural_audit import SCOPE, TARGET, row_predicates


PREDICATE = "qx_gen61_and_alt3_sum61"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("labels", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--predicate", default=PREDICATE)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    with args.labels.open(newline="") as source:
        labels = {(row["corpus"], row["index"]): row
                  for row in csv.DictReader(source, delimiter="\t")}

    selected = []
    with gzip.open(args.features, "rt", newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            if not all(row[name] == value for name, value in SCOPE.items()):
                continue
            truth = labels[(row["corpus"], row["index"])]
            if truth["selector_status"] != "constraining":
                continue
            predicate = row_predicates(row)[args.predicate]
            if not predicate:
                continue
            low3 = int(row["low3"])
            base0 = (2 * low3 + 2 * int(row["b1"])
                     + 3 * int(row["b2"]) - 3 * (low3 & 1) - 6)
            u0 = 2 * (base0 // 8) + (low3 & 1)
            mreg = int(row["Mreg"], 16)
            current = int(truth["current_carry"])
            extended = int(not (mreg < (u0 + 1) * (1 << 66)))
            if extended == current:
                continue
            row["label"] = "POS" if row["op"] == TARGET else "NEG"
            row["physical_status"] = truth["selector_status"]
            row["physical_label"] = truth["allowed_carry"]
            row["target_flip"] = truth["target_flip"]
            selected.append(row)

    if sum(row["label"] == "POS" for row in selected) != 1:
        raise RuntimeError("frozen population must contain dcc exactly once")
    columns = (
        "label", "physical_status", "physical_label", "target_flip",
    ) + tuple(key for key in selected[0]
              if key not in {"label", "physical_status", "physical_label",
                             "target_flip"})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", newline="") as target:
        writer = csv.DictWriter(
            target, columns, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(selected)
    print(f"wrote {args.output} rows={len(selected)}", flush=True)


if __name__ == "__main__":
    main()
