#!/usr/bin/env python3
"""h1037: find the exact phase displacement of the TOP/act0 M coordinate.

The sole h1036 obstruction is not a monotonicity conflict: FIX and BREAK
are correctly ordered but share one integer M/2^66 bin.  Evaluate the
nonlinear coordinate at the signed sum phase, as in the earlier theta-ladder
derivation:

    x_k = sqlow + k*theta
    M_k = low3*x_k - (x_k*x_k mod 2^s4).

Scan the small integer port scale k and count structural cells for which an
integer u-floor can exactly separate every known positive and negative.
"""

import csv
from collections import Counter, defaultdict

import h1034_top0_tap_solver as tap_solver
import h1035_top0_response_score as response_score


def load_joint():
    joint = []
    for source in tap_solver.load_h1033_rows():
        if source["line"] != "TOP" or source["act"] != 0 \
                or source["pcut"] != 1:
            continue
        lab = tap_solver.label(source)
        if lab is None:
            continue
        row = dict(source)
        row.update(target=lab, source="h975")
        joint.append(row)
    with open("/tmp/h1025_response_records.tsv") as source:
        raw = [row for row in csv.DictReader(source, delimiter="\t")
               if row["family"] == "top0" and row["source"] == "h1000"]
    records = response_score.run_dumps([row["op"] for row in raw])
    for datum, record in zip(raw, records):
        row = response_score.reconstructed(record)
        if row["pcut"] != 1 or row["sum8"] < 0xf0:
            continue
        row.update(target=int(datum["label"] == "FIX"), source="h1000",
                   op=datum["op"])
        joint.append(row)
    return joint


def shifted_m(row, scale):
    theta = 256 - row["sum8"]
    x = row["sqlow"] + scale * theta
    return row["low3"] * x - (x * x & ((1 << row["s4"]) - 1))


def floor_interval(rows, scale):
    positives = [shifted_m(row, scale) for row in rows if row["target"]]
    negatives = [shifted_m(row, scale) for row in rows if not row["target"]]
    # M >= u*ONE: max negative must be below u*ONE, while min positive
    # must be at or above it.  The integer interval is inclusive.
    lo = max(value // tap_solver.ONE + 1 for value in negatives) \
        if negatives else None
    hi = min(value // tap_solver.ONE for value in positives) \
        if positives else None
    if lo is not None and hi is not None and lo > hi:
        return None
    return lo, hi


def main():
    joint = load_joint()
    for scale in range(-64, 65):
        cells = defaultdict(list)
        for row in joint:
            cells[(256 - row["sum8"], row["s4"], row["side"],
                   row["dist"], row["low3"], row["b1"], row["b2"])].append(row)
        conflict = []
        for cell, rows in cells.items():
            if floor_interval(rows, scale) is None:
                conflict.append((cell, rows))
        conflict_positive = sum(sum(row["target"] for row in rows)
                                for _, rows in conflict)
        if conflict_positive <= 2:
            print("scale", scale, "conflict cells", len(conflict),
                  "conflict positives", conflict_positive)
            for cell, rows in conflict[:8]:
                print(" ", cell,
                      [(row["source"], row["target"],
                        shifted_m(row, scale) / tap_solver.ONE,
                        row.get("op", "")) for row in rows])

    print("\nscale detail for zero-conflict candidates")
    for scale in range(-64, 65):
        cells = defaultdict(list)
        for row in joint:
            cells[(256 - row["sum8"], row["s4"], row["side"],
                   row["dist"], row["low3"], row["b1"], row["b2"])].append(row)
        if all(floor_interval(rows, scale) is not None
               for rows in cells.values()):
            print(" scale", scale, "cells", len(cells),
                  "labels", Counter((row["source"], row["target"])
                                    for row in joint))


if __name__ == "__main__":
    main()
