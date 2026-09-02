#!/usr/bin/env python3
"""h1046: synthesize small floor laws for active-family integer thresholds."""

import argparse
import csv
from collections import Counter, defaultdict

import h1034_top0_tap_solver as tap_solver


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


def mixed_thresholds(rows, fields, family):
    cells = defaultdict(list)
    for row in rows:
        cells[tuple(row[field] for field in fields)].append(row)
    thresholds = []
    for key, cell in cells.items():
        fixes = [row["mreg"] for row in cell if row["label"] == "FIX"]
        breaks = [row["mreg"] for row in cell if row["label"] == "BREAK"]
        if not fixes or not breaks:
            continue
        if family == "top1":
            lo, hi = max(breaks), min(fixes)
        else:
            lo, hi = max(fixes), min(breaks)
        candidates = [value for value in range(lo // ONE - 1, hi // ONE + 2)
                      if lo < value * ONE <= hi]
        if not candidates:
            raise AssertionError((key, lo, hi, candidates))
        thresholds.append((key, (min(candidates), max(candidates))))
    return thresholds


def fit_floor(points, fields, max_weight=36, max_q=16):
    results = []
    dimensions = len(fields)
    for denominator in range(1, max_q + 1):
        best_weight = None
        for weight in range(max_weight + 1):
            if best_weight is not None and weight > best_weight:
                break
            for slopes in tap_solver.signed_shell(dimensions, weight):
                c0lo, c0hi = -512, 512
                for values, target_range in points:
                    target_lo, target_hi = target_range
                    rest = sum(slope * value
                               for slope, value in zip(slopes, values))
                    c0lo = max(c0lo, denominator * target_lo - rest)
                    c0hi = min(c0hi,
                               denominator * (target_hi + 1) - 1 - rest)
                    if c0lo > c0hi:
                        break
                if c0lo > c0hi:
                    continue
                c0 = min(max(0, c0lo), c0hi)
                total_weight = weight + abs(c0) + denominator
                if best_weight is None:
                    best_weight = weight
                results.append((total_weight,
                                sum(value != 0 for value in (c0,) + slopes),
                                denominator, (c0,) + slopes))
    return sorted(results)


def score(rows, fields, denominator, coeff, family):
    c0, slopes = coeff[0], coeff[1:]
    counts = Counter()
    bad = []
    for row in rows:
        numerator = c0 + sum(slope * row[field]
                             for slope, field in zip(slopes, fields))
        threshold = numerator // denominator
        fire = (row["mi"] >= threshold if family == "top1"
                else row["mi"] < threshold)
        wanted = row["label"] == "FIX"
        counts[row["label"], fire] += 1
        if fire != wanted:
            bad.append((row, threshold))
    return counts, bad


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("family", choices=("top1", "low1"))
    parser.add_argument("--weight", type=int, default=32)
    args = parser.parse_args()
    rows = load(args.family)
    if args.family == "top1":
        cell_fields = ("sum8", "s4", "side", "dist", "low3", "b1",
                       "b2", "pdown", "mul65", "qpost56", "qpost55")
    else:
        cell_fields = ("sum8", "s4", "side", "dist", "low3", "b1",
                       "b2", "pdown", "qf441", "qpost57", "qpost56")
    thresholds = mixed_thresholds(rows, cell_fields, args.family)
    threshold_map = dict(thresholds)

    specs = (
        ("low3", "b1", "b2", "lp", "d7"),
        ("low3", "b1", "b2", "lp", "d7", "pdown"),
    )
    for quadrant in sorted({(row["s4"], row["side"]) for row in rows}):
        sample = [row for row in rows
                  if (row["s4"], row["side"]) == quadrant]
        cell_rows = defaultdict(list)
        for row in sample:
            key = tuple(row[field] for field in cell_fields)
            if key in threshold_map:
                cell_rows[key].append(row)
        print("\n", args.family, "quadrant", quadrant,
              "rows", len(sample), "mixed", len(cell_rows))
        for fields in specs:
            points = []
            for key, cell in cell_rows.items():
                points.append((tuple(cell[0][field] for field in fields),
                               threshold_map[key]))
            solutions = fit_floor(points, fields, args.weight)
            if not solutions:
                print(" fields", fields, "no floor law")
                continue
            ranked = []
            for complexity, nonzero, denominator, coeff in solutions[:200]:
                counts, bad = score(
                    sample, fields, denominator, coeff, args.family)
                ranked.append((len(bad), complexity, nonzero, denominator,
                               coeff, counts))
            print(" fields", fields)
            for result in sorted(ranked)[:12]:
                print("  bad/complexity/nz/q/coeff", result[:5],
                      "score", dict(result[5]))


if __name__ == "__main__":
    main()
