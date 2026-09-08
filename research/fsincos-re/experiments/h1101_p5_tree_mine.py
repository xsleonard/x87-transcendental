#!/usr/bin/env python3
"""Mine literal P5 multiplier-tree signals against the residual R59 set.

This is a diagnostic, not a fitted correction.  It asks whether a named
wire or local carry-chain property in the Intel US 5,195,051 multiplier
separates current R59 misses from already-exact endpoint-visible controls.
"""

import argparse
import csv
import os

import numpy as np

from h1100_p5_multiplier_tree import TREE_MASK, csa3, multiplier_tree


OFFSETS_FINAL = range(-32, 17)
OFFSETS_NODE = range(-8, 5)
NODE_VECTORS = ("sum", "carry", "first_sum", "first_carry")


def bit(value, position):
    return (value >> position) & 1 if position >= 0 else 0


def cpa_carries(sum_vector, carry_vector, through):
    carry = 0
    result = []
    for position in range(through + 1):
        result.append(carry)
        a = bit(sum_vector, position)
        b = bit(carry_vector, position)
        carry = (a & b) | (a & carry) | (b & carry)
    return result


def carry_between(sum_vector, carry_vector, start, end, assumed):
    """Carry into ``end`` from a conditional carry at ``start``."""
    carry = assumed
    for position in range(max(0, start), end):
        a = bit(sum_vector, position)
        b = bit(carry_vector, position)
        carry = (a & b) | (a & carry) | (b & carry)
    return carry


def product_features(prefix, multiplicand, multiplier):
    state = multiplier_tree(multiplicand, multiplier)
    product = multiplicand * multiplier
    cut = product.bit_length() - 67
    if cut not in (63, 64):
        raise AssertionError("unexpected product cut %d" % cut)
    final_sum = state["sum"]
    final_carry = state["carry"]
    carries = cpa_carries(final_sum, final_carry, cut + 20)
    values = {}
    for offset in OFFSETS_FINAL:
        position = cut + offset
        sum_bit = bit(final_sum, position)
        carry_bit = bit(final_carry, position)
        values["%s.final.sum.%+d" % (prefix, offset)] = sum_bit
        values["%s.final.carry.%+d" % (prefix, offset)] = carry_bit
        values["%s.final.propagate.%+d" % (prefix, offset)] = (
            sum_bit ^ carry_bit)
        values["%s.final.generate.%+d" % (prefix, offset)] = (
            sum_bit & carry_bit)
        values["%s.final.kill.%+d" % (prefix, offset)] = (
            1 ^ (sum_bit | carry_bit))
        values["%s.final.cin.%+d" % (prefix, offset)] = carries[position]
    for node_name, node in state["nodes"].items():
        for vector_name in NODE_VECTORS:
            vector = node[vector_name]
            for offset in OFFSETS_NODE:
                values["%s.%s.%s.%+d" % (
                    prefix, node_name, vector_name, offset)] = bit(
                        vector, cut + offset)
    digits = state["digits"]
    for row, digit in enumerate(digits):
        values["%s.booth.neg.%02d" % (prefix, row)] = digit < 0
        values["%s.booth.zero.%02d" % (prefix, row)] = digit == 0
        values["%s.booth.abs3.%02d" % (prefix, row)] = abs(digit) == 3

    # Named local carry-chain summaries.  These remain circuit properties:
    # each threshold means that the final CPA's P line is asserted in every
    # one of the indicated consecutive columns immediately below the cut.
    run = 0
    for position in range(cut - 1, -1, -1):
        if bit(final_sum ^ final_carry, position):
            run += 1
        else:
            break
    for threshold in range(1, 33):
        values["%s.final.run_below.ge.%02d" % (prefix, threshold)] = (
            run >= threshold)
    return values, cut, state


