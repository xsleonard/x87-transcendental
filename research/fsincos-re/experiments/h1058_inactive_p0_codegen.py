#!/usr/bin/env python3
"""h1058: emit the exact inactive-upper pcut=0 selector.

The absolute +1 response population is monotone in the R60 integer
coordinate inside every populated terminal cell.  Restrict extrapolation to
the (distance, low digit, qpost11) endpoint cells containing a required
response, then synthesize a table-free integer comparison tree.
"""

import csv
from collections import Counter, defaultdict

import h1047_active_selector_tree as tree
import h1054_active_tree_codegen as emit


ONE = 1 << 66
FIELDS = ("mi", "low3", "b1", "b2", "lp", "d7", "s4", "side",
          "qpost11")
emit.FIELDS = FIELDS


def load():
    with open("/tmp/h1056_top0_p0.tsv") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    for row in rows:
        for field in row.keys() - {"label", "insn", "op"}:
            row[field] = int(row[field])
        row["mi"] = row["mreg"] // ONE
        row["lp"] = row["low3"] & 1
        row["d7"] = row["dist"] - 7
        row["qpost11"] = row["qpost"] >> 55
    return rows


def main():
    all_rows = load()
    cells = defaultdict(Counter)
    for row in all_rows:
        cells[row["dist"], row["low3"], row["qpost11"]][row["label"]] += 1
    support = {cell for cell, labels in cells.items() if labels["FIX"]}
    rows = [row for row in all_rows
            if (row["dist"], row["low3"], row["qpost11"]) in support]
    selector = tree.build(rows, FIELDS, 0, 40)
    mistakes = [row for row in rows
                if emit.predict(selector, row) != (row["label"] == "FIX")]
    print("/* support", sorted(support), "*/")
    print("/* rows", len(rows), dict(Counter(row["label"] for row in rows)),
          "leaves/depth/mixed/errors", tree.stats(selector),
          "mistakes", len(mistakes), "*/")
    print(emit.emit_dnf(selector))


if __name__ == "__main__":
    main()
