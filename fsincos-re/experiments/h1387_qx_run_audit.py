#!/usr/bin/env python3
"""Audit the literal-P5 QX square carry-propagate run on cached banks."""

import argparse
import csv
import os

from h1100_p5_multiplier_tree import TREE_MASK, csa3, multiplier_tree


def qx_run(square_input):
    state = multiplier_tree(square_input, square_input >> 3)
    square_sum, square_carry = csa3(
        (state["sum"] << 3) & TREE_MASK,
        (state["carry"] << 3) & TREE_MASK,
        square_input * (square_input & 7))
    cut = (square_input * square_input).bit_length() - 67
    run = 0
    for position in range(cut - 1, -1, -1):
        if ((square_sum ^ square_carry) >> position) & 1:
            run += 1
        else:
            break
    return cut, run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--minimum", type=int, default=13)
    args = parser.parse_args()
    if os.path.exists(args.output):
        raise SystemExit("refusing to overwrite " + args.output)
    with open(args.input) as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    hits = []
    histogram = {}
    for row in rows:
        cut, run = qx_run(int(row["tc_mul_sig"], 16))
        histogram[run] = histogram.get(run, 0) + 1
        if run >= args.minimum:
            hits.append((row, cut, run))
    fields = ("mode", "op", "label", "branch", "desired", "hw", "model",
              "base", "force_minus2", "force_plus1", "endpoint_matches",
              "anchor", "challenge_tier", "cell_relation")
    with open(args.output, "w") as target:
        target.write("rows\t%d\nhits\t%d\nminimum\t%d\n" %
                     (len(rows), len(hits), args.minimum))
        target.write("histogram\t" + ",".join(
            "%d:%d" % item for item in sorted(histogram.items())) + "\n")
        target.write("\ncut\trun\t" + "\t".join(fields) + "\n")
        for row, cut, run in hits:
            target.write("%d\t%d\t%s\n" % (
                cut, run, "\t".join(row.get(field, "") for field in fields)))
    print("rows", len(rows), "hits", len(hits), "minimum", args.minimum)


if __name__ == "__main__":
    main()
