#!/usr/bin/env python3
"""h507: empirical free-slope table for every dist=9 stratum, with the
XD-region model from h506-B2 (step at 1/3) applied where it wins.

For each (9, low3): partition rows by XD region (<1/3, [1/3,1/2),
[1/2,1)) pooling BOTH rud strata (rud is XD's top bit — h506 showed
the frame variable dissolves).  Per region: fine slope scan (1/8192
steps over [0.03, 0.30]), error-minimizing intercept, near-optimal
band, half-intercept check.  Output: empirical (slope, intercept)
per (low3, region) — the raw material for the law's true form.
"""
from collections import defaultdict
from multiprocessing import Pool
from h500_plane_m import build, load_comb


def best_c(pts, s):
    vals = sorted((mf - s*XT, o) for XT, XD, mf, o in pts)
    ns = sum(o for _, o in vals)
    pre1 = 0
    bb, bc = ns, None
    for i, (r, o) in enumerate(vals):
        pre1 += o
        e = (i + 1 - pre1) + (ns - pre1)
        if e < bb:
            bb, bc = e, r
    return bb, bc


def scan_region(args):
    key, pts = args
    n = len(pts)
    n1 = sum(p[3] for p in pts)
    if n1 == 0 or n1 == n or n < 800:
        return (key, n, n1, None)
    results = []
    for si in range(int(0.03 * 8192), int(0.30 * 8192) + 1, 2):
        s = si / 8192
        e, c = best_c(pts, s)
        results.append((e, s, c))
    results.sort()
    emin, sbest, cbest = results[0]
    band = sorted(s for e, s, c in results if e <= emin + 2)
    lo_half = [p for p in pts if p[0] < 0.5]
    hi_half = [p for p in pts if p[0] >= 0.5]
    _, cl = best_c(lo_half, sbest) if len(lo_half) > 400 else (0, None)
    _, ch = best_c(hi_half, sbest) if len(hi_half) > 400 else (0, None)
    return (key, n, n1, (emin, sbest, cbest, band[0], band[-1],
                         cl, ch))


def main():
    rows = load_comb()
    with Pool(8) as pool:
        data = pool.map(build, rows, chunksize=1000)
    regions = defaultdict(list)
    for cell, XT, XD, mf, fire in data:
        if cell[0] != 9:
            continue
        low3 = cell[1]
        reg = 0 if XD < 1/3 else (1 if XD < 0.5 else 2)
        regions[(low3, reg)].append((XT, XD, mf, fire))
        regions[(low3, 9)].append((XT, XD, mf, fire))  # pooled
    with Pool(8) as pool:
        out = pool.map(scan_region, sorted(regions.items()),
                       chunksize=1)
    names = {0: "XD<1/3 ", 1: "[1/3,.5)", 2: "XD>=1/2 ",
             9: "POOLED  "}
    print(f"{'low3':>4s} {'region':8s} {'n':>6s} {'fires':>6s} "
          f"{'errs':>5s} {'slope':>8s} {'band-lo':>8s} "
          f"{'band-hi':>8s} {'1/slope':>7s} {'c':>8s} "
          f"{'c_lo':>8s} {'c_hi':>8s}")
    for (low3, reg), n, n1, res in out:
        if res is None:
            tag = ("all-fire" if n1 == n and n else
                   "no-fire" if n1 == 0 else "small")
            print(f"{low3:4d} {names[reg]:8s} {n:6d} {n1:6d}  "
                  f"PURE/{tag}")
            continue
        emin, s, c, blo, bhi, cl, ch = res
        print(f"{low3:4d} {names[reg]:8s} {n:6d} {n1:6d} "
              f"{emin:5d} {s:8.5f} {blo:8.5f} {bhi:8.5f} "
              f"{1/s:7.3f} {c:8.5f} "
              f"{cl if cl is None else round(cl, 5)!s:>8s} "
              f"{ch if ch is None else round(ch, 5)!s:>8s}")


if __name__ == "__main__":
    main()
