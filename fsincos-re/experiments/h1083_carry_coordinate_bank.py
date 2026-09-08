#!/usr/bin/env python3
"""Build a deduplicated RU bank for the active-lower carry coordinate.

The h1082 searches are hardware-label blind.  This script merges their exact
distance-9/low3=5/qpost11=20 selections and removes every operand already
present in an earlier hardware bank.  It does not capture hardware itself.
"""

import csv
import glob
import os
import sys


if len(sys.argv) != 4:
    raise SystemExit("usage: h1083_carry_coordinate_bank.py "
                     "H1082_GLOB FEATURES_OUT OPS_OUT")
source_glob, feature_output, operand_output = sys.argv[1:]
source_paths = set(glob.glob(source_glob))
for path in (feature_output, operand_output):
    if os.path.exists(path):
        raise SystemExit("refusing to overwrite " + path)

cached = set()
for path in glob.glob("tmp/ledger33/current/*.tsv"):
    if path in source_paths:
        continue
    with open(path) as source:
        reader = csv.DictReader(source, delimiter="\t")
        if (reader.fieldnames and "op" in reader.fieldnames
                and "hw" in reader.fieldnames):
            for row in reader:
                if row.get("op") and row.get("hw"):
                    cached.add(row["op"].lower())
with open("tmp/ledger33/probe_keys.tsv") as source:
    for fields in csv.reader(source, delimiter="\t"):
        if len(fields) >= 4:
            cached.add((fields[2] + " " + fields[3]).lower())

selected = {}
columns = None
for path in sorted(source_paths):
    with open(path) as source:
        reader = csv.DictReader(source, delimiter="\t")
        if columns is None:
            columns = reader.fieldnames
        elif reader.fieldnames != columns:
            raise RuntimeError("feature schema mismatch in " + path)
        for row in reader:
            operand = row["op"].lower()
            if operand not in cached:
                selected.setdefault(operand, row)

if not selected:
    raise RuntimeError("no fresh operands selected")
order = sorted(selected, key=lambda operand: (
    int(selected[operand]["pcut"]), int(selected[operand]["mi"]),
    int(selected[operand]["b1"]), int(selected[operand]["b2"]),
    int(selected[operand]["m128"]), operand))
with open(feature_output, "w", newline="") as target:
    writer = csv.DictWriter(target, columns, delimiter="\t")
    writer.writeheader()
    writer.writerows(selected[operand] for operand in order)
with open(operand_output, "w") as target:
    for operand in order:
        target.write(operand + "\n")

print("sources", len(source_paths), "cached", len(cached),
      "fresh", len(order))
for operand in order:
    row = selected[operand]
    print(operand, "p=" + row["pcut"], "mi=" + row["mi"],
          "b=" + row["b1"] + row["b2"], "m128=" + row["m128"],
          "oldfire=" + row["fire"])
