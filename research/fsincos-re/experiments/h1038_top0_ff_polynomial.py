#!/usr/bin/env python3
"""h1038: synthesize the closed tap for the disjoint retained-byte-FF arm.

The h1000 fixes all satisfy terminal_byte == 0xff, a regime absent from the
h975 positives.  h1037 supplies the exact 3/32 negative-phase sub-bin term.
This script asks whether the remaining per-cell u-floor intervals collapse
under a small polynomial tap over the already physical digit features.  It
uses an exact bounded-integer constraint search, not regression.
"""

import csv
from collections import Counter, defaultdict

import h1034_top0_tap_solver as tap_solver
import h1035_top0_response_score as response_score
import h1036_top0_joint_phase as joint


def load_ff_rows():
    with open("/tmp/h1025_response_records.tsv") as source:
        raw = [row for row in csv.DictReader(source, delimiter="\t")
               if row["family"] == "top0" and row["source"] == "h1000"]
    records = response_score.run_dumps([row["op"] for row in raw])
    rows = []
    for datum, record in zip(raw, records):
        row = response_score.reconstructed(record)
        if row["pcut"] != 1 or row["sum8"] - row["low3"] != 0xff:
            continue
        row["target"] = int(datum["label"] == "FIX")
        row["op"] = datum["op"]
        rows.append(row)
    return rows


def interval(rows, limit=256):
    feasible = []
    for tap in range(-limit, limit + 1):
        good = True
        for row in rows:
            _, u = tap_solver.base_and_u(row, tap)
            predicted = joint.comparison_value(row) >= 32 * u * tap_solver.ONE
            if predicted != bool(row["target"]):
                good = False
                break
        if good:
            feasible.append(tap)
    if not feasible:
        return None
    return (None if feasible[0] == -limit else feasible[0],
            None if feasible[-1] == limit else feasible[-1])


def values(row):
    low = row["low3"]
    b1, b2 = row["b1"], row["b2"]
    parity = low & 1
    dd = row["dist"] - 7
    return {
        "1": 1, "L": low, "b1": b1, "b2": b2, "lp": parity,
        "dd": dd, "L*b1": low * b1, "L*b2": low * b2,
        "L*dd": low * dd, "b1*dd": b1 * dd, "b2*dd": b2 * dd,
        "lp*dd": parity * dd, "b1*b2": b1 * b2, "L2": low * low,
    }


def exact_search(constraints, names, bound=16, node_limit=8_000_000):
    """Depth-first bounded integer feasibility with interval pruning."""
    matrix = []
    for row, (lo, hi) in constraints:
        feature = values(row)
        matrix.append(([feature[name] for name in names], lo, hi))

    # High-range columns first make the interval bounds contract early.
    order = sorted(range(len(names)),
                   key=lambda column: max(abs(item[0][column])
                                          for item in matrix),
                   reverse=True)
    ordered_names = [names[index] for index in order]
    ordered = [([feature[index] for index in order], lo, hi)
               for feature, lo, hi in matrix]
    domain = [0] + [value for magnitude in range(1, bound + 1)
                    for value in (magnitude, -magnitude)]
    nodes = 0
    best = None

    def visit(depth, partial, coefficients, weight):
        nonlocal nodes, best
        nodes += 1
        if nodes > node_limit:
            return True
        if best is not None and weight >= best[0]:
            return False
        if depth == len(ordered_names):
            for current, (_, lo, hi) in zip(partial, ordered):
                if lo is not None and current < lo:
                    return False
                if hi is not None and current > hi:
                    return False
            best = (weight, tuple(coefficients))
            return False

        # Precompute the most any unassigned bounded coefficient can move
        # each constraint.  This is conservative but exact for pruning.
        remaining = []
        for feature, _, _ in ordered:
            remaining.append(sum(abs(value) * bound
                                 for value in feature[depth + 1:]))
        column = [feature[depth] for feature, _, _ in ordered]
        for coefficient in domain:
            next_weight = weight + abs(coefficient)
            if best is not None and next_weight >= best[0]:
                continue
            next_partial = [current + coefficient * value
                            for current, value in zip(partial, column)]
            possible = True
            for current, reach, (_, lo, hi) in zip(
                    next_partial, remaining, ordered):
                if lo is not None and current + reach < lo:
                    possible = False
                    break
                if hi is not None and current - reach > hi:
                    possible = False
                    break
            if possible:
                stop = visit(depth + 1, next_partial,
                             coefficients + [coefficient], next_weight)
                if stop:
                    return True
        return False

    visit(0, [0] * len(matrix), [], 0)
    if best is None:
        return None, nodes, ordered_names
    by_name = dict(zip(ordered_names, best[1]))
    return (best[0], tuple(by_name[name] for name in names)), nodes, ordered_names


def main():
    rows = load_ff_rows()
    print("rows", Counter(row["target"] for row in rows))
    for quadrant in sorted(set((row["s4"], row["side"]) for row in rows)):
        sample = [row for row in rows
                  if (row["s4"], row["side"]) == quadrant]
        cells = defaultdict(list)
        for row in sample:
            cells[(row["dist"], row["low3"], row["b1"], row["b2"])].append(row)
        cell_intervals = {cell: interval(members)
                          for cell, members in cells.items()}
        print("\nquadrant", quadrant, "rows", len(sample),
              "labels", Counter(row["target"] for row in sample))
        print(" intervals", cell_intervals)
        if any(value is None for value in cell_intervals.values()):
            print(" within-cell conflict")
            continue
        constraints = []
        for cell, members in cells.items():
            constraints.append((members[0], cell_intervals[cell]))

        bases = [
            ("1", "L", "b1", "b2", "lp", "dd"),
            ("1", "L", "b1", "b2", "lp", "dd", "L*b1"),
            ("1", "L", "b1", "b2", "lp", "dd", "L*b2"),
            ("1", "L", "b1", "b2", "lp", "dd", "L*dd"),
            ("1", "L", "b1", "b2", "lp", "dd", "b1*dd"),
            ("1", "L", "b1", "b2", "lp", "dd", "lp*dd"),
            ("1", "L", "b1", "b2", "lp", "dd", "b1*b2"),
            ("1", "L", "b1", "b2", "lp", "dd", "L2"),
            ("1", "L", "b1", "b2", "lp", "dd",
             "L*b1", "L*b2", "L*dd"),
            ("1", "L", "b1", "b2", "lp", "dd",
             "L*b1", "L*b2", "L*dd", "b1*dd", "lp*dd"),
        ]
        for names in bases:
            answer, nodes, order = exact_search(constraints, names)
            print(" basis", names, "=>", answer, "nodes", nodes,
                  "order", order)
            if answer is not None:
                break


if __name__ == "__main__":
    main()
