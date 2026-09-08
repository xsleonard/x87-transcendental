#!/usr/bin/env python3
"""Mine pre-materialization Horner FADD wires for the R59 residual.

The terminal feature banks contain only the rounded ``negative`` and
``positive`` polynomial factors.  A literal dual-adder implementation also
has operand-add carry, rounding-carry, sticky-scanner, and conditional-carry
signals immediately before each factor is materialized.  This experiment
reconstructs those named signals for the four same-sign Horner additions and
tests the exact structural equation

    delta = borrow_terminal - 1 + gate(c_incumbent, wire) - decrement(wire).

The optional decrement is included because three residual operands cannot be
represented by either terminal carry value.  No input identity, learned
numeric boundary, or hardware label is used to construct a feature.
"""

import argparse
import csv
import os

import numpy as np

from h1110_carry_gate_mine import (
    GATE_NAMES, allmode_allowed, extract_carry_state,
)


CONSTANTS = {
    1: (1, -68, (0x7 << 64) | 0xfffffffffffffffe),
    2: (0, -71, (0x5 << 64) | 0x5555555555554277),
    3: (1, -76, (0x5 << 64) | 0xb05b05b05a18a1ba),
    4: (0, -82, (0x6 << 64) | 0x80680675b559f2cf),
    5: (1, -88, (0x4 << 64) | 0x9f93af61f5349300),
    6: (0, -95, (0x4 << 64) | 0x7a4f2483514c1af8),
}
RELATIVE = range(-16, 17)
DELTAS = range(-2, 3)


def bit(value, position):
    return (value >> position) & 1 if position >= 0 else 0


def round_word(sign, magnitude, scale, bits, nearest):
    if not magnitude:
        return 0, 0, 0
    shift = magnitude.bit_length() - bits
    if shift <= 0:
        return sign, scale + shift, magnitude << -shift
    top = magnitude >> shift
    guard = bit(magnitude, shift - 1)
    sticky = bool(magnitude & ((1 << (shift - 1)) - 1)) \
        if shift > 1 else False
    if nearest and guard and (sticky or (top & 1)):
        top += 1
        if top == 1 << bits:
            top >>= 1
            shift += 1
    return sign, scale + shift, top


def multiply(left, right):
    return round_word(left[0] ^ right[0], left[2] * right[2],
                      left[1] + right[1], 67, False)


def ripple_carries(left, right, through, assumed=0, start=0):
    carry = assumed
    result = {start: carry}
    for position in range(start, through):
        a = bit(left, position)
        b = bit(right, position)
        carry = (a & b) | ((a ^ b) & carry)
        result[position + 1] = carry
    return result


def conditional_carry(left, right, start, end, assumed):
    carry = assumed
    for position in range(max(0, start), end):
        a = bit(left, position)
        b = bit(right, position)
        carry = (a & b) | ((a ^ b) & carry)
    return carry


