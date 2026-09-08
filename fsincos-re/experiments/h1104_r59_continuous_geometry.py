#!/usr/bin/env python3
"""Test whether R59 endpoint labels expose a continuous selector coordinate.

This is a diagnostic, not a classifier generator.  It asks whether the two
hardware endpoint classes in each already-derived structural cell are ordered
by M, by the unquantized thirds residue, or by one common affine combination.
A clean common slope would be evidence for a missing arithmetic comparator;
failure prevents disguising a cell-by-cell decision table as a formula.
"""

import argparse
import csv
from collections import defaultdict
from fractions import Fraction


CELL = ("mode", "branch", "theta", "ce", "s4", "side", "low3", "dist",
        "rsh", "b1", "b2")


def signed128(text):
    value = int(text, 16)
    return value - (1 << 128) if value >> 127 else value


def best_threshold(rows, scores):
    """Return minimum errors for either orientation of a scalar threshold."""
    ordered = sorted(zip(scores, rows), key=lambda pair: pair[0])
    groups = []
    for score, row in ordered:
        if not groups or groups[-1][0] != score:
            groups.append([score, 0, 0])
        groups[-1][1 if row["desired"] == "minus2" else 2] += 1
    total_minus = sum(group[1] for group in groups)
    total_plus = sum(group[2] for group in groups)
    # A threshold may be before the first or after the last distinct score.
    candidates = [(total_plus, "minus-low", None),
                  (total_minus, "plus-low", None)]
    low_minus = 0
    low_plus = 0
    for index, group in enumerate(groups):
        low_minus += group[1]
        low_plus += group[2]
        # minus-low errors: plus below + minus above
        candidates.append((low_plus + total_minus - low_minus,
                           "minus-low", group[0]))
        # plus-low errors: minus below + plus above
        candidates.append((low_minus + total_plus - low_plus,
                           "plus-low", group[0]))
    return min(candidates, key=lambda item: (item[0], item[1],
                                             item[2] is None,
                                             item[2] or 0))


parser = argparse.ArgumentParser()
parser.add_argument("features")
parser.add_argument("--slope-denominator", type=int, default=16)
parser.add_argument("--slope-radius", type=int, default=256)
args = parser.parse_args()

with open(args.features) as source:
    rows = list(csv.DictReader(source, delimiter="\t"))

for row in rows:
    row["m"] = Fraction(signed128(row["Mreg"]), 1 << 66)
    row["z"] = Fraction(int(row["rd3"], 16), 1 << int(row["rsh"]))
    # b1/b2 are the integer thirds digit.  Preserve only the continuous
    # residue inside that digit so it cannot merely re-encode the cell key.
    row["zr"] = row["z"] - int(row["z"])

positive_cells = {
    tuple(row[name] for name in CELL)
    for row in rows if row["label"] == "POS"
}
cells = defaultdict(list)
for row in rows:
    key = tuple(row[name] for name in CELL)
    if key in positive_cells:
        cells[key].append(row)

print("rows", len(rows), "positive-cells", len(cells))
print("cell\trows\tpos\tminus\tplus\tMerr\tZerr\tbest_affine")

total_m = total_z = total_affine = 0
common = defaultdict(int)
cell_results = []
slopes = [Fraction(n, args.slope_denominator)
          for n in range(-args.slope_radius, args.slope_radius + 1)]
for key in sorted(cells):
    group = cells[key]
    m_result = best_threshold(group, [row["m"] for row in group])
    z_result = best_threshold(group, [row["zr"] for row in group])
    affine = []
    for slope in slopes:
        result = best_threshold(
            group, [row["m"] + slope * row["zr"] for row in group])
        affine.append((result[0], abs(slope), slope, result))
    _, _, slope, a_result = min(affine)
    total_m += m_result[0]
    total_z += z_result[0]
    total_affine += a_result[0]
    if a_result[0] == 0:
        for candidate in affine:
            if candidate[0] == 0:
                common[candidate[2]] += 1
    positives = sum(row["label"] == "POS" for row in group)
    minus = sum(row["desired"] == "minus2" for row in group)
    print("/".join(key), len(group), positives, minus,
          len(group) - minus, m_result[0], z_result[0],
          "%s@%s:%s" % (a_result[0], slope, a_result[1]), sep="\t")
    cell_results.append((key, group))

print("pooled-independent-cell-errors",
      "M=" + str(total_m), "Z=" + str(total_z),
      "affine=" + str(total_affine))
print("clean-cell-count-by-common-slope")
for slope, count in sorted(common.items(), key=lambda item: (-item[1],
                                                              abs(item[0]),
                                                              item[0]))[:30]:
    print(slope, count)

# Score each common slope with independently optimized thresholds.  This is
# weaker than a closed form (offsets remain cell-specific), but it reveals
# whether one physical comparator direction is even plausible.
pooled = []
for slope in slopes:
    errors = 0
    clean = 0
    for _, group in cell_results:
        result = best_threshold(
            group, [row["m"] + slope * row["zr"] for row in group])
        errors += result[0]
        clean += result[0] == 0
    pooled.append((errors, -clean, abs(slope), slope))
print("best-common-slopes")
for errors, negclean, _, slope in sorted(pooled)[:30]:
    print(slope, "errors=" + str(errors), "clean=" + str(-negclean),
          "of=" + str(len(cells)))
