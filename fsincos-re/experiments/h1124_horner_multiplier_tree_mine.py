#!/usr/bin/env python3
"""Mine redundant carry-save wires in the four Horner multiplications.

The two coefficient-leading products are 67x67 in the numeric model.  They
are represented as the literal Intel 67x64 radix-8 tree plus the omitted
low radix-8 digit, in both operand-port orientations.  The two following
products already have a 64-bit rounded Horner factor and therefore map
directly to the patent's 67x64 tree.  Features are circuit wires and local
conditional-carry endpoints only; no operand-space thresholds are learned.
"""

import argparse
import csv
import os

import numpy as np

from h1100_p5_multiplier_tree import TREE_MASK, csa3
from h1101_p5_tree_mine import (
    OFFSETS_FINAL, bit, cpa_carries, product_features,
)
from h1110_carry_gate_mine import (
    GATE_NAMES, allmode_allowed, extract_carry_state, gate_changes,
    gate_errors, state_bad_counts,
)
from h1123_horner_fadd_carry_mine import (
    CONSTANTS, DELTAS, decrement_wire_scores, equation_cached_counts,
    equation_signature_cache, fadd, multiply,
)


def carry_between(sum_vector, carry_vector, start, end, assumed):
    carry = assumed
    for position in range(max(0, start), end):
        a = bit(sum_vector, position)
        b = bit(carry_vector, position)
        carry = (a & b) | ((a ^ b) & carry)
    return carry


def full_product_features(prefix, x, y, main_state):
    exact = x * y
    cut = exact.bit_length() - 67
    sum_vector, carry_vector = csa3(
        (main_state["sum"] << 3) & TREE_MASK,
        (main_state["carry"] << 3) & TREE_MASK,
        x * (y & 7),
    )
    if ((sum_vector + carry_vector) & ((1 << 134) - 1)) != exact:
        raise AssertionError(prefix + " low-digit reconstruction mismatch")
    carries = cpa_carries(sum_vector, carry_vector, cut + 20)
    values = {}
    for offset in OFFSETS_FINAL:
        position = cut + offset
        sv = bit(sum_vector, position)
        cv = bit(carry_vector, position)
        values[prefix + ".sum.%+d" % offset] = sv
        values[prefix + ".carry.%+d" % offset] = cv
        values[prefix + ".p.%+d" % offset] = sv ^ cv
        values[prefix + ".g.%+d" % offset] = sv & cv
        values[prefix + ".kill.%+d" % offset] = 1 ^ (sv | cv)
        values[prefix + ".cin.%+d" % offset] = carries[position]
    run = 0
    for position in range(cut - 1, -1, -1):
        if bit(sum_vector ^ carry_vector, position):
            run += 1
        else:
            break
    for threshold in range(1, 33):
        values[prefix + ".run.ge.%02d" % threshold] = run >= threshold
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


def product67x67(prefix, x, y):
    values = {}
    for orientation, (multiplicand, multiplier) in enumerate(((x, y),
                                                               (y, x))):
        main, _, state = product_features(
            "%s.port%d.main" % (prefix, orientation),
            multiplicand, multiplier >> 3)
        values.update(main)
        values.update(full_product_features(
            "%s.port%d.full" % (prefix, orientation),
            multiplicand, multiplier, state))
    return values


def product67x64(prefix, multiplicand, multiplier, expected):
    values, cut, _ = product_features(prefix, multiplicand, multiplier)
    if (multiplicand * multiplier) >> cut != expected[2]:
        raise AssertionError(prefix + " chopped product mismatch")
    return values


