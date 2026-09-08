#!/usr/bin/env python3
"""Retest the fused-terminal CSA hypothesis on the exact R59 corpus.

h993 explored generic live-FMUL carry-save pairs before the residual had an
all-mode one-bit formulation.  This stricter test uses the literal P5 67x64
radix-8/4:2 multiplier, all four distinguished-D orientations, the exact
26-carry/3-upstream labels, and 34,464 carry-forbidden controls.

Each representation is an arithmetic isomorphism, not an operand partition:
the two terminal products, subtraction, and payload are carried as redundant
rows and reduced by a fixed balanced CSA recurrence.  Signals are local
sum/carry, propagate/generate, and conditional carry endpoints at the retained
cut.  The search tests every two-input Boolean gate with the incumbent carry;
it never introduces a numeric input threshold or an operand identity.
"""

import argparse
import csv
import os

import numpy as np

from h1100_p5_multiplier_tree import (
    PRODUCT_MASK, multiplier_tree,
)
from h1110_carry_gate_mine import (
    GATE_NAMES, allmode_allowed, extract_carry_state, gate_changes,
    gate_errors, state_bad_counts,
)


WIDTH = 224
MASK = (1 << WIDTH) - 1
BIT_OFFSETS = range(-12, 9)
RELATIVE_WIDTHS = range(1, 25)
BLOCK_WIDTHS = (4, 8, 16)


def bit(value, position):
    return (value >> position) & 1 if 0 <= position < WIDTH else 0


def csa3(a, b, c):
    total_sum = (a ^ b ^ c) & MASK
    carry = (((a & b) | (a & c) | (b & c)) << 1) & MASK
    return total_sum, carry


def reduce_balanced(rows):
    """Balanced 3:2 compression; preserve every intermediate level."""
    wires = [row & MASK for row in rows]
    if not wires:
        return 0, 0, []
    if len(wires) == 1:
        return wires[0], 0, []
    levels = []
    while len(wires) > 2:
        output = []
        nodes = []
        for start in range(0, len(wires), 3):
            group = wires[start:start + 3]
            if len(group) == 3:
                sum_vector, carry_vector = csa3(*group)
                output.extend((sum_vector, carry_vector))
                nodes.append((sum_vector, carry_vector))
            else:
                output.extend(group)
        levels.append(tuple(nodes))
        wires = output
    if (sum(rows) - sum(wires)) & MASK:
        raise AssertionError("CSA reduction changed the modular sum")
    return wires[0], wires[1], levels


def negate_rows(rows):
    """Negate a redundant row collection modulo 2**WIDTH."""
    rows = [row & MASK for row in rows]
    return [((~row) & MASK) for row in rows] + [len(rows)]


def shift_wire(value, shift):
    if shift >= 0:
        return (value << shift) & MASK
    return (value >> -shift) & MASK


def product_state(multiplicand, multiplier, d_slot):
    exact = multiplicand * multiplier
    cut = exact.bit_length() - 67
    state = multiplier_tree(multiplicand, multiplier, d_slot=d_slot)
    sum_vector = state["sum"] & PRODUCT_MASK
    carry_vector = state["carry"] & PRODUCT_MASK
    if ((sum_vector + carry_vector) & PRODUCT_MASK) != exact:
        raise AssertionError("literal multiplier reconstruction mismatch")
    raw = [value & PRODUCT_MASK for value in state["rows"]]
    raw.append(state["w"] & PRODUCT_MASK)
    if sum(raw) & PRODUCT_MASK != exact:
        raise AssertionError("literal multiplier input-row mismatch")
    return {
        "sum": sum_vector, "carry": carry_vector, "raw": raw,
        "cut": cut, "exact": exact,
    }


