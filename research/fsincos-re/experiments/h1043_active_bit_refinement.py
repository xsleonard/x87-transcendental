#!/usr/bin/env python3
"""h1043: refine active-family cells with individual multiplier-state bits.

The force probes label where replacing the terminal carry fixes or breaks the
union corpus.  This experiment asks which discarded product bits make those
labels monotone in the already-derived R60 coordinate.  It reports only
one-bit refinements, so a zero-conflict result remains an integer closed-form
partition rather than an unconstrained operand table.
"""

import argparse
import csv
from collections import Counter, defaultdict


SOURCES = ("qpost", "qpre", "qright", "qleft", "qf4", "qsq", "mul",
           "lf", "f4k", "rf", "mag")


def load(family):
    with open(f"/tmp/h1042_{family}_union.tsv") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    for row in rows:
        for key in row.keys() - {"label", "insn", "op"}:
            row[key] = int(row[key])
    widths = {name: max(row[name].bit_length() for row in rows)
              for name in SOURCES}
    for row in rows:
        for name in SOURCES:
            value = row[name]
            for bit in range(max(1, widths[name])):
                row[f"{name}{bit}"] = (value >> bit) & 1
    return rows


def classify(rows, fields, coordinate="mreg"):
    cells = defaultdict(list)
    for row in rows:
        cells[tuple(row[field] for field in fields)].append(row)

    counts = Counter()
    details = []
    for key, cell in cells.items():
        positives = [row[coordinate] for row in cell if row["label"] == "FIX"]
        negatives = [row[coordinate] for row in cell if row["label"] == "BREAK"]
        if not positives:
            kind = "negative"
        elif not negatives:
            kind = "positive"
        elif max(negatives) < min(positives):
            kind = "gt"
        elif max(positives) < min(negatives):
            kind = "lt"
        else:
            kind = "conflict"
        counts[(kind, "FIX")] += len(positives)
        counts[(kind, "BREAK")] += len(negatives)
        if kind in ("gt", "lt", "conflict"):
            details.append((key, kind, len(positives), len(negatives),
                            min(positives), max(positives),
                            min(negatives), max(negatives)))
    return counts, details


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("family", choices=("top1", "low1"))
    parser.add_argument("--add", action="append", default=[])
    args = parser.parse_args()
    rows = load(args.family)
    if args.family == "top1":
        fields = ["sum8", "s4", "side", "dist", "low3", "b1", "b2",
                  "pdown", "mul65"]
    else:
        fields = ["sum8", "s4", "side", "dist", "low3", "b1", "b2",
                  "pdown"]
    fields += args.add

    counts, details = classify(rows, fields)
    print("fields", fields)
    print("base", dict(counts))
    candidates = sorted({key for row in rows for key in row
                         if key[-1:].isdigit() and key not in fields
                         and key not in SOURCES})
    ranked = []
    for candidate in candidates:
        score, _ = classify(rows, fields + [candidate])
        ranked.append((score[("conflict", "FIX")],
                       score[("conflict", "BREAK")],
                       -score[("gt", "FIX")] - score[("lt", "FIX")],
                       candidate, score))
    print("\nbest refinements")
    for conflict_pos, conflict_neg, neg_separable, name, score in sorted(ranked)[:30]:
        print(name, "conflict", conflict_pos, conflict_neg,
              "separable", -neg_separable,
              "pure", score[("positive", "FIX")])

    print("\nnon-pure cells")
    for detail in sorted(details):
        print(detail)


if __name__ == "__main__":
    main()