def fadd(prefix, left, right):
    if left[0] != right[0]:
        raise AssertionError(prefix + " is not a same-sign Horner FADD")
    scale = min(left[1], right[1])
    a = left[2] << (left[1] - scale)
    b = right[2] << (right[1] - scale)
    total = a + b
    cut = total.bit_length() - 64
    rounded = round_word(left[0], total, scale, 64, True)
    if rounded[1] != scale + cut:
        raise AssertionError(prefix + " unexpected rounding overflow")
    carries = ripple_carries(a, b, total.bit_length() + 2)
    values = {}

    for offset in RELATIVE:
        position = cut + offset
        av = bit(a, position)
        bv = bit(b, position)
        values[prefix + ".a.%+d" % offset] = av
        values[prefix + ".b.%+d" % offset] = bv
        values[prefix + ".sum.%+d" % offset] = bit(total, position)
        values[prefix + ".g.%+d" % offset] = av & bv
        values[prefix + ".p.%+d" % offset] = av ^ bv
        values[prefix + ".kill.%+d" % offset] = 1 ^ (av | bv)
        values[prefix + ".cin.%+d" % offset] = (
            carries.get(position, 0))
        values[prefix + ".cout.%+d" % offset] = (
            carries.get(position + 1, 0))

    lsb = bit(total, cut)
    guard = bit(total, cut - 1)
    sticky = bool(total & ((1 << (cut - 1)) - 1)) if cut > 1 else False
    increment = guard and (sticky or lsb)
    values[prefix + ".round.lsb"] = lsb
    values[prefix + ".round.guard"] = guard
    values[prefix + ".round.sticky"] = sticky
    values[prefix + ".round.inexact"] = guard or sticky
    values[prefix + ".round.tie"] = guard and not sticky
    values[prefix + ".round.increment"] = increment
    values[prefix + ".round.carry_or_twos"] = increment

    retained_ones = 0
    position = cut
    while bit(total, position):
        retained_ones += 1
        position += 1
    for threshold in range(1, 17):
        values[prefix + ".round.ones.ge.%02d" % threshold] = (
            retained_ones >= threshold)
        values[prefix + ".round.carry_to.%02d" % threshold] = (
            increment and retained_ones >= threshold)

    propagate_run = 0
    position = cut - 1
    while position >= 0 and (bit(a, position) ^ bit(b, position)):
        propagate_run += 1
        position -= 1
    for threshold in range(1, 17):
        values[prefix + ".add.run_below.ge.%02d" % threshold] = (
            propagate_run >= threshold)

    # The patent's sticky scanner operates on four-bit groups.  Emit the
    # eight groups immediately below the result cut and their cumulative OR.
    cumulative = 0
    for group in range(8):
        high = cut - 4 * group
        low = max(0, high - 4)
        nibble = (total >> low) & ((1 << max(0, high - low)) - 1)
        nonzero = bool(nibble)
        cumulative |= nonzero
        values[prefix + ".sticky.nibble.%02d" % group] = nonzero
        values[prefix + ".sticky.cumulative.%02d" % group] = cumulative

    # Conditional carry endpoints aligned to both the result cut and the
    # physical exponent phase.  These are literal carry-select alternatives.
    for width in (2, 4, 8, 16):
        for relative_block in range(-1, 2):
            start = cut + relative_block * width
            end = start + width
            for assumed in (0, 1):
                values[prefix + ".cut.block%02d.rel%+d.c%d" % (
                    width, relative_block, assumed)] = (
                        conditional_carry(a, b, start, end, assumed)
                        if start >= 0 else 0)
        phase = (scale + cut) % width
        start = cut - phase
        for assumed in (0, 1):
            values[prefix + ".phys.block%02d.cut.c%d" % (
                width, assumed)] = conditional_carry(
                    a, b, start, cut, assumed)
            values[prefix + ".phys.block%02d.out.c%d" % (
                width, assumed)] = conditional_carry(
                    a, b, start, start + width, assumed)
        values[prefix + ".phys.block%02d.actual_cin" % width] = (
            carries.get(start, 0))
        values[prefix + ".phys.block%02d.actual_cut" % width] = (
            carries.get(cut, 0))
        values[prefix + ".phys.block%02d.actual_out" % width] = (
            carries.get(start + width, 0))
    return rounded, values


def row_features(row):
    fourth = (int(row["tc_f4_sign"]), int(row["tc_f4_exp"]),
              int(row["tc_f4_sig"], 16))
    negative_product_1 = multiply(fourth, CONSTANTS[5])
    negative_1, values = fadd("negative.add1", CONSTANTS[3],
                              negative_product_1)
    negative_product_2 = multiply(fourth, negative_1)
    negative_2, more = fadd("negative.add2", CONSTANTS[1],
                            negative_product_2)
    values.update(more)

    positive_product_1 = multiply(fourth, CONSTANTS[6])
    positive_1, more = fadd("positive.add1", CONSTANTS[4],
                            positive_product_1)
    values.update(more)
    positive_product_2 = multiply(fourth, positive_1)
    positive_2, more = fadd("positive.add2", CONSTANTS[2],
                            positive_product_2)
    values.update(more)

    expected_negative = (int(row["tc_lf_sign"]), int(row["tc_lf_exp"]),
                         int(row["tc_lf_sig"], 16))
    expected_positive = (int(row["tc_rf_sign"]), int(row["tc_rf_exp"]),
                         int(row["tc_rf_sig"], 16))
    if negative_2 != expected_negative:
        raise AssertionError("negative Horner mismatch for " + row["op"])
    if positive_2 != expected_positive:
        raise AssertionError("positive Horner mismatch for " + row["op"])
    return values


