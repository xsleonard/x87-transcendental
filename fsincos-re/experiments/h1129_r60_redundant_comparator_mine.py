#!/usr/bin/env python3
"""Test an R60 redundant-residue comparator for the R59 carry residual.

The scalar selector compares

    M = low3 * (mu - 2**66) - (mu*mu mod 2**s4)

against an integer multiple of 2**66.  This experiment keeps the square
residue as the literal P5 multiplier's redundant S/C pair and asks whether a
block-local carry into column 66 explains where the scalar comparison chooses
the wrong terminal carry.  It covers all 20 legal squarer orientations (four
inner 4:2 D slots times five low-digit merge choices).

The candidate signals are fixed carry recurrences, not learned numeric
thresholds.  Rows without an incumbent R60 threshold keep a zero mismatch so
that the experiment cannot silently alter the corner/q67 branches.
"""

import argparse
import csv
import os

import numpy as np

from h1100_p5_multiplier_tree import TREE_MASK, csa3, csa42, multiplier_tree
from h1110_carry_gate_mine import (
    GATE_NAMES, allmode_allowed, extract_carry_state, gate_changes,
    gate_errors, state_bad_counts,
)


WIDTH = 80
MASK = (1 << WIDTH) - 1
CUT = 66


def bit(value, position):
    return (value >> position) & 1 if 0 <= position < WIDTH else 0


def csa3w(a, b, c):
    return ((a ^ b ^ c) & MASK,
            (((a & b) | (a & c) | (b & c)) << 1) & MASK)


def reduce_balanced(rows):
    wires = [row & MASK for row in rows]
    while len(wires) > 2:
        output = []
        for start in range(0, len(wires), 3):
            group = wires[start:start + 3]
            if len(group) == 3:
                output.extend(csa3w(*group))
            else:
                output.extend(group)
        wires = output
    if len(wires) == 1:
        wires.append(0)
    if (sum(rows) - sum(wires)) & MASK:
        raise AssertionError("comparator CSA changed modular sum")
    return tuple(wires)


def negate_rows(rows):
    rows = [row & MASK for row in rows]
    return [((~row) & MASK) for row in rows] + [len(rows)]


def carry_between(sum_vector, carry_vector, start, end, assumed):
    carry = assumed
    for position in range(max(0, start), end):
        a = bit(sum_vector, position)
        b = bit(carry_vector, position)
        carry = (a & b) | (a & carry) | (b & carry)
    return carry


def less_with_carry(sum_vector, carry_vector, carry):
    high_width = WIDTH - CUT
    high_mask = (1 << high_width) - 1
    high = ((sum_vector >> CUT) + (carry_vector >> CUT) + carry) & high_mask
    return (high >> (high_width - 1)) & 1


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


def comparator_features(prefix, rows, exact_less):
    sum_vector, carry_vector = reduce_balanced(rows)
    values = {}
    exact_carry = carry_between(sum_vector, carry_vector, 0, CUT, 0)
    represented_less = less_with_carry(sum_vector, carry_vector, exact_carry)
    values[prefix + ".exact_carry"] = exact_carry
    values[prefix + ".represented_less"] = represented_less
    values[prefix + ".represented_mismatch"] = represented_less ^ exact_less

    for offset in range(-8, 5):
        position = CUT + offset
        a = bit(sum_vector, position)
        b = bit(carry_vector, position)
        values[prefix + ".propagate.%+d" % offset] = a ^ b
        values[prefix + ".generate.%+d" % offset] = a & b

    for width in (4, 6, 8, 10, 12, 16, 20, 24, 32):
        start = CUT - width
        for assumed in (0, 1):
            predicted_carry = carry_between(
                sum_vector, carry_vector, start, CUT, assumed)
            predicted_less = less_with_carry(
                sum_vector, carry_vector, predicted_carry)
            stem = prefix + ".rel%02d.c%d" % (width, assumed)
            values[stem + ".carry"] = predicted_carry
            values[stem + ".less"] = predicted_less
            values[stem + ".mismatch"] = predicted_less ^ exact_less
    for block_width in (4, 8, 16, 32):
        start = CUT - (CUT % block_width)
        for assumed in (0, 1):
            predicted_carry = carry_between(
                sum_vector, carry_vector, start, CUT, assumed)
            predicted_less = less_with_carry(
                sum_vector, carry_vector, predicted_carry)
            stem = prefix + ".abs%02d.c%d" % (block_width, assumed)
            values[stem + ".carry"] = predicted_carry
            values[stem + ".less"] = predicted_less
            values[stem + ".mismatch"] = predicted_less ^ exact_less
    return values


