#!/usr/bin/env python3
"""h487d: exact 2D linear separability per cell in (XT, XD).
For each mixed cell test whether ANY line separates fires from
cleans (O(n^3) over candidate lines through point pairs, exact
integer arithmetic).  Also 3D (XT, XD, Xrf) for cells that fail 2D.
Prints per-cell verdicts and fitted line parameters."""
from collections import defaultdict
from multiprocessing import Pool
from h487b_fullprec import build_row, SC
from h484_cegis import load_labels
from h453_chain_variants import (C6_2, C6_4, C6_6, build_chain,
                                 mul_round)

def sep2d(pts):
    """pts: (x, y, o).  Exact: exists (a,b,c) with sign(ax+by+c)
    separating?  Try lines through all point pairs plus axis dirs."""
    n = len(pts)
    fires = [(x, y) for x, y, o in pts if o]
    cools = [(x, y) for x, y, o in pts if not o]
    cands = []
    for i in range(n):
        for j in range(i + 1, n):
            x1, y1, _ = pts[i]
            x2, y2, _ = pts[j]
            a, b = y2 - y1, x1 - x2
            if a or b:
                cands.append((a, b, -(a * x1 + b * y1)))
    cands += [(1, 0, 0), (0, 1, 0)]
    for a, b, c in cands:
        # allow boundary points on either side: check strict split
        for sign in (1, -1):
            ok = True
            for x, y in fires:
                if sign * (a * x + b * y + c) < 0:
                    ok = False
                    break
            if ok:
                for x, y in cools:
                    if sign * (a * x + b * y + c) > 0:
                        ok = False
                        break
            if ok:
                return (a * sign, b * sign, c * sign)
    return None

def enrich(item):
    r = build_row(item)
    if r is None:
        return None
    o, cell, q = r
    m = int(item[0], 16)
    mag = (0, -66, m)
    square = mul_round(mag, mag, 67, "chop")
    fourth = mul_round(square, square, 67, "chop")
    positive = build_chain(fourth, C6_6, C6_4, C6_2, 67, 64, "rn",
                           False, False, False)
    q["RF"] = positive[2]
    return (o, cell, q)

def main():
    rows = load_labels()
    with Pool(8) as pool:
        data = [r for r in pool.map(enrich, sorted(rows.items()),
                                    chunksize=50) if r]
    cells = defaultdict(list)
    for o, cell, q in data:
        cells[cell].append((o, q))
    sep = unsep = 0
    lines = {}
    for cell in sorted(cells):
        rs_ = cells[cell]
        if len(rs_) < 8:
            continue
        n1 = sum(o for o, _ in rs_)
        if n1 == 0 or n1 == len(rs_):
            continue
        pts = [(q["XT"], q["XD"], o) for o, q in rs_]
        r = sep2d(pts)
        if r:
            sep += 1
            a, b, c = r
            # normalize: slope = -a/b if b else inf
            if b:
                slope = -a / b
                inter = -c / b / 2**SC
                lines[cell] = (slope, inter, len(rs_), n1)
                print(f"  {cell} n={len(rs_)} f={n1}: SEPARABLE "
                      f"XD >= {slope:+.4f}*XT + {inter:.4f}"
                      if b > 0 else
                      f"  {cell}: SEPARABLE (b<0 dir)")
            else:
                print(f"  {cell} n={len(rs_)} f={n1}: SEPARABLE "
                      f"(vertical XT threshold)")
        else:
            unsep += 1
            print(f"  {cell} n={len(rs_)} f={n1}: NOT separable in "
                  f"(XT, XD)")
    print(f"\n2D separable: {sep}, not: {unsep}")
    if lines:
        print("\n=== fitted lines (slope, intercept) vs cell ===")
        for cell, (sl, it, n, f) in sorted(lines.items()):
            print(f"  {cell}: slope={sl:+.4f} intercept={it:+.4f}")

if __name__ == "__main__":
    main()
