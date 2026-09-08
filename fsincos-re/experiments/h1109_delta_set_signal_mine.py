#!/usr/bin/env python3
"""Score terminal circuit signals against exact admissible R59 deltas.

The force models expose an equivalence set, not a unique target: more than one
internal retained delta can round to the same hardware result.  This script
therefore rejects a candidate only when its selected delta is outside the
intersection of the force responses from all four rounding modes.  It tests
ordinary carry/borrow-prefix wires as two-way selectors; it does not use the
operand identity or learn numeric input boundaries.
"""

import argparse
import csv
import os
from collections import defaultdict

import numpy as np

from h1106_terminal_prefix_mine import terminal_features


DELTAS = tuple(range(-2, 3))


def read_tsv(path):
    with open(path) as source:
        return list(csv.DictReader(source, delimiter="\t"))


def allmode_allowed(path):
    """Return per-operand intersections; force number n means delta n-3."""
    responses = defaultdict(list)
    for row in read_tsv(path):
        matches = set()
        if row["matches"] != "-":
            matches = {int(value) - 3
                       for value in row["matches"].split(",")}
        responses[row["op"]].append(matches)
    allowed = {}
    for operand, mode_sets in responses.items():
        if len(mode_sets) != 4:
            raise AssertionError(
                "%s has %d modes, expected four" % (operand, len(mode_sets)))
        exact = set.intersection(*mode_sets)
        if not exact:
            raise AssertionError("empty all-mode delta set for " + operand)
        allowed[operand] = frozenset(exact)
    return allowed


def direct_allowed(value):
    """Parse an already delta-valued response list (the adversarial bank)."""
    if value == "-":
        return frozenset()
    return frozenset(int(item) for item in value.split(","))


def current_delta(row):
    return int(row["br_r"], 16) - (int(row["umag"], 16) >> int(row["k"]))


def group_statistics(matrix, allowed_matrix, current, subset):
    """Precompute counts needed to score every d0/d1 signal mapping."""
    subset = np.asarray(subset, dtype=bool)
    selected = int(subset.sum())
    bad = (~allowed_matrix) & subset[:, None]
    changed = np.asarray([
        ((current != delta) & subset) for delta in DELTAS],
        dtype=bool).T
    # For a signal column, false rows choose d0 and true rows choose d1.
    # false_bad(d0) + true_bad(d1) is obtained from these aggregate counts.
    true_bad = matrix.T @ bad.astype(np.int64)
    true_changed = matrix.T @ changed.astype(np.int64)
    return {
        "rows": selected,
        "bad": bad.sum(axis=0, dtype=np.int64),
        "true_bad": true_bad,
        "changed": changed.sum(axis=0, dtype=np.int64),
        "true_changed": true_changed,
    }


def mapped_count(stats, feature, d0, d1, stem):
    i0 = d0 + 2
    i1 = d1 + 2
    totals = stats[stem]
    true_totals = stats["true_" + stem]
    return int(totals[i0] - true_totals[feature, i0]
               + true_totals[feature, i1])


def constant_count(allowed_matrix, subset, delta):
    return int(np.count_nonzero(
        np.asarray(subset, dtype=bool) & ~allowed_matrix[:, delta + 2]))


