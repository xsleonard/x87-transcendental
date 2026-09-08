#!/usr/bin/env python3
"""h1052: derive the active selector's 11-bit endpoint/R60 floor law."""

from collections import Counter, defaultdict

import h1051_active_blind_score as blind


ONE = 1 << 66
BANKS = (
    "/tmp/h1050_active_force_blind.tsv",
    "/tmp/h1050_active_force_annulus.tsv",
    "/tmp/h1050_active_force_micro.tsv",
)


def rows(family):
    result = blind.load_training(family)
    for path in BANKS:
        result.extend(blind.blind_rows(family, path))
    direction = 1 if family == "top1" else 0
    for row in result:
        row["qpost11"] = row["qpost"] * 2048 // ONE
    return [row for row in result
            if row["pcut"] == direction
            and (row["qpost11"] >= 2024 if family == "top1"
                 else row["qpost11"] <= 27)]


def threshold_range(family, fixes, breaks):
    if family == "top1":
        lower, upper = max(breaks), min(fixes)
    else:
        lower, upper = max(fixes), min(breaks)
    values = [value for value in range(lower // ONE - 1,
                                       upper // ONE + 2)
              if lower < value * ONE <= upper]
    if not values:
        raise AssertionError((family, lower, upper))
    return min(values), max(values), lower / ONE, upper / ONE


def main():
    for family in ("top1", "low1"):
        sample = rows(family)
        fields = ("s4", "side", "dist", "low3", "b1", "b2", "qpost11")
        cells = defaultdict(list)
        for row in sample:
            cells[tuple(row[field] for field in fields)].append(row)
        print("\n", family, "rows", len(sample),
              Counter(row["label"] for row in sample), "cells", len(cells))
        for key, cell in sorted(cells.items()):
            fixes = [row["mreg"] for row in cell if row["label"] == "FIX"]
            breaks = [row["mreg"] for row in cell if row["label"] == "BREAK"]
            if fixes and breaks:
                trange = threshold_range(family, fixes, breaks)
                print(" MIX", key, len(fixes), len(breaks), "U", trange)
            elif fixes:
                values = [value / ONE for value in fixes]
                print(" POS", key, len(fixes), "M", min(values), max(values))


if __name__ == "__main__":
    main()
