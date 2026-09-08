#!/usr/bin/env python3
"""Mine two-input hardware gates for the unresolved R59 carry predictor.

The incumbent R59 retained delta has the exact subtractor form

    delta = borrow_exact - 1 + carry_predicted.

All cached controls and 26 of the 29 remaining operands admit at least one
carry bit under this equation.  This script asks whether the true carry is a
two-input Boolean gate of the incumbent predictor and one named circuit wire.
The search space is the complete set of sixteen two-input gates, applied to
terminal prefix wires and/or literal P5 multiplier-tree wires.  It does not
use operand identities or numeric input-space boundaries.
"""

import argparse
import csv
import os
from collections import defaultdict

import numpy as np

from h1101_p5_tree_mine import row_features as product_features
from h1106_terminal_prefix_mine import terminal_features


GATE_NAMES = {
    0x0: "0",
    0x1: "nor(c,f)",
    0x2: "not(c)&f",
    0x3: "not(c)",
    0x4: "c&not(f)",
    0x5: "not(f)",
    0x6: "c xor f",
    0x7: "nand(c,f)",
    0x8: "c&f",
    0x9: "c xnor f",
    0xA: "f",
    0xB: "not(c)|f",
    0xC: "c",
    0xD: "c|not(f)",
    0xE: "c|f",
    0xF: "1",
}


def read_tsv(path):
    with open(path) as source:
        return list(csv.DictReader(source, delimiter="\t"))


def allmode_allowed(path):
    responses = defaultdict(list)
    for row in read_tsv(path):
        matches = ({int(value) - 3 for value in row["matches"].split(",")}
                   if row["matches"] != "-" else set())
        responses[row["op"]].append(matches)
    result = {}
    for operand, mode_sets in responses.items():
        if len(mode_sets) != 4:
            raise AssertionError("expected four modes for " + operand)
        exact = set.intersection(*mode_sets)
        if not exact:
            raise AssertionError("empty delta set for " + operand)
        result[operand] = exact
    return result


def bit(value, position):
    return (value >> position) & 1


def extract_carry_state(row, allowed_delta):
    s_value = int(row["S"], 16)
    b_value = int(row["B"], 16)
    cut = int(row["k"])
    mask = (1 << cut) - 1
    borrow = int((s_value & mask) < (b_value & mask))
    current_delta = (int(row["br_r"], 16)
                     - (int(row["umag"], 16) >> cut))
    current_carry = current_delta - borrow + 1
    if current_carry not in (0, 1):
        raise AssertionError("incumbent is not a carry predictor: " + row["op"])
    allowed_carry = {delta - borrow + 1 for delta in allowed_delta}
    allowed_carry.intersection_update((0, 1))
    return borrow, current_delta, current_carry, allowed_carry


def feature_values(row, family):
    values = {}
    if family in ("terminal", "both"):
        values.update({"terminal." + name: value
                       for name, value in terminal_features(row).items()})
    if family in ("product", "both"):
        values.update({"product." + name: value
                       for name, value in product_features(row).items()})
    return values


def state_bad_counts(matrix, current, allowed, subset):
    """Count disallowed outputs for every (current, feature) state."""
    counts = {}
    subset = np.asarray(subset, dtype=bool)
    for carry in (0, 1):
        for feature_value in (0, 1):
            for output in (0, 1):
                selected = subset & (current == carry) & ~allowed[:, output]
                true_count = matrix.T @ selected.astype(np.int64)
                if feature_value:
                    counts[carry, feature_value, output] = true_count
                else:
                    counts[carry, feature_value, output] = (
                        int(selected.sum()) - true_count)
    return counts


def gate_errors(counts, gate):
    result = None
    for carry in (0, 1):
        for feature_value in (0, 1):
            output = (gate >> (2 * carry + feature_value)) & 1
            term = counts[carry, feature_value, output]
            result = term.copy() if result is None else result + term
    return result