def row_mapped_counts(matrix, allowed_matrix, current, subset, d0, d1):
    """Score signal=0/1 when each row has its own two candidate deltas."""
    subset = np.asarray(subset, dtype=bool)
    indexes = np.arange(len(current))
    bad0 = subset & ~allowed_matrix[indexes, d0 + 2]
    bad1 = subset & ~allowed_matrix[indexes, d1 + 2]
    changed0 = subset & (current != d0)
    changed1 = subset & (current != d1)
    errors = (int(bad0.sum()) - matrix.T @ bad0.astype(np.int64)
              + matrix.T @ bad1.astype(np.int64))
    changes = (int(changed0.sum()) - matrix.T @ changed0.astype(np.int64)
               + matrix.T @ changed1.astype(np.int64))
    return errors, changes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("features")
    parser.add_argument("positive_allmode")
    parser.add_argument("control_allmode")
    parser.add_argument("adversarial")
    parser.add_argument("output")
    args = parser.parse_args()
    if os.path.exists(args.output):
        raise SystemExit("refusing to overwrite " + args.output)

    positive_allowed = allmode_allowed(args.positive_allmode)
    control_allowed = allmode_allowed(args.control_allmode)
    source_rows = read_tsv(args.features)
    if len({row["op"] for row in source_rows}) != len(source_rows):
        raise AssertionError("feature bank contains duplicate operands")

    rows = []
    for row in source_rows:
        bank = positive_allowed if row["label"] == "POS" else control_allowed
        if row["op"] not in bank:
            raise AssertionError("missing all-mode response for " + row["op"])
        rows.append((row, row["label"].lower(), bank[row["op"]]))

    known_operands = {row[0]["op"] for row in rows}
    for row in read_tsv(args.adversarial):
        if row["op"] in known_operands:
            raise AssertionError("adversarial operand is not fresh: " + row["op"])
        allowed = direct_allowed(row["matches"])
        if not allowed:
            raise AssertionError("empty adversarial delta set for " + row["op"])
        rows.append((row, "adversarial", allowed))
        known_operands.add(row["op"])

    names = None
    feature_rows = []
    for index, (row, _, _) in enumerate(rows):
        values = terminal_features(row)
        if names is None:
            names = sorted(values)
        elif set(values) != set(names):
            raise AssertionError("feature schema changed")
        feature_rows.append([values[name] for name in names])
        if (index + 1) % 5000 == 0:
            print("features", index + 1, "/", len(rows), flush=True)
    matrix = np.asarray(feature_rows, dtype=np.uint8)
    current = np.asarray([current_delta(row) for row, _, _ in rows],
                         dtype=np.int64)
    if not np.isin(current, DELTAS).all():
        raise AssertionError("current retained delta outside force range")
    allowed_matrix = np.asarray([
        [delta in allowed for delta in DELTAS]
        for _, _, allowed in rows], dtype=bool)
    kinds = np.asarray([kind for _, kind, _ in rows])
    subsets = {
        "base": kinds == "neg",
        "positive": kinds == "pos",
        "adversarial": kinds == "adversarial",
        "controls": kinds != "pos",
        "all": np.ones(len(rows), dtype=bool),
    }
    stats = {name: group_statistics(matrix, allowed_matrix, current, subset)
             for name, subset in subsets.items()}

    current_bad = {
        name: int(np.count_nonzero(
            subset & ~allowed_matrix[np.arange(len(rows)), current + 2]))
        for name, subset in subsets.items()
    }

    constants = []
    for delta in DELTAS:
        errors = {name: constant_count(allowed_matrix, subset, delta)
                  for name, subset in subsets.items()}
        changes = int(np.count_nonzero(subsets["controls"]
                                       & (current != delta)))
        constants.append((errors["all"], errors["positive"],
                          errors["base"], errors["adversarial"], changes,
                          delta))
    constants.sort()

    scores = []
    for feature, name in enumerate(names):
        for d0 in DELTAS:
            for d1 in DELTAS:
                errors = {
                    group: mapped_count(group_stats, feature, d0, d1, "bad")
                    for group, group_stats in stats.items()
                }
                changes = mapped_count(
                    stats["controls"], feature, d0, d1, "changed")
                scores.append((errors["all"], errors["positive"],
                               errors["base"], errors["adversarial"],
                               changes, name, d0, d1))
    scores.sort()

    # A subtraction result formed as A_hi + ~B_hi + c_pred differs from
    # exact floor((A-B)/2^k) by borrow_exact - 1 + c_pred.  This is the
    # circuit equation for the patent's two's-complement carry c; unlike the
    # constant-delta score above, the same predicted-carry wire can yield
    # -1, 0, or +1 depending on the actual discarded-field borrow.
    borrow = np.asarray([
        ((int(row["S"], 16) & ((1 << int(row["k"])) - 1))
         < (int(row["B"], 16) & ((1 << int(row["k"])) - 1)))
        for row, _, _ in rows], dtype=np.int64)
    carry_scores = []
    carry_group_scores = {}
    for group, subset in subsets.items():
        carry_group_scores[group] = []
        # orientation 1: the feature itself is predicted no-borrow carry.
        carry_group_scores[group].append(row_mapped_counts(
            matrix, allowed_matrix, current, subset, borrow - 1, borrow))
        # orientation 0: the complement of the feature is predicted carry.
        carry_group_scores[group].append(row_mapped_counts(
            matrix, allowed_matrix, current, subset, borrow, borrow - 1))
    for feature, name in enumerate(names):
        for carry_when in (0, 1):
            errors = {group: int(carry_group_scores[group][carry_when][0][feature])
                      for group in subsets}
            changes = int(carry_group_scores["controls"][carry_when][1][feature])
            carry_scores.append((errors["all"], errors["positive"],
                                 errors["base"], errors["adversarial"],
                                 changes, name, carry_when))
    carry_scores.sort()

    with open(args.output, "w") as target:
        target.write("rows\t%d\nfeatures\t%d\n" % (len(rows), len(names)))
        for name in ("base", "positive", "adversarial", "controls", "all"):
            target.write("%s_rows\t%d\n" % (name, stats[name]["rows"]))
            target.write("current_bad_%s\t%d\n" % (name, current_bad[name]))

        target.write("\n[constants]\n")
        target.write("all_bad\tpositive_bad\tbase_bad\tadversarial_bad"
                     "\tcontrol_delta_changes\tdelta\n")
        for score in constants:
            target.write("\t".join(map(str, score)) + "\n")

        target.write("\n[two-way terminal signals]\n")
        target.write("all_bad\tpositive_bad\tbase_bad\tadversarial_bad"
                     "\tcontrol_delta_changes\tfeature\tdelta_if_0"
                     "\tdelta_if_1\n")
        for score in scores[:200]:
            target.write("\t".join(map(str, score)) + "\n")

        exact = [score for score in scores if score[0] == 0]
        target.write("\n[zero-error signals]\n")
        target.write("count\t%d\n" % len(exact))
        for score in exact[:1000]:
            target.write("\t".join(map(str, score)) + "\n")

        target.write("\n[predicted subtraction carry]\n")
        target.write("all_bad\tpositive_bad\tbase_bad\tadversarial_bad"
                     "\tcontrol_delta_changes\tfeature\tcarry_when\n")
        for score in carry_scores[:200]:
            target.write("\t".join(map(str, score)) + "\n")

        exact_carry = [score for score in carry_scores if score[0] == 0]
        target.write("\n[zero-error predicted carries]\n")
        target.write("count\t%d\n" % len(exact_carry))
        for score in exact_carry[:1000]:
            target.write("\t".join(map(str, score)) + "\n")

    print("wrote", args.output, "rows", len(rows), "features", len(names),
          "best", scores[0], "zero_error", sum(s[0] == 0 for s in scores),
          "best_carry", carry_scores[0],
          "zero_error_carry", sum(s[0] == 0 for s in carry_scores))


if __name__ == "__main__":
    main()