def terminal_rows(row):
    multiplier = int(row["tc_mul_sig"], 16)
    left_factor = int(row["tc_lf_sig"], 16)
    fourth = int(row["tc_f4_sig"], 16)
    right_factor = int(row["tc_rf_sig"], 16)
    left_e2 = int(row["tc_left_exp"])
    right_e2 = int(row["tc_right_exp"])
    left_base = int(row["tc_mul_exp"]) + int(row["tc_lf_exp"])
    right_base = int(row["tc_f4_exp"]) + int(row["tc_rf_exp"])
    rscale = int(row["rscale"])
    payload = int(row["payload"])
    payload_e2 = left_e2 - 8
    cut_exponent = rscale + int(row["k"])

    product_cache = {}
    for d_slot in range(4):
        product_cache["L", d_slot] = product_state(
            multiplier, left_factor, d_slot)
        product_cache["R", d_slot] = product_state(
            fourth, right_factor, d_slot)

    representations = {}

    # Materialized terminal, included as a control for the feature machinery.
    mat_left = int(row["tc_left_sig"], 16) << int(row["dl"])
    mat_right = int(row["tc_right_sig"], 16) << int(row["dr"])
    mat_rows = [mat_left]
    if payload:
        mat_rows.append(payload << int(row["dp"]))
    mat_rows.extend(negate_rows([mat_right]))
    representations["materialized"] = (mat_rows, rscale, int(row["k"]))

    for d_slot in range(4):
        left = product_cache["L", d_slot]
        right = product_cache["R", d_slot]

        # Independent 67-bit chops, but without resolving each product's
        # incoming cut carry before the terminal sees its two live vectors.
        left_chop = [shift_wire(left[name], -left["cut"] + int(row["dl"]))
                     for name in ("sum", "carry")]
        right_chop = [shift_wire(right[name], -right["cut"] + int(row["dr"]))
                      for name in ("sum", "carry")]
        rows_chop = list(left_chop)
        if payload:
            rows_chop.append(payload << int(row["dp"]))
        rows_chop.extend(negate_rows(right_chop))
        representations["pair_chop.d%d" % d_slot] = (
            rows_chop, rscale, int(row["k"]))

        # Align the unresolved final multiplier vectors directly to the
        # materialized terminal scale.  Low columns are killed per wire,
        # allowing the missing cross-wire carry to become visible.
        left_align = [shift_wire(left[name], left_base - rscale)
                      for name in ("sum", "carry")]
        right_align = [shift_wire(right[name], right_base - rscale)
                       for name in ("sum", "carry")]
        rows_align = list(left_align)
        if payload:
            rows_align.append(payload << (payload_e2 - rscale))
        rows_align.extend(negate_rows(right_align))
        representations["pair_align.d%d" % d_slot] = (
            rows_align, rscale, int(row["k"]))

        # Preserve every exact product column at a shared fine scale.  This
        # is the literal-tree version of h993's full live-CSA hypothesis.
        fine = min(left_base, right_base,
                   payload_e2 if payload else left_base)
        left_fine = [shift_wire(left[name], left_base - fine)
                     for name in ("sum", "carry")]
        right_fine = [shift_wire(right[name], right_base - fine)
                      for name in ("sum", "carry")]
        rows_fine = list(left_fine)
        if payload:
            rows_fine.append(payload << (payload_e2 - fine))
        rows_fine.extend(negate_rows(right_fine))
        representations["pair_fine.d%d" % d_slot] = (
            rows_fine, fine, cut_exponent - fine)

    # The most aggressive fusion: align the 23 physical inputs of each
    # multiplier before any product-local reduction.
    left = product_cache["L", 0]
    right = product_cache["R", 0]
    left_raw_align = [shift_wire(value, left_base - rscale)
                      for value in left["raw"]]
    right_raw_align = [shift_wire(value, right_base - rscale)
                       for value in right["raw"]]
    rows_raw_align = list(left_raw_align)
    if payload:
        rows_raw_align.append(payload << (payload_e2 - rscale))
    rows_raw_align.extend(negate_rows(right_raw_align))
    representations["raw_align"] = (
        rows_raw_align, rscale, int(row["k"]))

    fine = min(left_base, right_base, payload_e2 if payload else left_base)
    left_raw_fine = [shift_wire(value, left_base - fine)
                     for value in left["raw"]]
    right_raw_fine = [shift_wire(value, right_base - fine)
                      for value in right["raw"]]
    rows_raw_fine = list(left_raw_fine)
    if payload:
        rows_raw_fine.append(payload << (payload_e2 - fine))
    rows_raw_fine.extend(negate_rows(right_raw_fine))
    representations["raw_fine"] = (
        rows_raw_fine, fine, cut_exponent - fine)
    return representations


def carry_between(sum_vector, carry_vector, start, end, assumed):
    carry = assumed
    for position in range(max(0, start), end):
        a = bit(sum_vector, position)
        b = bit(carry_vector, position)
        carry = (a & b) | (a & carry) | (b & carry)
    return carry


def representation_features(prefix, rows, scale, cut):
    if not 0 < cut < WIDTH:
        raise AssertionError("invalid retained cut")
    sum_vector, carry_vector, levels = reduce_balanced(rows)
    values = {}
    for offset in BIT_OFFSETS:
        position = cut + offset
        a = bit(sum_vector, position)
        b = bit(carry_vector, position)
        values[prefix + ".sum.%+d" % offset] = a
        values[prefix + ".carry.%+d" % offset] = b
        values[prefix + ".propagate.%+d" % offset] = a ^ b
        values[prefix + ".generate.%+d" % offset] = a & b
    for width in RELATIVE_WIDTHS:
        start = max(0, cut - width)
        for assumed in (0, 1):
            values[prefix + ".rel%02d.c%d" % (width, assumed)] = (
                carry_between(sum_vector, carry_vector, start, cut, assumed))
    for width in BLOCK_WIDTHS:
        phase = (scale + cut) % width
        start = max(0, cut - phase)
        for assumed in (0, 1):
            values[prefix + ".phys%02d.c%d" % (width, assumed)] = (
                carry_between(sum_vector, carry_vector, start, cut, assumed))
    values[prefix + ".exact_cin"] = carry_between(
        sum_vector, carry_vector, 0, cut, 0)
    run_below = 0
    while cut - 1 - run_below >= 0 \
            and bit(sum_vector ^ carry_vector, cut - 1 - run_below):
        run_below += 1
    run_above = 0
    while cut + run_above < WIDTH \
            and bit(sum_vector ^ carry_vector, cut + run_above):
        run_above += 1
    for threshold in range(1, 17):
        values[prefix + ".run_below.ge.%02d" % threshold] = (
            run_below >= threshold)
        values[prefix + ".run_above.ge.%02d" % threshold] = (
            run_above >= threshold)

    # The last compressor level is a physically named recurrence state, not
    # a scalar operand boundary.  It is useful when the final S/C pair alone
    # has already absorbed the distinguishing carry.
    if levels and levels[-1]:
        node_sum, node_carry = levels[-1][-1]
        for offset in range(-8, 5):
            position = cut + offset
            values[prefix + ".last.sum.%+d" % offset] = bit(
                node_sum, position)
            values[prefix + ".last.carry.%+d" % offset] = bit(
                node_carry, position)
    else:
        for offset in range(-8, 5):
            values[prefix + ".last.sum.%+d" % offset] = 0
            values[prefix + ".last.carry.%+d" % offset] = 0
    return values