def equation_counts(matrix, current, borrow, allowed_delta, subset,
                    gate, decrement_when):
    subset = np.asarray(subset, dtype=bool)
    errors = np.zeros(matrix.shape[1], dtype=np.int64)
    changes = np.zeros(matrix.shape[1], dtype=np.int64)
    for carry in (0, 1):
        for feature_value in (0, 1):
            output_carry = (gate >> (2 * carry + feature_value)) & 1
            decrement = int(feature_value == decrement_when)
            for borrowed in (0, 1):
                predicted = borrowed - 1 + output_carry - decrement
                delta_index = predicted + 2
                state = subset & (current == carry) & (borrow == borrowed)
                bad = state & ~allowed_delta[:, delta_index]
                # Use the scalar state value.  Subtracting one from the
                # uint8 ``borrow`` vector would wrap zero to 255 and corrupt
                # this diagnostic count (the admissibility score is separate).
                changed = state & (predicted != (borrowed - 1 + carry))
                true_bad = matrix.T @ bad.astype(np.int64)
                true_changed = matrix.T @ changed.astype(np.int64)
                if feature_value:
                    errors += true_bad
                    changes += true_changed
                else:
                    errors += int(bad.sum()) - true_bad
                    changes += int(changed.sum()) - true_changed
    return errors, changes


def equation_signature_cache(matrix, current, borrow, allowed_delta,
                             positives):
    """Collapse rows to exact finite states before enumerating gates."""
    groups = {}
    for index in range(len(current)):
        allowed_mask = sum(
            int(allowed_delta[index, delta + 2]) << (delta + 2)
            for delta in DELTAS)
        key = (int(current[index]), int(borrow[index]), allowed_mask,
               int(positives[index]))
        groups.setdefault(key, []).append(index)
    cache = []
    for key, indexes in groups.items():
        true_counts = matrix[indexes].sum(axis=0, dtype=np.int64)
        cache.append((key, len(indexes) - true_counts, true_counts))
    return cache


def equation_cached_counts(cache, feature_count, gate, decrement_when):
    errors = {
        "all": np.zeros(feature_count, dtype=np.int64),
        "positive": np.zeros(feature_count, dtype=np.int64),
        "base": np.zeros(feature_count, dtype=np.int64),
    }
    base_changes = np.zeros(feature_count, dtype=np.int64)
    for (carry, borrowed, allowed_mask, positive), false_counts, \
            true_counts in cache:
        for feature_value, counts in ((0, false_counts), (1, true_counts)):
            output_carry = (gate >> (2 * carry + feature_value)) & 1
            decrement = int(feature_value == decrement_when)
            predicted = borrowed - 1 + output_carry - decrement
            if not (allowed_mask & (1 << (predicted + 2))):
                errors["all"] += counts
                errors["positive" if positive else "base"] += counts
            if not positive and predicted != borrowed - 1 + carry:
                base_changes += counts
    return errors, base_changes


