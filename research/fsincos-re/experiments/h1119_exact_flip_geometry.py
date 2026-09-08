#!/usr/bin/env python3
"""Measure exact R59 carry-flip geometry using all-mode delta sets.

Unlike h1104, this does not treat the two force endpoints as labels.  A row
is constraining only when the intersection of all four architectural modes
requires the incumbent carry or its complement.  Rows permitting both are
neutral.  The three operands not representable by a carry bit are reported
separately.
"""

import argparse
import csv
from collections import Counter, defaultdict
from fractions import Fraction

from h1110_carry_gate_mine import allmode_allowed, extract_carry_state


CELL = ("branch", "theta", "ce", "s4", "side", "b1", "b2",
        "low3", "dist", "rsh")


def signed128(text):
    value = int(text, 16)
    return value - (1 << 128) if value >> 127 else value


def best_threshold(records, coordinate):
    """Minimum errors for a scalar threshold in either orientation."""
    grouped = defaultdict(lambda: [0, 0])
    for row in records:
        grouped[coordinate(row)][row["target_flip"]] += 1
    points = sorted(grouped.items())
    total = [sum(counts[label] for _, counts in points) for label in (0, 1)]
    below = [0, 0]
    candidates = []
    for index in range(len(points) + 1):
        # flip below: no-flips below plus flips above are errors.
        candidates.append((below[0] + total[1] - below[1],
                           "flip_ge", index))
        # flip above: flips below plus no-flips above are errors.
        candidates.append((below[1] + total[0] - below[0],
                           "flip_lt", index))
        if index < len(points):
            below[0] += points[index][1][0]
            below[1] += points[index][1][1]
    return min(candidates)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("features")
    parser.add_argument("positive_allmode")
    parser.add_argument("control_allmode")
    parser.add_argument("output")
    args = parser.parse_args()

    positive_delta = allmode_allowed(args.positive_allmode)
    control_delta = allmode_allowed(args.control_allmode)
    with open(args.features) as source:
        rows = list(csv.DictReader(source, delimiter="\t"))

    constraining = []
    impossible = []
    for row in rows:
        bank = positive_delta if row["label"] == "POS" else control_delta
        state = extract_carry_state(row, bank[row["op"]])
        allowed_carry = state[3]
        if not allowed_carry:
            impossible.append((row, state))
            continue
        opposite = 1 - state[2]
        if state[2] in allowed_carry and opposite in allowed_carry:
            continue
        row = dict(row)
        row["target_flip"] = int(opposite in allowed_carry)
        row["m"] = Fraction(signed128(row["Mreg"]), 1 << 66)
        row["z"] = Fraction(int(row["rd3"], 16), 1 << int(row["rsh"]))
        row["zr"] = row["z"] - int(row["z"])
        row["t4q"] = Fraction(int(row["t4"], 16), 1 << int(row["s4"]))
        constraining.append(row)

    positive_cells = {tuple(row[name] for name in CELL)
                      for row in constraining if row["target_flip"]}
    cells = defaultdict(list)
    for row in constraining:
        key = tuple(row[name] for name in CELL)
        if key in positive_cells:
            cells[key].append(row)

    coordinates = {
        "M": lambda row: row["m"],
        "thirds_fraction": lambda row: row["zr"],
        "square_discard": lambda row: row["t4q"],
    }
    slopes = [Fraction(n, 16) for n in range(-256, 257)]
    totals = Counter()
    with open(args.output, "w") as target:
        target.write("rows\t%d\nconstraining\t%d\nimpossible\t%d\n"
                     "positive_cells\t%d\n" %
                     (len(rows), len(constraining), len(impossible),
                      len(cells)))
        target.write("\n[carry-impossible]\n")
        for row, state in impossible:
            target.write("%s\t%s\tcurrent_delta=%d\n" %
                         (row["op"], row["branch"], state[1]))
        target.write("\n[cell scalar thresholds]\n")
        target.write("cell\trows\tflip\tnoflip\tMerr\tZerr\tT4err"
                     "\tbest_affine_err\tbest_affine_slope\n")
        for key in sorted(cells):
            group = cells[key]
            results = {name: best_threshold(group, function)
                       for name, function in coordinates.items()}
            affine = []
            for slope in slopes:
                result = best_threshold(
                    group, lambda row, s=slope: row["m"] + s * row["zr"])
                affine.append((result[0], abs(slope), slope, result))
            best_affine = min(affine)
            for name, result in results.items():
                totals[name] += result[0]
            totals["affine"] += best_affine[0]
            flips = sum(row["target_flip"] for row in group)
            target.write("%s\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%s\n" % (
                "/".join(key), len(group), flips, len(group) - flips,
                results["M"][0], results["thirds_fraction"][0],
                results["square_discard"][0], best_affine[0],
                best_affine[2]))
        target.write("\n[totals]\n")
        for name in ("M", "thirds_fraction", "square_discard", "affine"):
            target.write("%s\t%d\n" % (name, totals[name]))

    print("wrote", args.output, "rows", len(rows),
          "constraining", len(constraining), "cells", len(cells),
          "impossible", len(impossible), "totals", dict(totals))


if __name__ == "__main__":
    main()