def row_features(row):
    values = {}
    for name, (rows, scale, cut) in terminal_rows(row).items():
        values.update(representation_features(name, rows, scale, cut))
    return values


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
    for index, row in enumerate(rows):
        bank = positive_delta if row["label"] == "POS" else control_delta
        states.append(extract_carry_state(row, bank[row["op"]]))
        values = row_features(row)
        if names is None:
            names = sorted(values)
            matrix = np.empty((len(rows), len(names)), dtype=np.uint8)
        elif set(values) != set(names):
            raise AssertionError("feature schema changed")
        matrix[index] = [values[name] for name in names]
        if (index + 1) % 2000 == 0:
            print("features", index + 1, "/", len(rows), flush=True)

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

    representations = sorted({name.split(".", 1)[0] for name in names})
    with open(args.output, "w") as target:
        target.write("rows\t%d\nfeatures\t%d\nrepresentations\t%d\n"
                     "carry_capable\t%d\ncarry_impossible\t%d\n" %
                     (len(rows), len(names), len(representations),
                      int(capable.sum()), int((~capable).sum())))
        target.write("\n[global gate ranking]\n")
        target.write("all_bad\tpositive_bad\tbase_bad\tbase_changes"
                     "\tgate\tgate_mask\tfeature\n")
        for score in scores[:1000]:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[best per representation]\n")
        target.write("representation\tall_bad\tpositive_bad\tbase_bad"
                     "\tbase_changes\tgate\tgate_mask\tfeature\n")
        for representation in representations:
            scoped = [score for score in scores
                      if score[-1].startswith(representation + ".")]
            target.write(representation + "\t"
                         + "\t".join(map(str, scoped[0])) + "\n")
        target.write("\n[best nonidentity per representation]\n")
        target.write("representation\tall_bad\tpositive_bad\tbase_bad"
                     "\tbase_changes\tgate\tgate_mask\tfeature\n")
        for representation in representations:
            scoped = [score for score in scores
                      if score[5] != 0xC
                      and score[-1].startswith(representation + ".")]
            target.write(representation + "\t"
                         + "\t".join(map(str, scoped[0])) + "\n")
        target.write("\n[zero-collateral improvements]\n")
        improvements = [score for score in scores
                        if score[2] == 0 and score[1] < 26
                        and score[5] != 0xC]
        target.write("count\t%d\n" % len(improvements))
        for score in improvements[:2000]:
            target.write("\t".join(map(str, score)) + "\n")
        exact = [score for score in scores if score[0] == 0]
        target.write("\n[zero-error gates]\ncount\t%d\n" % len(exact))
        for score in exact[:2000]:
            target.write("\t".join(map(str, score)) + "\n")

        best = scores[0]
        best_gate, best_name = best[5], best[6]
        best_column = names.index(best_name)
        target.write("\n[best-gate residual details]\n")
        target.write("op\tbranch\tcurrent\tfeature\tpredicted"
                     "\tallowed\tstatus\n")
        for index, (row, state) in enumerate(zip(rows, states)):
            if row["label"] != "POS" or not state[3]:
                continue
            feature_value = int(matrix[index, best_column])
            predicted = ((best_gate
                          >> (2 * int(current[index]) + feature_value)) & 1)
            target.write("%s\t%s\t%d\t%d\t%d\t%s\t%s\n" % (
                row["op"], row["branch"], int(current[index]),
                feature_value, predicted,
                ",".join(map(str, sorted(state[3]))),
                "OK" if predicted in state[3] else "MISS"))
        target.write("best\t%s\n" % ("\t".join(map(str, best))))
    print("wrote", args.output, "rows", len(rows), "features", len(names),
          "representations", len(representations), "best", scores[0],
          "zero_error", len(exact), flush=True)


if __name__ == "__main__":
    main()