def decrement_wire_scores(matrix, target_decrement, positives, names):
    """Rank wire/complement predictions without per-feature row scans."""
    scores = []
    for subset_name, subset in (
            ("all", np.ones(len(positives), dtype=bool)),
            ("positive", positives), ("base", ~positives)):
        wanted = subset & target_decrement
        unwanted = subset & ~target_decrement
        true_wanted = matrix.T @ wanted.astype(np.int64)
        true_unwanted = matrix.T @ unwanted.astype(np.int64)
        errors_one = int(wanted.sum()) - true_wanted + true_unwanted
        errors_zero = int(subset.sum()) - errors_one
        if subset_name == "all":
            all_errors = (errors_zero, errors_one)
        elif subset_name == "positive":
            positive_errors = (errors_zero, errors_one)
        else:
            base_errors = (errors_zero, errors_one)
    for feature, name in enumerate(names):
        for decrement_when in (0, 1):
            scores.append((
                int(all_errors[decrement_when][feature]),
                int(positive_errors[decrement_when][feature]),
                int(base_errors[decrement_when][feature]),
                decrement_when, name,
            ))
    scores.sort()
    return scores


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
    feature_rows = []
    states = []
    names = None
    allowed_sets = []
    for index, row in enumerate(rows):
        allowed = (positive_delta if row["label"] == "POS"
                   else control_delta)[row["op"]]
        states.append(extract_carry_state(row, allowed))
        allowed_sets.append(allowed)
        values = row_features(row)
        if names is None:
            names = sorted(values)
        elif set(values) != set(names):
            raise AssertionError("feature schema changed")
        feature_rows.append([int(values[name]) for name in names])
        if (index + 1) % 5000 == 0:
            print("features", index + 1, "/", len(rows), flush=True)

    matrix = np.asarray(feature_rows, dtype=np.uint8)
    current = np.asarray([state[2] for state in states], dtype=np.uint8)
    borrow = np.asarray([state[0] for state in states], dtype=np.uint8)
    allowed_matrix = np.asarray([
        [delta in allowed for delta in DELTAS]
        for allowed in allowed_sets], dtype=bool)
    positives = np.asarray([row["label"] == "POS" for row in rows])
    subsets = {
        "base": ~positives,
        "positive": positives,
        "all": np.ones(len(rows), dtype=bool),
    }

    signature_cache = equation_signature_cache(
        matrix, current, borrow, allowed_matrix, positives)
    scores = []
    for decrement_when in (0, 1):
        for gate in range(16):
            group, base_changes = equation_cached_counts(
                signature_cache, len(names), gate, decrement_when)
            for feature, name in enumerate(names):
                scores.append((
                    int(group["all"][feature]),
                    int(group["positive"][feature]),
                    int(group["base"][feature]),
                    int(base_changes[feature]),
                    GATE_NAMES[gate], gate, decrement_when, name,
                ))
    scores.sort()

    target_decrement = np.asarray([not state[3] for state in states])
    decrement_scores = decrement_wire_scores(
        matrix, target_decrement, positives, names)

    with open(args.output, "w") as target:
        target.write("rows\t%d\nfeatures\t%d\npositives\t%d\n" % (
            len(rows), len(names), int(positives.sum())))
        target.write("carry_impossible\t%d\n" % int(target_decrement.sum()))
        target.write("\n[unified carry-plus-decrement ranking]\n")
        target.write("all_bad\tpositive_bad\tbase_bad\tbase_changes"
                     "\tgate\tgate_mask\tdecrement_when\tfeature\n")
        for score in scores[:1000]:
            target.write("\t".join(map(str, score)) + "\n")
        exact = [score for score in scores if score[0] == 0]
        target.write("\n[zero-error unified equations]\ncount\t%d\n" %
                     len(exact))
        for score in exact[:2000]:
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

        best = scores[0]
        feature = names.index(best[-1])
        gate = best[5]
        decrement_when = best[6]
        target.write("\n[best-equation positive and changed rows]\n")
        target.write("op\tlabel\tbranch\tborrow\tcurrent_delta"
                     "\tcurrent_carry\tfeature\tnew_carry\tdecrement"
                     "\tpredicted_delta\tallowed_delta\n")
        for row_index, (row, state, allowed) in enumerate(zip(
                rows, states, allowed_sets)):
            feature_value = int(matrix[row_index, feature])
            new_carry = (gate >> (2 * state[2] + feature_value)) & 1
            decrement = int(feature_value == decrement_when)
            predicted = state[0] - 1 + new_carry - decrement
            if row["label"] != "POS" and predicted == state[1]:
                continue
            target.write("%s\t%s\t%s\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%s\n" % (
                row["op"], row["label"], row["branch"], state[0],
                state[1], state[2], feature_value, new_carry, decrement,
                predicted, ",".join(map(str, sorted(allowed)))))
        target.write("best_equation\t%s\t%d\tdec_when=%d\t%s\n" % (
            best[4], gate, decrement_when, best[-1]))

    print("wrote", args.output, "rows", len(rows), "features", len(names),
          "best", scores[0], "exact", len(exact),
          "best_decrement", decrement_scores[0])


if __name__ == "__main__":
    main()
