#!/usr/bin/env python3
"""h1048: search exact linear residue coordinates for active selectors."""

import argparse
import csv
import math
from collections import Counter, defaultdict


def load(family):
    with open(f"/tmp/h1042_{family}_union.tsv") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    for row in rows:
        for key in row.keys() - {"label", "insn", "op"}:
            row[key] = int(row[key])
        row["mul65"] = (row["mul"] >> 65) & 1
    return rows


def evaluate(rows, fields, first, second, coefficient):
    cells = defaultdict(lambda: [[], []])
    for row in rows:
        key = tuple(row[field] for field in fields)
        value = first * row["mreg"] + coefficient * row[second]
        cells[key][row["label"] == "FIX"].append(value)
    counts = Counter()
    for negatives, positives in cells.values():
        if not positives:
            counts["negative"] += len(negatives)
        elif not negatives:
            counts["pure"] += len(positives)
        elif max(negatives) < min(positives):
            counts["gt"] += len(positives)
        elif max(positives) < min(negatives):
            counts["lt"] += len(positives)
        else:
            counts["conflict"] += len(positives)
            counts["conflict_negative"] += len(negatives)
    return counts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("family", choices=("top1", "low1"))
    args = parser.parse_args()
    rows = load(args.family)
    fields = ["sum8", "s4", "side", "dist", "low3", "b1", "b2",
              "pdown"]
    if args.family == "top1":
        fields.append("mul65")
    seen = set()
    ranked = []
    for second in ("qpost", "qpre", "qright", "qleft", "qf4", "qsq"):
        for first in range(1, 33):
            for coefficient in range(-256, 257):
                divisor = math.gcd(first, abs(coefficient))
                signature = second, first // divisor, coefficient // divisor
                if signature in seen:
                    continue
                seen.add(signature)
                counts = evaluate(rows, fields, first, second, coefficient)
                ranked.append((counts["conflict"],
                               counts["conflict_negative"],
                               -(counts["gt"] + counts["lt"]),
                               -counts["pure"], second, first, coefficient,
                               counts))
    print(args.family, "fields", fields, "rows", len(rows))
    for result in sorted(ranked)[:80]:
        print(result[4:7], "conflict", result[0], result[1],
              "separable", -result[2], "pure", -result[3],
              "dirs", result[7]["gt"], result[7]["lt"])


if __name__ == "__main__":
    main()
