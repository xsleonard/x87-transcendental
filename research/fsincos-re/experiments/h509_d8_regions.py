#!/usr/bin/env python3
"""h509: dist=8 structure from comb-3 — free-slope per (low3,
XD-region), after scoring the LOCKED h505 predictions (P1 pinned
slopes 1/(4*low3); P2 pencil/harmonic form).

Outputs: census (incl. pure/constant strata), per-region free-slope
table (1/8192 then 1/65536 refinement on dense regions), 1/s
arithmetic check, intercept clustering, XD-step check for even low3.
"""
from collections import defaultdict
from multiprocessing import Pool
from h500_plane_m import build
from h505_slopelaw_d8 import load_comb3


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
    if n1 == 0 or n1 == n or n < 800 or min(n1, n - n1) < 30:
        return (key, n, n1, None, None)
    res = []
    for si in range(int(0.02 * 8192), int(0.35 * 8192) + 1, 2):
        s = si / 8192
        e, c = best_c(pts, s)
        res.append((e, s, c))
    res.sort()
    emin, sb, cb = res[0]
    # refine around best at 1/65536
    res2 = []
    for si in range(int((sb - 0.004) * 65536),
                    int((sb + 0.004) * 65536) + 1):
        s = si / 65536
        e, c = best_c(pts, s)
        res2.append((e, s, c))
    res2.sort()
    emin, sb, cb = res2[0]
    band = sorted(s for e, s, c in res2 if e <= emin + 2)
    coarse_band = sorted(s for e, s, c in res if e <= emin + 2)
    blo = min(band[0], coarse_band[0] if coarse_band else band[0])
    bhi = max(band[-1], coarse_band[-1] if coarse_band else band[-1])
    # locked P1 slope score
    dist, low3, reg = key
    p1 = None
    if low3 > 0:
        s1 = 1.0 / (4 * low3)
        e1, c1 = best_c(pts, s1)
        p1 = (s1, e1, c1)
    return (key, n, n1, (emin, sb, cb, blo, bhi), p1)


def built_comb3():
    import os
    cache = "comb3_built.tsv"
    if os.path.exists(cache):
        data = []
        for line in open(cache):
            d, l3, ru, xt, xd, mf, fi = line.split()
            data.append(((int(d), int(l3), int(ru)), float(xt),
                         float(xd), float(mf), int(fi)))
        return data
    rows = load_comb3()
    with Pool(8) as pool:
        data = pool.map(build, rows, chunksize=1000)
    with open(cache, "w") as f:
        for cell, XT, XD, mf, fire in data:
            f.write(f"{cell[0]} {cell[1]} {cell[2]} {XT!r} {XD!r} "
                    f"{mf!r} {fire}\n")
    return data


def main():
    data = built_comb3()
    regions = defaultdict(list)
    census = defaultdict(int)
    for cell, XT, XD, mf, fire in data:
        dist, low3, rud = cell
        census[dist] += 1
        reg = 0 if XD < 1/3 else (1 if XD < 0.5 else 2)
        regions[(dist, low3, reg)].append((XT, XD, mf, fire))
    print("dist census:", dict(sorted(census.items())))
    jobs = sorted((k, v) for k, v in regions.items())
    with Pool(8) as pool:
        out = pool.map(scan_region, jobs, chunksize=1)
    names = {0: "XD<1/3 ", 1: "[1/3,.5)", 2: "XD>=1/2"}
    print(f"\n{'cell':14s} {'n':>6s} {'fires':>6s} | "
          f"{'errs':>5s} {'slope':>9s} {'1/s':>7s} {'c':>9s} "
          f"{'band':>19s} | {'P1 1/(4*low3)':>13s} {'P1errs':>6s}")
    lines = []
    for key, n, n1, res, p1 in out:
        dist, low3, reg = key
        cellname = f"d{dist} low3={low3} {names[reg]}"
        if res is None:
            tag = ("ALWAYS-FIRE" if n and n1 == n else
                   "NEVER-FIRE" if n1 == 0 else f"sparse({n1})")
            print(f"{cellname:14s} {n:6d} {n1:6d} | {tag}")
            continue
        emin, s, c, blo, bhi = res
        if c is None:
            print(f"{cellname:14s} {n:6d} {n1:6d} | {emin:5d} "
                  f"never-fire optimum (no line beats it)")
            continue
        p1s = f"1/{4*low3}={1/(4*low3):.5f}" if p1 else ""
        p1e = f"{p1[1]}" if p1 else ""
        inb = "IN" if p1 and blo - 1e-9 <= p1[0] <= bhi + 1e-9 \
            else "OUT"
        print(f"{cellname:14s} {n:6d} {n1:6d} | {emin:5d} "
              f"{s:9.6f} {1/s:7.3f} {c:9.6f} "
              f"[{blo:.5f},{bhi:.5f}] | {p1s:>13s} {p1e:>6s} {inb}")
        if dist == 8:
            lines.append((low3, reg, s, c, emin, n))
    # 1/s arithmetic across low3 at fixed region, dist=8
    print("\n1/s by low3 (dist=8):")
    for reg in (0, 1, 2):
        row = [(l3, 1/s, c) for l3, r, s, c, e, n in lines
               if r == reg]
        if len(row) >= 2:
            txt = "  ".join(f"low3={l3}:{inv:.3f}(c={c:.5f})"
                            for l3, inv, c in row)
            print(f"  {names[reg]}: {txt}")
            if len(row) >= 3:
                diffs = [round(row[i+1][1] - row[i][1], 4)
                         for i in range(len(row) - 1)
                         if row[i+1][0] - row[i][0] == 1]
                print(f"    consecutive diffs: {diffs}")


if __name__ == "__main__":
    main()
