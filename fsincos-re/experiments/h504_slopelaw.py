#!/usr/bin/env python3
"""h504: test the slope law s = 1/(4*payload) per dist=9 stratum.
Pin the slope, find the error-minimizing intercept c; report error
count, the violators' distance-from-boundary distribution (band rows
vs scattered), and a curvature check (optimal c per XT-half)."""
from collections import defaultdict
from multiprocessing import Pool
from h500_plane_m import build, load_comb

def main():
    rows = load_comb()
    with Pool(8) as pool:
        data = pool.map(build, rows, chunksize=1000)
    strata = defaultdict(list)
    for cell, XT, XD, mf, fire in data:
        if cell[0] == 9 and cell[1] >= 2:
            strata[cell].append((XT, XD, mf, fire))
    print(f"{'stratum':12s} {'payload':>7s} {'slope':>8s} {'n':>6s} "
          f"{'errs':>5s} {'rate':>7s} {'in-band':>7s} "
          f"{'c-lo-half':>9s} {'c-hi-half':>9s}")
    for cell in sorted(strata):
        dist, low3, rud = cell
        payload = low3 + 8 - dist
        if payload <= 0:
            continue
        s = 1.0 / (4 * payload)
        pts = strata[cell]
        n1 = sum(p[3] for p in pts)
        if n1 == 0 or n1 == len(pts):
            continue
        def best_c(sub):
            vals = sorted((mf - s*XT, o) for XT, XD, mf, o in sub)
            ns = sum(o for _, o in vals)
            pre1 = 0
            bb, bc = ns, None
            for i, (r, o) in enumerate(vals):
                pre1 += o
                e = (i + 1 - pre1) + (ns - pre1)
                if e < bb:
                    bb, bc = e, r
            if bc is None:
                bc = vals[0][0] - 1.0 if vals else 0.0
            return bb, bc
        errs, c = best_c(pts)
        # violators' distance from boundary
        inband = 0
        for XT, XD, mf, o in pts:
            r = mf - s*XT
            pred = 1 if r < c else 0
            if pred != o and abs(r - c) < 0.003:
                inband += 1
        # curvature: c per XT half
        lo_half = [p for p in pts if p[0] < 0.5]
        hi_half = [p for p in pts if p[0] >= 0.5]
        _, cl = best_c(lo_half) if len(lo_half) > 500 else (0, None)
        _, ch = best_c(hi_half) if len(hi_half) > 500 else (0, None)
        print(f"{str(cell):12s} {payload:7d} 1/{4*payload:<6d} "
              f"{len(pts):6d} {errs:5d} {errs/len(pts):7.4f} "
              f"{inband:7d} "
              f"{cl if cl is None else round(cl,5)!s:>9s} "
              f"{ch if ch is None else round(ch,5)!s:>9s}")

if __name__ == "__main__":
    main()
