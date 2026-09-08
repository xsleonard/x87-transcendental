#!/usr/bin/env python3
"""h487c: inspect the rows that violate each cell's best step fit.
For each mixed cell: fit the best single/composite threshold (min
errors), then print every violator's position relative to the
threshold (distance in units of the cell's quantity spread) plus its
other quantities' percentiles -- distinguishing 'needs a small extra
term' (violators hug the threshold) from 'second input overrides'
(violators far away)."""
from collections import defaultdict
from multiprocessing import Pool
from h487b_fullprec import build_row, COMPS, SC
from h484_cegis import load_labels

def main():
    rows = load_labels()
    with Pool(8) as pool:
        data = [r for r in pool.map(build_row, sorted(rows.items()),
                                    chunksize=50) if r]
    cells = defaultdict(list)
    for o, cell, q in data:
        cells[cell].append((o, q))
    for cell in sorted(cells):
        rs_ = cells[cell]
        if len(rs_) < 8:
            continue
        n1 = sum(o for o, _ in rs_)
        if n1 == 0 or n1 == len(rs_):
            continue
        best = None
        for name, fn in COMPS:
            vals = sorted((fn(q), o, q) for o, q in rs_)
            labs = [o for _, o, _ in vals]
            # best up threshold
            for direction in ("up", "down"):
                ll = labs if direction == "up" else \
                    [1 - x for x in labs]
                errs_at = [sum(1 for x in ll[:i] if x == 1)
                           + sum(1 for x in ll[i:] if x == 0)
                           for i in range(len(ll) + 1)]
                e = min(errs_at)
                if best is None or e < best[0]:
                    i = errs_at.index(e)
                    best = (e, name, direction, i, vals)
        e, name, direction, i, vals = best
        if e == 0 or e > 4:
            continue
        xs = [v for v, _, _ in vals]
        lo, hi = min(xs), max(xs)
        spread = (hi - lo) or 1
        th = xs[i] if i < len(xs) else hi
        print(f"\n{cell} n={len(rs_)} fires={n1}: best {name} "
              f"{direction} errs={e}, theta={th/2**SC:.6f}")
        for j, (x, o, q) in enumerate(vals):
            wrong = (o == 1) != ((j >= i) == (direction == "up"))
            if wrong:
                reldist = (x - th) / spread
                others = " ".join(
                    f"{nm}={q[nm]/2**SC:.4f}" for nm in
                    ("XT", "XD", "XP", "XE"))
                print(f"    VIOL o={o} x={x/2**SC:.6f} "
                      f"rel-dist={reldist:+.3f}  {others}")

if __name__ == "__main__":
    main()