def row_features(row):
    left_x = int(row["tc_mul_sig"], 16)
    left_y = int(row["tc_lf_sig"], 16)
    right_x = int(row["tc_f4_sig"], 16)
    right_y = int(row["tc_rf_sig"], 16)
    square_x = int(row["tc_mul_sig"], 16)
    # The physical multiplier has a 67-bit multiplicand port and a 64-bit
    # multiplier port.  A 67-bit internal square therefore enters the latter
    # as its upper 64 bits; its low radix-8 digit is the separate low3 term
    # whose carry interaction R59 reconstructs.
    square_y = square_x >> 3
    left, left_cut, left_state = product_features("L", left_x, left_y)
    right, right_cut, right_state = product_features("R", right_x, right_y)
    square, square_cut, square_state = product_features(
        "Q", square_x, square_y)
    if (left_x * left_y) >> left_cut != int(row["tc_left_sig"], 16):
        raise AssertionError("left product/chop mismatch for " + row["op"])
    if (right_x * right_y) >> right_cut != int(row["tc_right_sig"], 16):
        raise AssertionError("right product/chop mismatch for " + row["op"])
    square_full = square_x * square_x
    square_full_cut = square_full.bit_length() - 67
    if square_full >> square_full_cut != int(row["tc_f4_sig"], 16):
        raise AssertionError("square product/chop mismatch for " + row["op"])
    values = left
    values.update(right)
    values.update(square)
    # Reinsert the external radix-8 low digit through one 3:2 compression.
    # QX is an isomorphic redundant representation of the exact square; its
    # final S/C wires are the natural place for a carry-predict anomaly.
    low_product = square_x * (square_x & 7)
    square_sum, square_carry = csa3(
        (square_state["sum"] << 3) & TREE_MASK,
        (square_state["carry"] << 3) & TREE_MASK,
        low_product)
    square_mask = (1 << 134) - 1
    if ((square_sum + square_carry) & square_mask) != square_full:
        raise AssertionError("redundant square reconstruction mismatch for "
                             + row["op"])
    square_carries = cpa_carries(
        square_sum, square_carry, square_full_cut + 20)
    for offset in OFFSETS_FINAL:
        position = square_full_cut + offset
        sum_bit = bit(square_sum, position)
        carry_bit = bit(square_carry, position)
        values["QX.final.sum.%+d" % offset] = sum_bit
        values["QX.final.carry.%+d" % offset] = carry_bit
        values["QX.final.propagate.%+d" % offset] = sum_bit ^ carry_bit
        values["QX.final.generate.%+d" % offset] = sum_bit & carry_bit
        values["QX.final.kill.%+d" % offset] = 1 ^ (sum_bit | carry_bit)
        values["QX.final.cin.%+d" % offset] = square_carries[position]
    square_run = 0
    for position in range(square_full_cut - 1, -1, -1):
        if bit(square_sum ^ square_carry, position):
            square_run += 1
        else:
            break
    for threshold in range(1, 33):
        values["QX.final.run_below.ge.%02d" % threshold] = (
            square_run >= threshold)
    # Conditional-carry endpoints at the exact square-product cut.  These
    # are the two physical answers a carry-select block computes before its
    # incoming carry is known.  Emit both cut-relative windows and ordinary
    # power-of-two block alignments; neither construction examines labels or
    # operand-space boundaries.
    for width in range(1, 33):
        start = max(0, square_full_cut - width)
        for assumed in (0, 1):
            values["QX.cond.rel%02d.c%d" % (width, assumed)] = (
                carry_between(square_sum, square_carry, start,
                              square_full_cut, assumed))
    for width in (2, 4, 8, 16, 32, 64):
        start = square_full_cut - (square_full_cut % width)
        for assumed in (0, 1):
            values["QX.cond.abs%02d.c%d" % (width, assumed)] = (
                carry_between(square_sum, square_carry, start,
                              square_full_cut, assumed))
    # The final terminal is a subtraction.  XORs expose paired physical
    # wires without inventing an operand-value threshold.
    for offset in OFFSETS_FINAL:
        for signal in ("sum", "carry", "propagate", "generate", "cin"):
            lname = "L.final.%s.%+d" % (signal, offset)
            rname = "R.final.%s.%+d" % (signal, offset)
            values["LR.final.%s.xor.%+d" % (signal, offset)] = (
                values[lname] ^ values[rname])
            values["LR.final.%s.and.%+d" % (signal, offset)] = (
                values[lname] & values[rname])
    return values


