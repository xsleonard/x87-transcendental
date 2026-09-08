#!/usr/bin/env python3
"""h1036: solve the TOP/act0 floor threshold across both theta sides.

h1034 derived exact thresholds for the h975 positives at sum8 253..255.
The independent h1000 response fixes occupy sum8 256..262.  Treat both as
constraints on one signed phase, theta = 256-sum8, and solve

  T = c0 + cth*theta + cL*low3 + cb1*b1 + cb2*b2
         + clp*(low3&1) + cd*(dist-7)

inside the Round-60 floor.  All response BREAK rows and all target-impossible
h975 rows constrain the opposite side of the same full-precision inequality.
"""

import csv
from collections import Counter, defaultdict

import h1034_top0_tap_solver as tap_solver
import h1035_top0_response_score as response_score


def target(row):
    return row["target"]


def comparison_value(row):
    """Full-precision M with the h1037 negative-phase sub-bin tap."""
    theta = 256 - row["sum8"]
    return 32 * row["mreg"] + 3 * min(theta, 0) * tap_solver.ONE


def interval_for_rows(rows, limit=1024):
    feasible = []
    for tap in range(-limit, limit + 1):
        good = True
        for row in rows:
            _, u = tap_solver.base_and_u(row, tap)
            prediction = comparison_value(row) >= u * tap_solver.ONE * 32
            if prediction != bool(target(row)):
                good = False
                break
        if good:
            feasible.append(tap)
    if not feasible:
        return None
    if feasible != list(range(feasible[0], feasible[-1] + 1)):
        raise AssertionError("non-contiguous interval")
    return (None if feasible[0] == -limit else feasible[0],
            None if feasible[-1] == limit else feasible[-1])


def best_c0(lo, hi):
    return min(max(0, lo), hi)


def fit(intervals, max_slope_weight=36):
    """Enumerate (cth,cL,cb1,cb2,clp,cd) in L1 shells."""
    if any(interval is None for interval in intervals.values()):
        return []
    best_weight = None
    solutions = []
    for slope_weight in range(max_slope_weight + 1):
        if best_weight is not None and slope_weight > best_weight:
            break
        for cth, cL, cb1, cb2, clp, cd in tap_solver.signed_shell(
                6, slope_weight):
            lo0, hi0 = -1024, 1024
            for (theta, dist, low3, b1, b2), (lo, hi) in intervals.items():
                rest = (cth * theta + cL * low3 + cb1 * b1 + cb2 * b2
                        + clp * (low3 & 1) + cd * (dist - 7))
                if lo is not None:
                    lo0 = max(lo0, lo - rest)
                if hi is not None:
                    hi0 = min(hi0, hi - rest)
                if lo0 > hi0:
                    break
            if lo0 > hi0:
                continue
            c0 = best_c0(lo0, hi0)
            weight = slope_weight + abs(c0)
            coeff = c0, cth, cL, cb1, cb2, clp, cd
            if best_weight is None or weight < best_weight:
                best_weight = weight
                solutions = []
            if weight == best_weight:
                solutions.append((sum(value != 0 for value in coeff), coeff))
    return sorted(solutions)


def fires(row, coeff):
    c0, cth, cL, cb1, cb2, clp, cd = coeff
    theta = 256 - row["sum8"]
    tap = (c0 + cth * theta + cL * row["low3"]
           + cb1 * row["b1"] + cb2 * row["b2"]
           + clp * (row["low3"] & 1) + cd * (row["dist"] - 7))
    _, u = tap_solver.base_and_u(row, tap)
    return (row["pcut"] == 1
            and comparison_value(row) >= u * tap_solver.ONE * 32)


def main():
    census_rows = []
    for row in tap_solver.load_h1033_rows():
        if row["line"] != "TOP" or row["act"] != 0 or row["pcut"] != 1:
            continue
        lab = tap_solver.label(row)
        if lab is None:
            continue
        row = dict(row)
        row["target"] = lab
        row["source"] = "h975"
        census_rows.append(row)

    with open("/tmp/h1025_response_records.tsv") as source:
        raw_response = [row for row in csv.DictReader(source, delimiter="\t")
                        if row["family"] == "top0"
                        and row["source"] == "h1000"]
    records = response_score.run_dumps([row["op"] for row in raw_response])
    response_rows = []
    for raw, record in zip(raw_response, records):
        row = response_score.reconstructed(record)
        if row["pcut"] != 1:
            continue
        row["target"] = int(raw["label"] == "FIX")
        row["source"] = "h1000"
        row["op"] = raw["op"]
        response_rows.append(row)

    combined = census_rows + response_rows
    print("rows", Counter((row["source"], row["target"]) for row in combined))
    print("phase", Counter((row["source"], 256 - row["sum8"],
                            row["s4"], row["side"], row["target"])
                           for row in combined))

    quadrants = defaultdict(list)
    for row in combined:
        quadrants[(row["s4"], row["side"])].append(row)
    for quadrant in sorted(quadrants):
        sample = quadrants[quadrant]
        if not any(row["target"] for row in sample):
            continue
        cells = defaultdict(list)
        for row in sample:
            cells[(256 - row["sum8"], row["dist"], row["low3"],
                   row["b1"], row["b2"])].append(row)
        intervals = {cell: interval_for_rows(rows)
                     for cell, rows in cells.items()}
        impossible = [cell for cell, interval in intervals.items()
                      if interval is None]
        print(f"\nquadrant={quadrant} rows={len(sample)} cells={len(cells)} "
              f"impossible={len(impossible)}")
        if impossible:
            for cell in impossible:
                rr = cells[cell]
                print("  CONFLICT", cell,
                      Counter((row["source"], row["target"]) for row in rr),
                      [(row["mreg"] // tap_solver.ONE, row["target"],
                        row.get("op", "")) for row in rr])
            continue
        for cell in sorted(cells):
            if any(row["target"] for row in cells[cell]):
                print("  positive cell", cell, "interval", intervals[cell],
                      "labels", Counter((row["source"], row["target"])
                                        for row in cells[cell]))
        if quadrant == (66, 1):
            print("  sparse q66 branch is cell-piecewise; skipping affine scan")
            continue
        solutions = fit(intervals)
        if not solutions:
            print("  no joint affine phase solution")
            continue
        print("  solutions", len(solutions))
        for nonzero, coeff in solutions[:20]:
            score = Counter((row["source"], row["target"])
                            for row in sample if fires(row, coeff))
            bad = sum(fires(row, coeff) != bool(row["target"])
                      for row in sample)
            print("   ", coeff, "nz", nonzero, "bad", bad,
                  "selected", dict(score))


if __name__ == "__main__":
    main()
