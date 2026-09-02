#!/usr/bin/env python3
"""h1045: test integer-affine forms of the active-family R60 boundary."""

import argparse
import csv
import random
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
        row["ret128"] = int(row["sum8"] - row["low3"] == 127)
        for name, source, index in (
                ("mul65", "mul", 65),
                ("qpost55", "qpost", 55),
                ("qpost56", "qpost", 56),
                ("qpost57", "qpost", 57),
                ("qf441", "qf4", 41)):
            row[name] = (row[source] >> index) & 1
    return rows


def dot(first, second):
    return sum(a * b for a, b in zip(first, second))


def perceptron(sample, fields, seed, epochs):
    rng = random.Random(seed)
    examples = []
    for row in sample:
        x = [1] + [row[field] for field in fields]
        y = 1 if row["label"] == "FIX" else -1
        examples.append((x, y, row))
    weights = [0] * (len(fields) + 1)
    best = (len(examples) + 1, 0, tuple(weights))
    for epoch in range(epochs):
        rng.shuffle(examples)
        mistakes = 0
        for x, y, _ in examples:
            if y * dot(weights, x) <= 0:
                weights = [weight + y * value
                           for weight, value in zip(weights, x)]
                mistakes += 1
        bad = sum(y * dot(weights, x) <= 0 for x, y, _ in examples)
        candidate = bad, sum(abs(value) for value in weights), tuple(weights)
        if candidate[:2] < best[:2]:
            best = candidate
        if bad == 0:
            return epoch + 1, tuple(weights), examples
    return None, best[2], examples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("family", choices=("top1", "low1"))
    parser.add_argument("--epochs", type=int, default=20000)
    args = parser.parse_args()
    rows = load(args.family)
    if args.family == "top1":
        fields = ("mi", "low3", "b1", "b2", "lp", "d7", "pdown",
                  "mul65", "qpost56", "qpost55", "ret128")
    else:
        fields = ("mi", "low3", "b1", "b2", "lp", "d7", "side",
                  "qf441", "qpost57", "qpost56")

    for grouping in ("all", "quadrant"):
        groups = {("all",): rows}
        if grouping == "quadrant":
            groups = {(s4, side): [row for row in rows
                                   if (row["s4"], row["side"])
                                   == (s4, side)]
                      for s4, side in sorted({(row["s4"], row["side"])
                                              for row in rows})}
        print("\n", grouping, "fields", fields)
        for key, sample in groups.items():
            best = None
            for seed in range(8):
                epoch, weights, examples = perceptron(
                    sample, fields, seed, args.epochs)
                bad = sum(y * dot(weights, x) <= 0
                          for x, y, _ in examples)
                candidate = bad, sum(abs(value) for value in weights), \
                    epoch or args.epochs, weights
                if best is None or candidate[:3] < best[:3]:
                    best = candidate
            print(key, "rows", len(sample),
                  dict(Counter(row["label"] for row in sample)),
                  "bad/l1/epochs", best[:3], "weights", best[3])


if __name__ == "__main__":
    main()