def orientation_scores(matrix, subset_pos, subset_neg, names):
    pos_count = int(subset_pos.sum())
    neg_count = int(subset_neg.sum())
    if not pos_count or not neg_count:
        return []
    pos_true = matrix[subset_pos].sum(axis=0, dtype=np.int64)
    neg_true = matrix[subset_neg].sum(axis=0, dtype=np.int64)
    scores = []
    for index, name in enumerate(names):
        for value, covered_pos, covered_neg in (
                (1, int(pos_true[index]), int(neg_true[index])),
                (0, pos_count - int(pos_true[index]),
                 neg_count - int(neg_true[index]))):
            if covered_pos < 2:
                continue
            scores.append((covered_neg / covered_pos, covered_neg,
                           -covered_pos, name, value))
    scores.sort()
    return scores


def emit_ranking(target, title, scores, limit=40):
    target.write("\n[%s]\n" % title)
    target.write("neg_per_pos\tneg\tpos\tvalue\tfeature\n")
    for ratio, neg, minus_pos, name, value in scores[:limit]:
        target.write("%.6f\t%d\t%d\t%d\t%s\n" %
                     (ratio, neg, -minus_pos, value, name))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("output")
    args = parser.parse_args()
    if os.path.exists(args.output):
        raise SystemExit("refusing to overwrite " + args.output)
    with open(args.input) as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    feature_rows = []
    names = None
    for index, row in enumerate(rows):
        values = row_features(row)
        if names is None:
            names = sorted(values)
        elif set(values) != set(names):
            raise AssertionError("feature schema changed")
        feature_rows.append([values[name] for name in names])
        if (index + 1) % 5000 == 0:
            print("features", index + 1, "/", len(rows), flush=True)
    matrix = np.asarray(feature_rows, dtype=np.uint8)
    labels = np.asarray([row["label"] == "POS" for row in rows])
    branches = np.asarray([row["branch"] for row in rows])
    desired = np.asarray([row["desired"] for row in rows])
    cell_fields = ("branch", "theta", "ce", "s4", "side", "low3",
                   "dist", "rsh", "b1", "b2")
    positive_cells = {tuple(row[name] for name in cell_fields)
                      for row in rows if row["label"] == "POS"}
    in_positive_cell = np.asarray([
        tuple(row[name] for name in cell_fields) in positive_cells
        for row in rows])

    with open(args.output, "w") as target:
        target.write("rows\t%d\nfeatures\t%d\npositives\t%d\n" %
                     (len(rows), len(names), int(labels.sum())))
        emit_ranking(target, "global POS versus NEG",
                     orientation_scores(matrix, labels, ~labels, names))
        emit_ranking(target, "POS versus NEG inside positive exact cells",
                     orientation_scores(matrix, labels,
                                        (~labels) & in_positive_cell, names))
        for branch in sorted(set(branches)):
            in_branch = branches == branch
            emit_ranking(target, "branch=%s" % branch,
                         orientation_scores(matrix, labels & in_branch,
                                            (~labels) & in_branch, names))
            emit_ranking(target, "branch=%s positive exact cells" % branch,
                         orientation_scores(
                             matrix, labels & in_branch,
                             (~labels) & in_branch & in_positive_cell,
                             names))
        for branch in sorted(set(branches)):
            for endpoint in sorted(set(desired)):
                stratum = (branches == branch) & (desired == endpoint)
                emit_ranking(target, "branch=%s desired=%s" %
                             (branch, endpoint),
                             orientation_scores(matrix, labels & stratum,
                                                (~labels) & stratum, names),
                             limit=20)

        target.write("\n[positive rows: final-tree boundary words]\n")
        columns = ["op", "branch", "desired", "theta", "ce", "s4",
                   "side", "low3", "dist", "rsh", "b1", "b2"]
        signal_names = []
        for prefix in ("L", "R"):
            for signal in ("sum", "carry", "propagate", "cin"):
                signal_names.extend("%s.final.%s.%+d" %
                                    (prefix, signal, offset)
                                    for offset in range(-8, 5))
        target.write("\t".join(columns + signal_names) + "\n")
        for row_index, row in enumerate(rows):
            if not labels[row_index]:
                continue
            packed = []
            for name in signal_names:
                packed.append(str(int(matrix[row_index, names.index(name)])))
            target.write("\t".join([row[column] for column in columns] +
                                   packed) + "\n")
    print("wrote", args.output, "rows", len(rows), "features", len(names))


if __name__ == "__main__":
    main()
