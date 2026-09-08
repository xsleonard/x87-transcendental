#!/usr/bin/env python3
"""Mine exact terminal carry/borrow prefix nodes against the R59 residual.

This is an isomorphism test, not a fitted correction.  R96 expresses its
selector as comparisons over reconstructed values.  Here the same aligned
terminal subtraction S-B is represented as an ordinary two's-complement
prefix network.  The candidate features are named generate/propagate nodes,
carry-select endpoints, and borrow nodes.  A direct match would therefore be
a plausible hardware wire, not an input-identity boundary or learned table.
"""

import argparse
import csv
import os

import numpy as np


WIDTH = 80
RELATIVE_BITS = range(-8, 25)
PREFIX_POSITIONS = range(-4, 17)
SPANS = (2, 4, 8, 16, 32, 64)


def bit(value, position):
    if position < 0:
        return 0
    return (value >> position) & 1


def combine_prefix(g_hi, p_hi, g_lo, p_lo):
    return g_hi | (p_hi & g_lo), p_hi & p_lo


def prefix_levels(generate, propagate):
    """Return inclusive power-of-two prefix nodes ending at every bit."""
    levels = {}
    current_g = list(generate)
    current_p = list(propagate)
    span = 1
    while span < WIDTH:
        next_g = list(current_g)
        next_p = list(current_p)
        for position in range(WIDTH):
            if position >= span:
                next_g[position], next_p[position] = combine_prefix(
                    current_g[position], current_p[position],
                    current_g[position - span], current_p[position - span])
        span *= 2
        levels[span] = (next_g, next_p)
        current_g, current_p = next_g, next_p
    return levels


def ripple_carries(generate, propagate, initial):
    carries = [initial]
    for position in range(len(generate)):
        carries.append(generate[position]
                       | (propagate[position] & carries[-1]))
    return carries


def add_features(values, prefix, vector, positions, cut):
    for offset in positions:
        position = cut + offset
        values["%s.rel.%+d" % (prefix, offset)] = (
            vector[position] if 0 <= position < len(vector) else 0)
    for position in range(0, 25):
        values["%s.abs.%02d" % (prefix, position)] = (
            vector[position] if position < len(vector) else 0)


