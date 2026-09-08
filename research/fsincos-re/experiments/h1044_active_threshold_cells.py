#!/usr/bin/env python3
"""h1044: print the exact monotone R60 threshold cells for active misses."""

import argparse
import csv
from collections import defaultdict
from fractions import Fraction

import h1034_top0_tap_solver as tap_solver


ONE = 1 << 66


def bit(row, name, index):
    return (int(row[name]) >> index) & 1


def simplest_between(lower, upper, sense):
    """Return a small dyadic boundary in an open/closed integer gap."""
    for bits in range(0, 13):
        step = ONE >> bits
        if sense == "gt":
            # negative < boundary <= positive
            numerator = lower // step + 1
            value = numerator * step
            if value <= upper:
                return numerator, bits, value
        else:
            # positive < boundary <= negative
            numerator = lower // step + 1
            value = numerator * step
            if value <= upper:
                return numerator, bits, value
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("family", choices=("top1", "low1"))
    args = parser.parse_args()
    with open(f"/tmp/h1042_{args.family}_union.tsv") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    for row in rows:
        for key in row.keys() - {"label", "insn", "op"}:
            row[key] = int(row[key])
        row["mul65"] = bit(row, "mul", 65)
        row["qpost55"] = bit(row, "qpost", 55)
        row["qpost56"] = bit(row, "qpost", 56)
        row["qpost57"] = bit(row, "qpost", 57)
        row["qf441"] = bit(row, "qf4", 41)

    common = ("sum8", "s4", "side", "dist", "low3", "b1", "b2",
              "pdown")
    if args.family == "top1":
        fields = common + ("mul65", "qpost56", "qpost55")
        sense = "gt"
    else:
        fields = common + ("qf441", "qpost57", "qpost56")
        sense = "lt"
    cells = defaultdict(list)
    for row in rows:
        cells[tuple(row[field] for field in fields)].append(row)

    print("fields", fields, "sense", sense)
    mixed = []
    for key, cell in cells.items():
        positive = [row["mreg"] for row in cell if row["label"] == "FIX"]
        negative = [row["mreg"] for row in cell if row["label"] == "BREAK"]
        if not positive or not negative:
            continue
        if sense == "gt":
            lower, upper = max(negative), min(positive)
        else:
            lower, upper = max(positive), min(negative)
        if lower >= upper:
            raise AssertionError((key, lower, upper))
        simple = simplest_between(lower, upper, sense)
        _, u0 = tap_solver.base_and_u(cell[0], 0)
        mixed.append((key, len(positive), len(negative), lower, upper,
                      simple, u0))

    print("mixed", len(mixed))
    for key, np, nn, lower, upper, simple, u0 in sorted(mixed):
        lo = float(Fraction(lower, ONE))
        hi = float(Fraction(upper, ONE))
        if simple:
            numerator, bits, _ = simple
            boundary = f"{numerator}/2^{bits}"
        else:
            boundary = "none<=2^12"
        print(key, f"rows={np}+/{nn}-", f"gap={lo:.9f}..{hi:.9f}",
              "dyadic", boundary, "top0-u0", u0)


if __name__ == "__main__":
    main()
