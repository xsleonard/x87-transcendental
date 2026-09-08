#!/usr/bin/env python3
"""Enumerate physical D-input orientations of the squarer carry tree.

The arithmetic product is invariant under these choices, but the redundant
sum/carry wires are not.  This is the bounded structural ambiguity left by
Figure 5 of Intel US 5,195,051.  Score conditional-carry endpoints and
propagate runs for all four inner 4:2 D slots and all four D slots (plus a
plain 3:2 merge) used to reinsert the omitted radix-8 low digit.
"""

import argparse
import csv
import os
from collections import defaultdict

import numpy as np

from h1100_p5_multiplier_tree import TREE_MASK, csa3, csa42, multiplier_tree
from h1110_carry_gate_mine import (
    GATE_NAMES, allmode_allowed, extract_carry_state, gate_changes,
    gate_errors, state_bad_counts,
)


def bit(value, position):
    return (value >> position) & 1 if position >= 0 else 0


def carry_between(sum_vector, carry_vector, start, end, assumed):
    carry = assumed
    for position in range(max(0, start), end):
        a = bit(sum_vector, position)
        b = bit(carry_vector, position)
        carry = (a & b) | (a & carry) | (b & carry)
    return carry


def merge_low_digit(state, multiplicand, merge_slot):
    wires = [
        (state["sum"] << 3) & TREE_MASK,
        (state["carry"] << 3) & TREE_MASK,
        multiplicand * (multiplicand & 7),
        0,
    ]
    if merge_slot == "csa3":
        return csa3(wires[0], wires[1], wires[2])
    ordered = list(wires)
    distinguished = ordered.pop(merge_slot)
    out_sum, out_carry, _, _ = csa42(
        ordered[0], ordered[1], ordered[2], distinguished)
    return out_sum, out_carry


def orientation_features(row):
    multiplicand = int(row["tc_mul_sig"], 16)
    multiplier = multiplicand >> 3
    exact = multiplicand * multiplicand
    cut = exact.bit_length() - 67
    mask = (1 << 134) - 1
    values = {}
    for inner_slot in range(4):
        state = multiplier_tree(
            multiplicand, multiplier, d_slot=inner_slot)
        for merge_slot in ("csa3", 0, 1, 2, 3):
            sum_vector, carry_vector = merge_low_digit(
                state, multiplicand, merge_slot)
            if ((sum_vector + carry_vector) & mask) != exact:
                raise AssertionError("square reconstruction mismatch")
            prefix = "inner%d.merge%s" % (inner_slot, merge_slot)
            run = 0
            for position in range(cut - 1, -1, -1):
                if bit(sum_vector ^ carry_vector, position):
                    run += 1
                else:
                    break
            for threshold in range(1, 33):
                values[prefix + ".run.ge.%02d" % threshold] = (
                    run >= threshold)
            for width in range(1, 33):
                start = max(0, cut - width)
                for assumed in (0, 1):
                    values[prefix + ".rel%02d.c%d" % (width, assumed)] = (
                        carry_between(sum_vector, carry_vector, start, cut,
                                      assumed))
            for width in (2, 4, 8, 16, 32, 64):
                start = cut - (cut % width)
                for assumed in (0, 1):
                    values[prefix + ".abs%02d.c%d" % (width, assumed)] = (
                        carry_between(sum_vector, carry_vector, start, cut,
                                      assumed))
    return values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("features")
    parser.add_argument("positive_allmode")
    parser.add_argument("control_allmode")
    parser.add_argument("output")
    args = parser.parse_args()
    if os.path.exists(args.output):
        raise SystemExit("refusing to overwrite " + args.output)

    positive_delta = allmode_allowed(args.positive_allmode)
    control_delta = allmode_allowed(args.control_allmode)
    with open(args.features) as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    states = []
    feature_rows = []
    names = None
    for index, row in enumerate(rows):
        bank = positive_delta if row["label"] == "POS" else control_delta
        states.append(extract_carry_state(row, bank[row["op"]]))
        values = orientation_features(row)
        if names is None:
            names = sorted(values)
        elif set(values) != set(names):
            raise AssertionError("feature schema changed")
        feature_rows.append([values[name] for name in names])
        if (index + 1) % 2000 == 0:
            print("features", index + 1, "/", len(rows), flush=True)

    matrix = np.asarray(feature_rows, dtype=np.uint8)
    current = np.asarray([state[2] for state in states], dtype=np.uint8)
    allowed = np.asarray([[carry in state[3] for carry in (0, 1)]
                          for state in states], dtype=bool)
    capable = allowed.any(axis=1)
    positives = np.asarray([row["label"] == "POS" for row in rows])
    subsets = {
        "base": (~positives) & capable,
        "positive": positives & capable,
        "all": capable,
    }
    counts = {name: state_bad_counts(matrix, current, allowed, subset)
              for name, subset in subsets.items()}
    scores = []
    for gate in range(16):
        errors = {name: gate_errors(group, gate)
                  for name, group in counts.items()}
        changes = gate_changes(matrix, current, subsets["base"], gate)
        for feature, name in enumerate(names):
            scores.append((int(errors["all"][feature]),
                           int(errors["positive"][feature]),
                           int(errors["base"][feature]),
                           int(changes[feature]), GATE_NAMES[gate], gate,
                           name))
    scores.sort()

    with open(args.output, "w") as target:
        target.write("rows\t%d\nfeatures\t%d\ncarry_capable\t%d\n"
                     "carry_impossible\t%d\n" %
                     (len(rows), len(names), int(capable.sum()),
                      int((~capable).sum())))
        target.write("\n[gate ranking]\n")
        target.write("all_bad\tpositive_bad\tbase_bad\tbase_changes"
                     "\tgate\tgate_mask\tfeature\n")
        for score in scores[:1000]:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[best per orientation]\n")
        for inner_slot in range(4):
            for merge_slot in ("csa3", 0, 1, 2, 3):
                prefix = "inner%d.merge%s." % (inner_slot, merge_slot)
                scoped = [score for score in scores
                          if score[-1].startswith(prefix)]
                target.write("%d\t%s\t%s\n" %
                             (inner_slot, merge_slot,
                              "\t".join(map(str, scoped[0]))))

    print("wrote", args.output, "rows", len(rows), "features", len(names),
          "best", scores[0])


if __name__ == "__main__":
    main()
