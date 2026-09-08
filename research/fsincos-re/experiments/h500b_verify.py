#!/usr/bin/env python3
"""h500b: verify and rationalize the (XT, m) planes.
For the four near/exact strata: (1) split-half — fit on half A
(perceptron), count errors on half B; (2) boundary corridor — per XT
bin, the gap between max-m-of-fires and min-m-of-cleans; corridor
slope/intercept bounds via LP-free scan; (3) violator listing for
strata with <=33 total errors; (4) nice-rational candidates inside
the corridor."""
import random
from collections import defaultdict
from multiprocessing import Pool
from h500_plane_m import build, load_comb

TARGETS = [(9, 2, 0), (9, 2, 1), (9, 3, 0), (9, 3, 1)]

def fit(pts, epochs=3000):
    w = [0.0, 0.0, 0.0]
    best = (len(pts), None)
    for ep in range(epochs):
        errs = 0
        for x, mf, o in pts:
            s = w[0]*x + w[1]*mf + w[2]
            pred = 1 if s > 0 else 0
            if pred != o:
                errs += 1
                sgn = 1.0 if o else -1.0
                w[0] += sgn * x * 0.5
                w[1] += sgn * mf * 0.5
                w[2] += sgn * 0.5
        if errs < best[0]:
            best = (errs, list(w))
        if errs == 0:
            break
    return best[1]

def main():
    rows = load_comb()
    with Pool(8) as pool:
        data = pool.map(build, rows, chunksize=1000)
    strata = defaultdict(list)
    for cell, XT, XD, mf, fire in data:
        if cell in TARGETS:
            strata[cell].append((XT, mf, fire))
    rnd = random.Random(500)
    for cell in TARGETS:
        pts = strata[cell]
        rnd.shuffle(pts)
        half = len(pts)//2
        A, B = pts[:half], pts[half:]
        w = fit(A)
        if w is None:
            print(f"{cell}: no fit")
            continue
        eB = sum(1 for x, mf, o in B
                 if (1 if w[0]*x + w[1]*mf + w[2] > 0 else 0) != o)
        print(f"\n{cell}: n={len(pts)} split-half: heldout errs "
              f"{eB}/{len(B)}")
        # corridor: slope/intercept feasibility over line
        # m = s*XT + t (fire below): for grid of s, compute needed t
        # range: t must be >= max over fires (mf - s*x) NO:
        # fire <=> mf < s*x + t: t > mf - s*x for fires;
        # t <= mf - s*x for cleans
        best = None
        import math
        for si in range(0, 61):
            s = si / 200.0             # slope 0..0.30
            lo = max((mf - s*x) for x, mf, o in pts if o)
            hi = min((mf - s*x) for x, mf, o in pts if not o)
            if lo < hi:
                if best is None or (hi - lo) > best[2]:
                    best = (s, (lo+hi)/2, hi-lo, lo, hi)
        if best:
            s, t, wgap, lo, hi = best
            print(f"  EXACT corridor: slope={s:.3f} intercept in "
                  f"[{lo:.6f}, {hi:.6f}] (gap {wgap:.2e})")
            for num, den in ((1, 8), (1, 16), (3, 32), (1, 4),
                             (5, 32), (1, 12), (1, 10), (7, 64)):
                if abs(s - num/den) < 0.011:
                    print(f"    slope ~ {num}/{den}")
        else:
            # count min errors at best slope
            errbest = None
            for si in range(0, 61):
                s = si / 200.0
                vals = sorted((mf - s*x, o) for x, mf, o in pts)
                n1 = sum(o for _, o in vals)
                pre1 = 0
                bb = n1
                for i, (_, o) in enumerate(vals):
                    pre1 += o
                    e = (i+1) - pre1 + (n1 - pre1)
                    e = (i + 1 - pre1) + (n1 - pre1)
                    if e < bb:
                        bb = e
                if errbest is None or bb < errbest[0]:
                    errbest = (bb, s)
            print(f"  no exact corridor; best line errs="
                  f"{errbest[0]} at slope {errbest[1]:.3f}")

if __name__ == "__main__":
    main()