def active_row_features(row):
    # q67/corner branches do not expose an R60 u-threshold.  A zero feature
    # vector there makes every XOR-mismatch candidate leave them unchanged.
    if row.get("br_uu", "") in ("", None):
        return None
    multiplier = int(row["tc_mul_sig"], 16)
    low3 = int(row["low3"])
    sqlow = multiplier - (1 << 66)
    low_product = low3 * sqlow
    threshold = int(row["br_uu"]) << 66
    exact_m = signed128(row["Mreg"])
    exact_less = int(exact_m < threshold)
    s4 = int(row["s4"])
    residue_mask = (1 << s4) - 1
    exact_t4 = int(row["t4"], 16)

    values = comparator_features(
        "exact_t4", [low_product, (-exact_t4) & MASK,
                     (-threshold) & MASK], exact_less)
    for inner_slot in range(4):
        state = multiplier_tree(
            multiplier, multiplier >> 3, d_slot=inner_slot)
        for merge_slot in ("csa3", 0, 1, 2, 3):
            square_sum, square_carry = merge_low_digit(
                state, multiplier, merge_slot)
            square = multiplier * multiplier
            if ((square_sum + square_carry) & ((1 << 134) - 1)) != square:
                raise AssertionError("square reconstruction mismatch")
            sum_residue = square_sum & residue_mask
            carry_residue = square_carry & residue_mask
            residue_total = sum_residue + carry_residue
            if (residue_total & residue_mask) != exact_t4:
                raise AssertionError("square residue mismatch")
            overflow = residue_total >> s4
            tag = "inner%d.merge%s" % (inner_slot, merge_slot)

            raw_rows = [low_product]
            raw_rows.extend(negate_rows([sum_residue, carry_residue]))
            raw_rows.append((-threshold) & MASK)
            values.update(comparator_features(
                tag + ".raw", raw_rows, exact_less))

            corrected_rows = list(raw_rows)
            if overflow:
                corrected_rows.append(overflow << s4)
            values.update(comparator_features(
                tag + ".mod", corrected_rows, exact_less))
    return values


def signed128(text):
    value = int(text, 16)
    return value - (1 << 128) if value >> 127 else value


def read_tsv(path):
    with open(path) as source:
        return list(csv.DictReader(source, delimiter="\t"))


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
    rows = read_tsv(args.features)
    states = []
    matrix = None
    names = None
    eligible_count = 0
    for index, row in enumerate(rows):
        bank = positive_delta if row["label"] == "POS" else control_delta
        states.append(extract_carry_state(row, bank[row["op"]]))
        values = active_row_features(row)
        if values is not None:
            eligible_count += 1
        if names is None and values is not None:
            names = sorted(values)
            matrix = np.zeros((len(rows), len(names)), dtype=np.uint8)
        if values is not None:
            if set(values) != set(names):
                raise AssertionError("feature schema changed")
            matrix[index] = [values[name] for name in names]
        if (index + 1) % 1000 == 0:
            print("features", index + 1, "/", len(rows), flush=True)
    if names is None:
        raise RuntimeError("no R60-threshold rows")

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
    improvements = [score for score in scores
                    if score[2] == 0 and score[1] < 26]
    changing = [score for score in scores if score[1] < 26]

    with open(args.output, "w") as target:
        target.write("rows\t%d\neligible_threshold_rows\t%d\nfeatures\t%d\n"
                     "carry_capable\t%d\ncarry_impossible\t%d\n" %
                     (len(rows), eligible_count, len(names), int(capable.sum()),
                      int((~capable).sum())))
        target.write("\n[global ranking]\n")
        target.write("all_bad\tpositive_bad\tbase_bad\tbase_changes"
                     "\tgate\tgate_mask\tfeature\n")
        for score in scores[:500]:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[zero-collateral improvements]\ncount\t%d\n" %
                     len(improvements))
        for score in improvements[:2000]:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[best changing candidates]\ncount\t%d\n" % len(changing))
        for score in changing[:1000]:
            target.write("\t".join(map(str, score)) + "\n")
        exact = [score for score in scores if score[0] == 0]
        target.write("\n[zero-error gates]\ncount\t%d\n" % len(exact))
        for score in exact[:2000]:
            target.write("\t".join(map(str, score)) + "\n")
    print("wrote", args.output, "rows", len(rows), "eligible",
          eligible_count, "features", len(names), "best", scores[0],
          "zero_collateral_improvements", len(improvements),
          "zero_error", len(exact), flush=True)


if __name__ == "__main__":
    main()
