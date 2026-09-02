#!/usr/bin/env python3
"""h1053: fit the compact 11-bit endpoint/R60 floor by quadrant."""

import argparse
from collections import Counter, defaultdict

import h1046_active_floor_synthesis as synth
import h1051_active_blind_score as blind


ONE = 1 << 66
BANKS = (
    "/tmp/h1050_active_force_blind.tsv",
    "/tmp/h1050_active_force_annulus.tsv",
    "/tmp/h1050_active_force_micro.tsv",
)


def load(family):
    rows = blind.load_training(family)
    for path in BANKS:
        rows.extend(blind.blind_rows(family, path))
    direction = 1 if family == "top1" else 0
    result = []
    for row in rows:
        row["qpost11"] = row["qpost"] * 2048 // ONE
        row["phase11"] = (2048 - row["qpost11"]
                          if family == "top1" else row["qpost11"])
        row["lp"] = row["low3"] & 1
        row["d7"] = row["dist"] - 7
        if row["pcut"] != direction:
            continue
        if family == "top1" and row["qpost11"] < 2024:
            continue
        if family == "low1" and row["qpost11"] > 27:
            continue
        result.append(row)
    return result


def intervals(family, rows, cell_fields):
    cells = defaultdict(list)
    for row in rows:
        cells[tuple(row[field] for field in cell_fields)].append(row)
    points = []
    for cell in cells.values():
        fixes = [row["mreg"] for row in cell if row["label"] == "FIX"]
        breaks = [row["mreg"] for row in cell if row["label"] == "BREAK"]
        if not fixes or not breaks:
            continue
        if family == "top1":
            lower, upper = max(breaks), min(fixes)
        else:
            lower, upper = max(fixes), min(breaks)
        allowed = [value for value in range(lower // ONE - 1,
                                             upper // ONE + 2)
                   if lower < value * ONE <= upper]
        if not allowed:
            raise AssertionError((family, lower, upper))
        points.append((cell[0], (min(allowed), max(allowed))))
    return points


def score(family, rows, fields, denominator, coeff):
    counts = Counter()
    c0, slopes = coeff[0], coeff[1:]
    for row in rows:
        numerator = c0 + sum(slope * row[field]
                             for slope, field in zip(slopes, fields))
        threshold = numerator // denominator
        fire = (row["mreg"] >= threshold * ONE if family == "top1"
                else row["mreg"] < threshold * ONE)
        counts[row["label"], fire] += 1
    return counts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("family", choices=("top1", "low1"))
    parser.add_argument("--weight", type=int, default=20)
    args = parser.parse_args()
    rows = load(args.family)
    fields = ("low3", "b1", "b2", "lp", "d7", "phase11")
    cell_fields = ("s4", "side", "dist", "low3", "b1", "b2",
                   "qpost11")
    print(args.family, "rows", len(rows), Counter(row["label"] for row in rows))
    for quadrant in sorted({(row["s4"], row["side"]) for row in rows}):
        sample = [row for row in rows
                  if (row["s4"], row["side"]) == quadrant]
        points = intervals(args.family, sample, cell_fields)
        encoded = [(tuple(row[field] for field in fields), target)
                   for row, target in points]
        solutions = synth.fit_floor(
            encoded, fields, max_weight=args.weight, max_q=16)
        ranked = []
        for complexity, nonzero, denominator, coeff in solutions[:1000]:
            counts = score(args.family, sample, fields, denominator, coeff)
            errors = counts["FIX", False] + counts["BREAK", True]
            ranked.append((errors, complexity, nonzero, denominator,
                           coeff, counts))
        print("\nquadrant", quadrant, "rows", len(sample),
              Counter(row["label"] for row in sample),
              "mixed constraints", len(points), "solutions", len(solutions))
        for result in sorted(ranked)[:20]:
            print(" ", result[:5], dict(result[5]))


if __name__ == "__main__":
    main()