def gate_changes(matrix, current, subset, gate):
    """Count rows on which the gate changes the incumbent carry."""
    subset = np.asarray(subset, dtype=bool)
    changes = np.zeros(matrix.shape[1], dtype=np.int64)
    for carry in (0, 1):
        for feature_value in (0, 1):
            output = (gate >> (2 * carry + feature_value)) & 1
            if output == carry:
                continue
            selected = subset & (current == carry)
            true_count = matrix.T @ selected.astype(np.int64)
            changes += (true_count if feature_value else
                        int(selected.sum()) - true_count)
    return changes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("features")
    parser.add_argument("positive_allmode")
    parser.add_argument("control_allmode")
    parser.add_argument("output")
    parser.add_argument("--family", choices=("terminal", "product", "both"),
                        default="both")
    args = parser.parse_args()
    if os.path.exists(args.output):
        raise SystemExit("refusing to overwrite " + args.output)

    positive_delta = allmode_allowed(args.positive_allmode)
    control_delta = allmode_allowed(args.control_allmode)
    rows = read_tsv(args.features)
    states = []
    feature_rows = []
    names = None
    for index, row in enumerate(rows):
        delta_bank = positive_delta if row["label"] == "POS" else control_delta
        state = extract_carry_state(row, delta_bank[row["op"]])
        states.append(state)
        values = feature_values(row, args.family)
        if names is None:
            names = sorted(values)
        elif set(values) != set(names):
            raise AssertionError("feature schema changed")
        feature_rows.append([values[name] for name in names])
        if (index + 1) % 5000 == 0:
            print("features", index + 1, "/", len(rows), flush=True)

    matrix = np.asarray(feature_rows, dtype=np.uint8)
    current = np.asarray([state[2] for state in states], dtype=np.uint8)
    allowed = np.asarray([[carry in state[3] for carry in (0, 1)]
                          for state in states], dtype=bool)
    carry_capable = allowed.any(axis=1)
    positives = np.asarray([row["label"] == "POS" for row in rows])
    subsets = {
        "base": (~positives) & carry_capable,
        "positive": positives & carry_capable,
        "all": carry_capable,
    }
    impossible = ~carry_capable
    current_bad = {
        name: int(np.count_nonzero(
            subset & ~allowed[np.arange(len(rows)), current]))
        for name, subset in subsets.items()
    }

    counts = {name: state_bad_counts(matrix, current, allowed, subset)
              for name, subset in subsets.items()}
    changes = {gate: gate_changes(matrix, current, subsets["base"], gate)
               for gate in range(16)}
    scores = []
    for gate in range(16):
        errors = {name: gate_errors(group_counts, gate)
                  for name, group_counts in counts.items()}
        for feature, name in enumerate(names):
            scores.append((int(errors["all"][feature]),
                           int(errors["positive"][feature]),
                           int(errors["base"][feature]),
                           int(changes[gate][feature]),
                           GATE_NAMES[gate], gate, name))
    scores.sort()

    with open(args.output, "w") as target:
        target.write("rows\t%d\nfeatures\t%d\nfamily\t%s\n" %
                     (len(rows), len(names), args.family))
        target.write("carry_capable\t%d\ncarry_impossible\t%d\n" %
                     (int(carry_capable.sum()), int(impossible.sum())))
        target.write("positive_carry_capable\t%d\npositive_carry_impossible\t%d\n" %
                     (int((positives & carry_capable).sum()),
                      int((positives & impossible).sum())))
        for name in ("base", "positive", "all"):
            target.write("%s_rows\t%d\ncurrent_bad_%s\t%d\n" %
                         (name, int(subsets[name].sum()), name,
                          current_bad[name]))
        target.write("\n[carry-impossible rows]\n")
        for row, state in zip(rows, states):
            if not state[3]:
                target.write("%s\t%s\tborrow=%d\tcurrent_delta=%d\n" %
                             (row["op"], row["branch"], state[0], state[1]))

        target.write("\n[two-input gate ranking]\n")
        target.write("all_bad\tpositive_bad\tbase_bad\tbase_changes"
                     "\tgate\tgate_mask\tfeature\n")
        for score in scores[:500]:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[best per gate]\n")
        target.write("all_bad\tpositive_bad\tbase_bad\tbase_changes"
                     "\tgate\tgate_mask\tfeature\n")
        for gate in range(16):
            gate_scores = [score for score in scores if score[5] == gate]
            for score in gate_scores[:20]:
                target.write("\t".join(map(str, score)) + "\n")
        exact = [score for score in scores if score[0] == 0]
        target.write("\n[zero-error carry gates]\ncount\t%d\n" % len(exact))
        for score in exact[:2000]:
            target.write("\t".join(map(str, score)) + "\n")

        best = scores[0]
        _, _, _, _, best_gate_name, best_gate, best_name = best
        best_column = names.index(best_name)
        target.write("\n[best-gate changed and positive rows]\n")
        target.write("op\tlabel\tbranch\tborrow\tcurrent_delta"
                     "\tcurrent_carry\tfeature\toutput\tallowed_carry"
                     "\tallowed_delta\n")
        for row_index, (row, state) in enumerate(zip(rows, states)):
            feature_value = int(matrix[row_index, best_column])
            output = ((best_gate
                       >> (2 * int(current[row_index]) + feature_value))
                      & 1)
            if row["label"] != "POS" and output == current[row_index]:
                continue
            target.write("%s\t%s\t%s\t%d\t%d\t%d\t%d\t%d\t%s\t%s\n" % (
                row["op"], row["label"], row["branch"], state[0], state[1],
                int(current[row_index]), feature_value, output,
                ",".join(map(str, sorted(state[3]))) or "-",
                ",".join(map(str, sorted(
                    positive_delta[row["op"]]
                    if row["label"] == "POS"
                    else control_delta[row["op"]])))))
        target.write("best_gate\t%s\t%d\t%s\n" % (
            best_gate_name, best_gate, best_name))

    print("wrote", args.output, "rows", len(rows), "features", len(names),
          "best", scores[0], "zero_error", len(exact),
          "carry_impossible", int(impossible.sum()))


if __name__ == "__main__":
    main()
