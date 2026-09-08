#!/usr/bin/env python3
"""Mine zero-contradiction conjunctions of named circuit wires.

The target is not the endpoint label.  It is whether the incumbent R59
carry must be complemented under the intersection of all four architectural
rounding modes.  Neutral rows are ignored and carry-impossible rows are kept
out of this one-bit synthesis.  Candidate literals come only from the
terminal prefix network and the literal P5 multiplier/CSA trees.
"""

import argparse
import csv
import os

import numpy as np

from h1101_p5_tree_mine import row_features as product_features
from h1106_terminal_prefix_mine import terminal_features
from h1110_carry_gate_mine import allmode_allowed, extract_carry_state


def packed_integer(vector):
    return int.from_bytes(np.packbits(vector, bitorder="little").tobytes(),
                          "little")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("features")
    parser.add_argument("positive_allmode")
    parser.add_argument("control_allmode")
    parser.add_argument("output")
    parser.add_argument("--per-positive", type=int, default=160)
    args = parser.parse_args()
    if os.path.exists(args.output):
        raise SystemExit("refusing to overwrite " + args.output)

    positive_delta = allmode_allowed(args.positive_allmode)
    control_delta = allmode_allowed(args.control_allmode)
    with open(args.features) as source:
        rows = list(csv.DictReader(source, delimiter="\t"))

    feature_rows = []
    names = None
    states = []
    for index, row in enumerate(rows):
        bank = positive_delta if row["label"] == "POS" else control_delta
        state = extract_carry_state(row, bank[row["op"]])
        states.append(state)
        values = {"terminal." + name: value
                  for name, value in terminal_features(row).items()}
        values.update({"product." + name: value
                       for name, value in product_features(row).items()})
        values["state.current_carry"] = state[2]
        values["state.borrow"] = state[0]
        if names is None:
            names = sorted(values)
        elif set(values) != set(names):
            raise AssertionError("feature schema changed")
        feature_rows.append([values[name] for name in names])
        if (index + 1) % 5000 == 0:
            print("features", index + 1, "/", len(rows), flush=True)

    matrix = np.asarray(feature_rows, dtype=np.uint8)
    required = []
    forbidden = []
    impossible = []
    for index, state in enumerate(states):
        current = state[2]
        opposite = 1 - current
        if not state[3]:
            impossible.append(index)
        elif current not in state[3] and opposite in state[3]:
            required.append(index)
        elif current in state[3] and opposite not in state[3]:
            forbidden.append(index)
    required_matrix = matrix[required]
    forbidden_matrix = matrix[forbidden]
    positive_count = len(required)
    all_positive = (1 << positive_count) - 1
    all_forbidden = (1 << len(forbidden)) - 1

    literals = []
    for column, name in enumerate(names):
        positive_true = packed_integer(required_matrix[:, column])
        forbidden_true = packed_integer(forbidden_matrix[:, column])
        for value in (1, 0):
            positive_bits = (positive_true if value
                             else all_positive ^ positive_true)
            if not positive_bits:
                continue
            forbidden_bits = (forbidden_true if value
                              else all_forbidden ^ forbidden_true)
            literals.append({
                "name": name,
                "value": value,
                "positive": positive_bits,
                "forbidden": forbidden_bits,
                "negative_count": forbidden_bits.bit_count(),
            })

    # Retain the rarest literals true at each required row.  This keeps the
    # quadratic pass bounded without learning a numeric operand threshold.
    selected_indices = set()
    for positive in range(positive_count):
        candidates = [
            (literal["negative_count"],
             -literal["positive"].bit_count(), index)
            for index, literal in enumerate(literals)
            if (literal["positive"] >> positive) & 1
        ]
        candidates.sort()
        selected_indices.update(index for _, _, index
                                in candidates[:args.per_positive])
    selected = [literals[index] for index in sorted(selected_indices)]

    terms = []
    for literal in selected:
        if not literal["forbidden"]:
            terms.append((literal["positive"].bit_count(),
                          literal["positive"], literal["negative_count"],
                          (literal,)))
    for left_index, left in enumerate(selected):
        for right in selected[left_index + 1:]:
            positive_bits = left["positive"] & right["positive"]
            if not positive_bits:
                continue
            forbidden_bits = left["forbidden"] & right["forbidden"]
            if forbidden_bits:
                continue
            terms.append((positive_bits.bit_count(), positive_bits, 0,
                          (left, right)))
    # Deduplicate equivalent terms, preferring fewer literals and then
    # lexical wire names for deterministic reports.
    best_by_coverage = {}
    for term in terms:
        coverage = term[1]
        signature = tuple((literal["name"], literal["value"])
                          for literal in term[3])
        candidate = (len(term[3]), signature, term)
        if coverage not in best_by_coverage \
                or candidate < best_by_coverage[coverage]:
            best_by_coverage[coverage] = candidate
    terms = [candidate[2] for candidate in best_by_coverage.values()]
    terms.sort(key=lambda term: (-term[0], len(term[3]),
                                 tuple(lit["name"] for lit in term[3])))

    # Greedy zero-contradiction cover is only a complexity diagnostic.  A
    # large or singleton-heavy result is evidence against a compact gate.
    uncovered = all_positive
    cover = []
    while uncovered:
        choices = [term for term in terms if term[1] & uncovered]
        if not choices:
            break
        term = max(choices, key=lambda candidate: (
            (candidate[1] & uncovered).bit_count(), candidate[0],
            -len(candidate[3])))
        cover.append(term)
        uncovered &= ~term[1]

    with open(args.output, "w") as target:
        target.write("rows\t%d\nfeatures\t%d\nliterals\t%d\n"
                     "selected_literals\t%d\nrequired_flip\t%d\n"
                     "forbidden_flip\t%d\nneutral\t%d\n"
                     "carry_impossible\t%d\nzero_forbidden_terms\t%d\n" %
                     (len(rows), len(names), len(literals), len(selected),
                      len(required), len(forbidden),
                      len(rows) - len(required) - len(forbidden)
                      - len(impossible), len(impossible), len(terms)))
        target.write("\n[required rows]\nindex\top\tbranch\n")
        for positive, row_index in enumerate(required):
            target.write("%d\t%s\t%s\n" %
                         (positive, rows[row_index]["op"],
                          rows[row_index]["branch"]))
        target.write("\n[best zero-forbidden terms]\n")
        target.write("coverage_count\tpositive_indices\tterm\n")
        for count, positive_bits, _, term_literals in terms[:500]:
            indices = [str(index) for index in range(positive_count)
                       if (positive_bits >> index) & 1]
            expression = " & ".join("%s=%d" %
                                    (literal["name"], literal["value"])
                                    for literal in term_literals)
            target.write("%d\t%s\t%s\n" %
                         (count, ",".join(indices), expression))
        target.write("\n[greedy cover]\n")
        target.write("terms\t%d\nuncovered\t%d\n" %
                     (len(cover), uncovered.bit_count()))
        for count, positive_bits, _, term_literals in cover:
            indices = [str(index) for index in range(positive_count)
                       if (positive_bits >> index) & 1]
            expression = " & ".join("%s=%d" %
                                    (literal["name"], literal["value"])
                                    for literal in term_literals)
            target.write("%d\t%s\t%s\n" %
                         (count, ",".join(indices), expression))

    print("wrote", args.output, "rows", len(rows), "features", len(names),
          "required", len(required), "forbidden", len(forbidden),
          "selected_literals", len(selected), "terms", len(terms),
          "cover", len(cover), "uncovered", uncovered.bit_count())


if __name__ == "__main__":
    main()
