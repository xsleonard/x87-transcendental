#!/usr/bin/env python3
"""h1034: derive a closed-form tap vector for the TOP/act0 selector.

h1030 established the invariant behind the remaining +/-1 errors: TOP
targets are exactly the rows where the terminal subtractor substitutes
P[cut]=1 for the true carry-in 0.  h1033 then found that, after restricting
to that selector population, all TOP/act0 targets form an exact upper tail
of the Round-60 coordinate

    M = low3 * (square - 2^66) - (square^2 mod 2^s4).

This script converts those row constraints into intervals for a small tap
inside the already-derived Round-60 u-floor, then enumerates

    T = c0 + cL*low3 + cb1*b1 + cb2*b2
           + clp*(low3&1) + cd*(dist-7).

Unlike the old statistical fits, every target-present and target-impossible
row is checked at full integer precision.  Ambiguous rows are deliberately
left unconstrained.
"""

from collections import defaultdict
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path


ONE = 1 << 66
HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "stageA" / "h991"


def load_h1033_rows():
    """Load h1033 without duplicating its verified reconstruction code."""
    spec = importlib.util.spec_from_file_location(
        "h1033_selector_monotonicity", HERE / "h1033_selector_monotonicity.py")
    module = importlib.util.module_from_spec(spec)
    old_cwd = Path.cwd()
    try:
        import os
        os.chdir(DATA)
        with redirect_stdout(io.StringIO()):
            spec.loader.exec_module(module)
    finally:
        os.chdir(old_cwd)
    return module.rows


QUAD = {
    (66, 1): (2, 2, 1, 0, 4, 1, 0, lambda d: -5 * (d - 7)),
    (66, 0): (4, 1, 0, 0, 2, 1, 0, lambda d: -9 - 5 * (d - 9)),
    (67, 0): (4, 2, 1, -2, 4, 2, 1, lambda d: -5 * (d - 7)),
    (67, 1): (2, 2, 3, -3, 8, 2, 1, lambda d: -4 - 2 * (d - 7)),
}


