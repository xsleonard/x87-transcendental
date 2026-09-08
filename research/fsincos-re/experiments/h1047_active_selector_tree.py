#!/usr/bin/env python3
"""h1047: derive a compact exact decision tree for active selectors."""

import argparse
import csv
import math
from collections import Counter


ONE = 1 << 66


def load(family):
    with open(f"/tmp/h1042_{family}_union.tsv") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    for row in rows:
        for key in row.keys() - {"label", "insn", "op"}:
            row[key] = int(row[key])
        row["mi"] = row["mreg"] // ONE
        row["lp"] = row["low3"] & 1
        row["d7"] = row["dist"] - 7
        row["retained"] = row["sum8"] - row["low3"]
        row["qpost11"] = row["qpost"] * 2048 // ONE
        row["qf441"] = (row["qf4"] >> 41) & 1
        for source in ("qpost", "qf4", "mul"):
            for index in range(48, 66):
                row[f"{source}{index}"] = (row[source] >> index) & 1
        for index in range(36, 48):
            row[f"qf4{index}"] = (row["qf4"] >> index) & 1
    return rows


def impurity(rows):
    count = Counter(row["label"] for row in rows)
    return len(rows) - sum(value * value for value in count.values()) / len(rows)


def candidate_splits(rows, fields):
    for field in fields:
        ordered = sorted({row[field] for row in rows})
        for lower, upper in zip(ordered, ordered[1:]):
            threshold = (lower + upper) / 2
            left = [row for row in rows if row[field] <= threshold]
            right = [row for row in rows if row[field] > threshold]
            yield (impurity(left) + impurity(right),
                   -min(len(left), len(right)), field, threshold,
                   left, right)


def build(rows, fields, depth, max_depth):
    labels = Counter(row["label"] for row in rows)
    if len(labels) == 1 or depth == max_depth:
        return ("leaf", labels)
    split = min(candidate_splits(rows, fields), default=None)
    if split is None or split[0] >= impurity(rows):
        return ("leaf", labels)
    _, _, field, threshold, left, right = split
    return ("node", field, threshold,
            build(left, fields, depth + 1, max_depth),
            build(right, fields, depth + 1, max_depth))


def stats(tree, depth=0):
    if tree[0] == "leaf":
        labels = tree[1]
        return 1, depth, len(labels) > 1, sum(labels.values()) - max(labels.values())
    left = stats(tree[3], depth + 1)
    right = stats(tree[4], depth + 1)
    return (left[0] + right[0], max(left[1], right[1]),
            left[2] + right[2], left[3] + right[3])


def emit(tree, indent=""):
    if tree[0] == "leaf":
        print(indent + "=> " + repr(dict(tree[1])))
        return
    _, field, threshold, left, right = tree
    rendered = int(threshold) if threshold.is_integer() else threshold
    print(indent + f"if {field} <= {rendered}:")
    emit(left, indent + "  ")
    print(indent + "else:")
    emit(right, indent + "  ")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("family", choices=("top1", "low1"))
    parser.add_argument("--depth", type=int, default=16)
    args = parser.parse_args()
    rows = load(args.family)
    common = ("mi", "low3", "b1", "b2", "lp", "d7", "pdown",
              "s4", "side", "retained")
    if args.family == "top1":
        fields = common + ("mul65", "qpost11")
    else:
        fields = common + ("qf441", "qpost11")
    tree = build(rows, fields, 0, args.depth)
    print(args.family, "rows", len(rows), "fields", fields,
          "stats leaves/depth/mixed/errors", stats(tree))
    emit(tree)


if __name__ == "__main__":
    main()