def terminal_features(row):
    s_value = int(row["S"], 16)
    b_value = int(row["B"], 16)
    cut = int(row["k"])
    result_scale = int(row["rscale"])
    mask = (1 << WIDTH) - 1
    if s_value >= 1 << WIDTH or b_value >= 1 << WIDTH:
        raise AssertionError("terminal operand exceeds configured width")
    b_complement = (~b_value) & mask
    if ((s_value + b_complement + 1) & mask) != s_value - b_value:
        raise AssertionError("two's-complement subtraction mismatch")

    a_bits = [bit(s_value, position) for position in range(WIDTH)]
    b_bits = [bit(b_value, position) for position in range(WIDTH)]
    bn_bits = [1 ^ value for value in b_bits]

    # For addition of S + ~B + 1.  XOR propagation matches the ordinary
    # carry recurrence; OR propagation is also emitted because historical
    # Intel carry-generator descriptions use both conventions.
    add_g = [a & bn for a, bn in zip(a_bits, bn_bits)]
    add_px = [a ^ bn for a, bn in zip(a_bits, bn_bits)]
    add_po = [a | bn for a, bn in zip(a_bits, bn_bits)]
    add_k = [(1 ^ a) & (1 ^ bn) for a, bn in zip(a_bits, bn_bits)]
    carry_x = ripple_carries(add_g, add_px, 1)
    carry_o = ripple_carries(add_g, add_po, 1)
    if carry_x != carry_o:
        raise AssertionError("XOR/OR carry conventions disagree")

    # Direct borrow representation of S-B.  Equality propagates a borrow.
    borrow_g = [(1 ^ a) & b for a, b in zip(a_bits, b_bits)]
    borrow_p = [1 ^ (a ^ b) for a, b in zip(a_bits, b_bits)]
    borrows = ripple_carries(borrow_g, borrow_p, 0)

    values = {}
    base_vectors = {
        "a": a_bits,
        "b": b_bits,
        "bn": bn_bits,
        "add.g": add_g,
        "add.pxor": add_px,
        "add.por": add_po,
        "add.kill": add_k,
        "add.cin": carry_x[:-1],
        "add.cout": carry_x[1:],
        "borrow.g": borrow_g,
        "borrow.p": borrow_p,
        "borrow.bin": borrows[:-1],
        "borrow.bout": borrows[1:],
    }
    for name, vector in base_vectors.items():
        add_features(values, name, vector, RELATIVE_BITS, cut)

    for convention, propagate in (("xor", add_px), ("or", add_po)):
        for span, (node_g, node_p) in prefix_levels(
                add_g, propagate).items():
            if span not in SPANS:
                continue
            for offset in PREFIX_POSITIONS:
                position = cut + offset
                if position < 0:
                    group_g = 0
                    group_p = 0
                else:
                    group_g = node_g[position]
                    group_p = node_p[position]
                stem = "add.%s.span%02d.rel.%+d" % (
                    convention, span, offset)
                values[stem + ".g"] = group_g
                values[stem + ".p"] = group_p
                values[stem + ".c0"] = group_g
                values[stem + ".c1"] = group_g | group_p

    for span, (node_g, node_p) in prefix_levels(
            borrow_g, borrow_p).items():
        if span not in SPANS:
            continue
        for offset in PREFIX_POSITIONS:
            position = cut + offset
            if position < 0:
                group_g = 0
                group_p = 0
            else:
                group_g = node_g[position]
                group_p = node_p[position]
            stem = "borrow.span%02d.rel.%+d" % (span, offset)
            values[stem + ".g"] = group_g
            values[stem + ".p"] = group_p
            values[stem + ".b0"] = group_g
            values[stem + ".b1"] = group_g | group_p

    # Hardware-friendly local summaries at the discarded/retained cut.
    equality = [1 ^ (a ^ b) for a, b in zip(a_bits, b_bits)]
    run_down = 0
    position = cut
    while position >= 0 and equality[position]:
        run_down += 1
        position -= 1
    run_up = 0
    position = cut
    while position < WIDTH and equality[position]:
        run_up += 1
        position += 1
    for threshold in range(1, 33):
        values["equal.run_down.ge.%02d" % threshold] = (
            run_down >= threshold)
        values["equal.run_up.ge.%02d" % threshold] = (
            run_up >= threshold)

    # Carry-select blocks aligned both to the physical bit zero and to the
    # normalization cut.  Each feature is the exact block output under an
    # assumed carry/borrow input, the standard two-choice selector signal.
    for block_width in (2, 4, 8, 16):
        for offset in range(0, 17):
            end = cut + offset
            for alignment, start in (
                    ("abs", end - (end % block_width)),
                    ("cut", cut + (offset // block_width) * block_width)):
                if start > end:
                    continue
                start = max(0, start)
                add_c0 = 0
                add_c1 = 1
                borrow_b0 = 0
                borrow_b1 = 1
                for position in range(start, end + 1):
                    add_c0 = add_g[position] | (add_px[position] & add_c0)
                    add_c1 = add_g[position] | (add_px[position] & add_c1)
                    borrow_b0 = (borrow_g[position]
                                 | (borrow_p[position] & borrow_b0))
                    borrow_b1 = (borrow_g[position]
                                 | (borrow_p[position] & borrow_b1))
                stem = "%s.block%02d.end%+d" % (
                    alignment, block_width, offset)
                values[stem + ".add.c0"] = add_c0
                values[stem + ".add.c1"] = add_c1
                values[stem + ".borrow.b0"] = borrow_b0
                values[stem + ".borrow.b1"] = borrow_b1

    # Exponent-aligned carry-select blocks.  The observed R59 critical law
    # fixes the physical phase: bit ``cut`` has exponent result_scale+cut,
    # and block tops occur at exponent phase seven.  Earlier prefix mining
    # aligned blocks to the temporary integer's bit zero, which is not an
    # invariant hardware boundary when result_scale changes.
    for block_width in (4, 8, 16):
        phase = (result_scale + cut) % block_width
        cut_block_start = cut - phase
        for relative_block in range(-2, 3):
            start = cut_block_start + relative_block * block_width
            end = start + block_width
            stem = "phys.block%02d.rel%+d" % (
                block_width, relative_block)
            if start < 0 or end > WIDTH:
                for suffix in (
                        ".add.c0", ".add.c1", ".borrow.b0",
                        ".borrow.b1", ".add.cin", ".add.cout",
                        ".borrow.bin", ".borrow.bout", ".add.g",
                        ".add.p", ".borrow.g", ".borrow.p"):
                    values[stem + suffix] = 0
                continue
            add_c0 = ripple_carries(
                add_g[start:end], add_px[start:end], 0)[-1]
            add_c1 = ripple_carries(
                add_g[start:end], add_px[start:end], 1)[-1]
            borrow_b0 = ripple_carries(
                borrow_g[start:end], borrow_p[start:end], 0)[-1]
            borrow_b1 = ripple_carries(
                borrow_g[start:end], borrow_p[start:end], 1)[-1]
            values[stem + ".add.c0"] = add_c0
            values[stem + ".add.c1"] = add_c1
            values[stem + ".borrow.b0"] = borrow_b0
            values[stem + ".borrow.b1"] = borrow_b1
            values[stem + ".add.cin"] = carry_x[start]
            values[stem + ".add.cout"] = carry_x[end]
            values[stem + ".borrow.bin"] = borrows[start]
            values[stem + ".borrow.bout"] = borrows[end]
            values[stem + ".add.g"] = add_c0
            values[stem + ".add.p"] = add_c1 ^ add_c0
            values[stem + ".borrow.g"] = borrow_b0
            values[stem + ".borrow.p"] = borrow_b1 ^ borrow_b0

        # The conditional carry into the retained cut from the start of its
        # physical block, plus the carry out of the retained-side remainder.
        start = cut_block_start
        for assumed in (0, 1):
            stem = "phys.block%02d.cut.c%d" % (block_width, assumed)
            if 0 <= start <= cut:
                cin_cut = ripple_carries(
                    add_g[start:cut], add_px[start:cut], assumed)[-1]
                bout_cut = ripple_carries(
                    borrow_g[start:cut], borrow_p[start:cut], assumed)[-1]
                values[stem + ".add"] = cin_cut
                values[stem + ".borrow"] = bout_cut
            else:
                values[stem + ".add"] = 0
                values[stem + ".borrow"] = 0
        top = cut_block_start + block_width
        for assumed in (0, 1):
            stem = "phys.block%02d.top.c%d" % (block_width, assumed)
            if cut <= top <= WIDTH:
                cout_top = ripple_carries(
                    add_g[cut:top], add_px[cut:top], assumed)[-1]
                bout_top = ripple_carries(
                    borrow_g[cut:top], borrow_p[cut:top], assumed)[-1]
                values[stem + ".add"] = cout_top
                values[stem + ".borrow"] = bout_top
            else:
                values[stem + ".add"] = 0
                values[stem + ".borrow"] = 0
    return values


def endpoint_scores(matrix, subset, targets, names):
    count = int(subset.sum())
    if not count:
        return []
    selected = matrix[subset]
    truth = targets[subset]
    scores = []
    for index, name in enumerate(names):
        signal = selected[:, index].astype(bool)
        for plus1_when, prediction in ((1, signal), (0, ~signal)):
            errors = int(np.count_nonzero(prediction != truth))
            scores.append((errors, name, plus1_when))
    scores.sort()
    return scores


def anomaly_scores(matrix, positives, negatives, names):
    positive_count = int(positives.sum())
    negative_count = int(negatives.sum())
    if not positive_count or not negative_count:
        return []
    positive_true = matrix[positives].sum(axis=0, dtype=np.int64)
    negative_true = matrix[negatives].sum(axis=0, dtype=np.int64)
    scores = []
    for index, name in enumerate(names):
        for value, covered_positive, covered_negative in (
                (1, int(positive_true[index]), int(negative_true[index])),
                (0, positive_count - int(positive_true[index]),
                 negative_count - int(negative_true[index]))):
            if covered_positive < 2:
                continue
            scores.append((covered_negative / covered_positive,
                           covered_negative, -covered_positive, name, value))
    scores.sort()
    return scores


def emit_endpoint(target, title, scores, count, limit=40):
    target.write("\n[endpoint %s]\n" % title)
    target.write("rows\t%d\nerrors\tplus1_when\tfeature\n" % count)
    for errors, name, plus1_when in scores[:limit]:
        target.write("%d\t%d\t%s\n" % (errors, plus1_when, name))


def emit_anomaly(target, title, scores, limit=40):
    target.write("\n[anomaly %s]\n" % title)
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
        values = terminal_features(row)
        if names is None:
            names = sorted(values)
        elif set(values) != set(names):
            raise AssertionError("feature schema changed")
        feature_rows.append([values[name] for name in names])
        if (index + 1) % 5000 == 0:
            print("features", index + 1, "/", len(rows), flush=True)
    matrix = np.asarray(feature_rows, dtype=np.uint8)

    positives = np.asarray([row["label"] == "POS" for row in rows])
    plus1 = np.asarray([row["desired"] == "plus1" for row in rows])
    branches = np.asarray([row["branch"] for row in rows])
    cell_fields = ("mode", "branch", "theta", "ce", "s4", "side", "low3",
                   "dist", "rsh", "b1", "b2")
    positive_cells = {tuple(row[name] for name in cell_fields)
                      for row in rows if row["label"] == "POS"}
    in_positive_cell = np.asarray([
        tuple(row[name] for name in cell_fields) in positive_cells
        for row in rows])

    with open(args.output, "w") as target:
        target.write("rows\t%d\nfeatures\t%d\npositives\t%d\n"
                     "positive_cell_rows\t%d\n" %
                     (len(rows), len(names), int(positives.sum()),
                      int(in_positive_cell.sum())))
        all_rows = np.ones(len(rows), dtype=bool)
        emit_endpoint(target, "global",
                      endpoint_scores(matrix, all_rows, plus1, names),
                      len(rows))
        emit_endpoint(
            target, "inside positive exact cells",
            endpoint_scores(matrix, in_positive_cell, plus1, names),
            int(in_positive_cell.sum()))
        emit_anomaly(target, "POS versus all NEG",
                     anomaly_scores(matrix, positives, ~positives, names))
        emit_anomaly(
            target, "POS versus NEG inside positive exact cells",
            anomaly_scores(matrix, positives,
                           (~positives) & in_positive_cell, names))

        for branch in sorted(set(branches)):
            in_branch = branches == branch
            emit_endpoint(
                target, "branch=%s" % branch,
                endpoint_scores(matrix, in_branch, plus1, names),
                int(in_branch.sum()))
            emit_endpoint(
                target, "branch=%s positive exact cells" % branch,
                endpoint_scores(
                    matrix, in_branch & in_positive_cell, plus1, names),
                int((in_branch & in_positive_cell).sum()))
            emit_anomaly(
                target, "branch=%s positive exact cells" % branch,
                anomaly_scores(matrix, positives & in_branch,
                               (~positives) & in_branch & in_positive_cell,
                               names))

    print("wrote", args.output, "rows", len(rows),
          "features", len(names))


if __name__ == "__main__":
    main()