def base_and_u(row, tap):
    qa, qg1, qg2, qp, qq, qk, qpar, wd = QUAD[row["s4"], row["side"]]
    lp = row["low3"] & 1
    base = (qa * row["low3"] + qg1 * row["b1"] + qg2 * row["b2"]
            + qp * lp + wd(row["dist"]))
    return base, qk * ((base + tap) // qq) + qpar * lp


def label(row):
    if row["pinned"] and row["n"] == -1:
        return 1
    if -1 not in row["nset"]:
        return 0
    return None


def cell_intervals(sample, limit=512):
    cells = defaultdict(list)
    for row in sample:
        lab = label(row)
        if lab is not None:
            cells[(row["dist"], row["low3"], row["b1"], row["b2"])].append(
                (row, lab))

    intervals = {}
    for cell, rr in cells.items():
        feasible = []
        for tap in range(-limit, limit + 1):
            good = True
            for row, lab in rr:
                _, u = base_and_u(row, tap)
                predicted = row["mreg"] >= u * ONE
                if predicted != bool(lab):
                    good = False
                    break
            if good:
                feasible.append(tap)
        if not feasible:
            intervals[cell] = None
            continue
        if feasible != list(range(feasible[0], feasible[-1] + 1)):
            raise AssertionError((cell, "non-contiguous tap set", feasible))
        lo = None if feasible[0] == -limit else feasible[0]
        hi = None if feasible[-1] == limit else feasible[-1]
        intervals[cell] = lo, hi
    return cells, intervals


def signed_shell(dimensions, weight, prefix=()):
    """Yield integer vectors having exactly the requested L1 weight."""
    if dimensions == 1:
        if weight == 0:
            yield prefix + (0,)
        else:
            yield prefix + (weight,)
            yield prefix + (-weight,)
        return
    for magnitude in range(weight + 1):
        values = (0,) if magnitude == 0 else (magnitude, -magnitude)
        for value in values:
            yield from signed_shell(
                dimensions - 1, weight - magnitude, prefix + (value,))


def fit_intervals(intervals, max_slope_weight=28):
    """Intersect cell intervals, enumerating affine forms by complexity."""
    if any(interval is None for interval in intervals.values()):
        return []
    solutions = []
    best_weight = None
    # Slopes are (cL, cb1, cb2, clp, cd).  Enumerating L1 shells finds the
    # simplest form without paying the Cartesian 33^5 cost.
    for slope_weight in range(max_slope_weight + 1):
        if best_weight is not None and slope_weight > best_weight:
            break
        for cL, cb1, cb2, clp, cd in signed_shell(5, slope_weight):
            c0lo, c0hi = -512, 512
            for (dist, low3, b1, b2), (lo, hi) in intervals.items():
                rest = (cL * low3 + cb1 * b1 + cb2 * b2
                        + clp * (low3 & 1) + cd * (dist - 7))
                if lo is not None:
                    c0lo = max(c0lo, lo - rest)
                if hi is not None:
                    c0hi = min(c0hi, hi - rest)
                if c0lo > c0hi:
                    break
            if c0lo > c0hi:
                continue
            c0 = min(max(0, c0lo), c0hi)
            coeff = c0, cL, cb1, cb2, clp, cd
            weight = slope_weight + abs(c0)
            nonzero = sum(value != 0 for value in coeff)
            if best_weight is None or weight < best_weight:
                best_weight = weight
                solutions = []
            if weight == best_weight:
                solutions.append((weight, nonzero, coeff))
    return sorted(solutions)


def verify(sample, coeff):
    c0, cL, cb1, cb2, clp, cd = coeff
    counts = defaultdict(int)
    bad = []
    for row in sample:
        lab = label(row)
        if lab is None:
            counts["ambiguous"] += 1
            continue
        tap = (c0 + cL * row["low3"]
               + cb1 * row["b1"] + cb2 * row["b2"]
               + clp * (row["low3"] & 1) + cd * (row["dist"] - 7))
        _, u = base_and_u(row, tap)
        predicted = row["mreg"] >= u * ONE
        counts["positive" if lab else "negative"] += 1
        counts["predicted"] += predicted
        if predicted != bool(lab):
            bad.append((row, lab, tap, u))
    return counts, bad


def fit_group(name, sample):
    cells, intervals = cell_intervals(sample)
    positives = sum(label(row) == 1 for row in sample)
    negatives = sum(label(row) == 0 for row in sample)
    print(f"\n{name}: rows={len(sample)} labeled={positives}+/{negatives}- "
          f"cells={len(cells)}")
    if positives == 0:
        print("  no positive rows: selector is identically false")
        return None
    impossible = [cell for cell, interval in intervals.items()
                  if interval is None]
    if impossible:
        print("  scalar tap impossible in cells", impossible)
        return None
    for cell in sorted(intervals):
        np = sum(lab for _, lab in cells[cell])
        nn = len(cells[cell]) - np
        print(f"  cell={cell} rows={np}+/{nn}- T={intervals[cell]}")
    solutions = fit_intervals(intervals)
    if not solutions:
        print("  no affine tap solution in coefficient range")
        return None
    print(f"  solutions={len(solutions)}; simplest:")
    for weight, nonzero, coeff in solutions[:12]:
        counts, bad = verify(sample, coeff)
        print(f"    {coeff} weight={weight} nz={nonzero} "
              f"pred={counts['predicted']} bad={len(bad)}")
    return solutions[0][2]


def main():
    rows = load_h1033_rows()
    eligible = [row for row in rows if row["line"] == "TOP"
                and row["act"] == 0 and row["pcut"] == 1]
    groups = defaultdict(list)
    for row in eligible:
        theta = 256 - row["sum8"]
        groups[(theta, row["s4"], row["side"])].append(row)

    selected = {}
    for key in sorted(groups):
        selected[key] = fit_group(str(key), groups[key])

    print("\nselected", selected)
    print("unrepresented positives by group:")
    for key in sorted(groups):
        positive = sum(label(row) == 1 for row in groups[key])
        if positive or selected[key] is not None:
            print(f"  {key}: positives={positive} tap={selected[key]}")


if __name__ == "__main__":
    main()