def row_features(row):
    fourth = (int(row["tc_f4_sign"]), int(row["tc_f4_exp"]),
              int(row["tc_f4_sig"], 16))
    negative_product_1 = multiply(fourth, CONSTANTS[5])
    negative_1, _ = fadd("negative.add1", CONSTANTS[3],
                         negative_product_1)
    negative_product_2 = multiply(fourth, negative_1)
    negative_2, _ = fadd("negative.add2", CONSTANTS[1],
                         negative_product_2)
    positive_product_1 = multiply(fourth, CONSTANTS[6])
    positive_1, _ = fadd("positive.add1", CONSTANTS[4],
                         positive_product_1)
    positive_product_2 = multiply(fourth, positive_1)
    positive_2, _ = fadd("positive.add2", CONSTANTS[2],
                         positive_product_2)

    if negative_2[2] != int(row["tc_lf_sig"], 16):
        raise AssertionError("negative chain mismatch for " + row["op"])
    if positive_2[2] != int(row["tc_rf_sig"], 16):
        raise AssertionError("positive chain mismatch for " + row["op"])

    values = product67x67(
        "negative.mul1", fourth[2], CONSTANTS[5][2])
    values.update(product67x64(
        "negative.mul2", fourth[2], negative_1[2], negative_product_2))
    values.update(product67x67(
        "positive.mul1", fourth[2], CONSTANTS[6][2]))
    values.update(product67x64(
        "positive.mul2", fourth[2], positive_1[2], positive_product_2))
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

    with open(args.features) as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    positive_delta = allmode_allowed(args.positive_allmode)
    control_delta = allmode_allowed(args.control_allmode)
    states = []
    allowed_sets = []
    feature_rows = []
    names = None
    for index, row in enumerate(rows):
        allowed = (positive_delta if row["label"] == "POS"
                   else control_delta)[row["op"]]
        allowed_sets.append(allowed)
        states.append(extract_carry_state(row, allowed))
        values = row_features(row)
        if names is None:
            names = sorted(values)
        elif set(values) != set(names):
            raise AssertionError("feature schema changed")
        feature_rows.append([int(values[name]) for name in names])
        if (index + 1) % 2000 == 0:
            print("features", index + 1, "/", len(rows), flush=True)

    matrix = np.asarray(feature_rows, dtype=np.uint8)
    current = np.asarray([state[2] for state in states], dtype=np.uint8)
    borrow = np.asarray([state[0] for state in states], dtype=np.uint8)
    carry_allowed = np.asarray([
        [carry in state[3] for carry in (0, 1)]
        for state in states], dtype=bool)
    delta_allowed = np.asarray([
        [delta in allowed for delta in DELTAS]
        for allowed in allowed_sets], dtype=bool)
    positives = np.asarray([row["label"] == "POS" for row in rows])
    capable = carry_allowed.any(axis=1)
    carry_subsets = {
        "base": (~positives) & capable,
        "positive": positives & capable,
        "all": capable,
    }
    carry_counts = {
        name: state_bad_counts(matrix, current, carry_allowed, subset)
        for name, subset in carry_subsets.items()
    }
    carry_scores = []
    for gate in range(16):
        errors = {name: gate_errors(counts, gate)
                  for name, counts in carry_counts.items()}
        changes = gate_changes(matrix, current, carry_subsets["base"], gate)
        for feature, name in enumerate(names):
            carry_scores.append((
                int(errors["all"][feature]),
                int(errors["positive"][feature]),
                int(errors["base"][feature]),
                int(changes[feature]), GATE_NAMES[gate], gate, name,
            ))
    carry_scores.sort()

    signature_cache = equation_signature_cache(
        matrix, current, borrow, delta_allowed, positives)
    unified_scores = []
    for decrement_when in (0, 1):
        for gate in range(16):
            group, base_changes = equation_cached_counts(
                signature_cache, len(names), gate, decrement_when)
            for feature, name in enumerate(names):
                unified_scores.append((
                    int(group["all"][feature]),
                    int(group["positive"][feature]),
                    int(group["base"][feature]),
                    int(base_changes[feature]),
                    GATE_NAMES[gate], gate, decrement_when, name,
                ))
    unified_scores.sort()

    target_decrement = np.asarray([not state[3] for state in states])
    decrement_scores = decrement_wire_scores(
        matrix, target_decrement, positives, names)

    with open(args.output, "w") as target:
        target.write("rows\t%d\nfeatures\t%d\ncarry_capable\t%d\n"
                     "carry_impossible\t%d\n" % (
                         len(rows), len(names), int(capable.sum()),
                         int((~capable).sum())))
        target.write("\n[carry gate ranking]\n")
        target.write("all_bad\tpositive_bad\tbase_bad\tbase_changes"
                     "\tgate\tgate_mask\tfeature\n")
        for score in carry_scores[:1000]:
            target.write("\t".join(map(str, score)) + "\n")
        exact_carry = [score for score in carry_scores if score[0] == 0]
        target.write("\n[zero-error carry gates]\ncount\t%d\n" %
                     len(exact_carry))
        for score in exact_carry[:2000]:
            target.write("\t".join(map(str, score)) + "\n")

        target.write("\n[unified carry-plus-decrement ranking]\n")
        target.write("all_bad\tpositive_bad\tbase_bad\tbase_changes"
                     "\tgate\tgate_mask\tdecrement_when\tfeature\n")
        for score in unified_scores[:1000]:
            target.write("\t".join(map(str, score)) + "\n")
        exact_unified = [score for score in unified_scores if score[0] == 0]
        target.write("\n[zero-error unified equations]\ncount\t%d\n" %
                     len(exact_unified))
        for score in exact_unified[:2000]:
            target.write("\t".join(map(str, score)) + "\n")

        target.write("\n[standalone upstream-decrement wires]\n")
        target.write("all_bad\tpositive_bad\tbase_bad"
                     "\tdecrement_when\tfeature\n")
        for score in decrement_scores[:500]:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[carry-impossible rows]\n")
        for row, state in zip(rows, states):
            if not state[3]:
                target.write("%s\t%s\tborrow=%d\tcurrent_delta=%d\n" % (
                    row["op"], row["branch"], state[0], state[1]))

    print("wrote", args.output, "rows", len(rows), "features", len(names),
          "best_carry", carry_scores[0], "exact_carry", len(exact_carry),
          "best_unified", unified_scores[0],
          "exact_unified", len(exact_unified),
          "best_decrement", decrement_scores[0])


if __name__ == "__main__":
    main()
