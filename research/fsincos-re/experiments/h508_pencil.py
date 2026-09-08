#!/usr/bin/env python3
"""h508: refine the dist=9 line ladder at 1/65536 slope resolution and
test the PENCIL hypothesis: the L2 lines (low3=4 XD>=1/3, low3=5 all,
low3=6 XD<1/3) share one pivot (XT=0, m0).

Per dense line: fine slope scan, err-min intercept, band; then a joint
fit forcing a COMMON intercept m0 across the L2 members (grid m0,
per-member best slope); compare summed errors vs independent fits.
Emit h508_lines.json with the empirical law table for Phase C.
"""
import json
from collections import defaultdict
from multiprocessing import Pool
from h500_plane_m import build, load_comb

LINES = {
    "L2_a": (4, (1, 2)),   # low3=4, XD >= 1/3
    "L2_b": (5, (0, 1, 2)),
    "L2_c": (6, (0,)),
    "L3":   (6, (1, 2)),
    "L4_a": (7, (0,)),
    "L4_b": (7, (1, 2)),
}


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


def err_at(pts, s, c):
    e = 0
    for XT, XD, mf, o in pts:
        pred = 1 if mf - s*XT < c else 0
        e += pred != o
    return e


def fine_scan(args):
    name, pts = args
    results = []
    for si in range(int(0.040 * 65536), int(0.095 * 65536) + 1):
        s = si / 65536
        e, c = best_c(pts, s)
        results.append((e, s, c))
    results.sort()
    emin, sb, cb = results[0]
    band = sorted((s, c) for e, s, c in results if e <= emin + 2)
    return name, len(pts), sum(p[3] for p in pts), emin, sb, cb, \
        band[0], band[-1]


def main():
    rows = load_comb()
    with Pool(8) as pool:
        data = pool.map(build, rows, chunksize=1000)
    regions = defaultdict(list)
    for cell, XT, XD, mf, fire in data:
        if cell[0] != 9:
            continue
        reg = 0 if XD < 1/3 else (1 if XD < 0.5 else 2)
        regions[(cell[1], reg)].append((XT, XD, mf, fire))
    lines = {name: [p for lw, regs in [spec] for r in regs
                    for p in regions[(lw, r)]]
             for name, spec in LINES.items()}
    with Pool(6) as pool:
        out = pool.map(fine_scan, sorted(lines.items()), chunksize=1)
    table = {}
    print(f"{'line':6s} {'n':>6s} {'fires':>6s} {'errs':>5s} "
          f"{'slope':>9s} {'c':>9s} {'band(s,c) lo':>20s} "
          f"{'band(s,c) hi':>20s}")
    for name, n, n1, emin, s, c, blo, bhi in sorted(out):
        print(f"{name:6s} {n:6d} {n1:6d} {emin:5d} {s:9.6f} "
              f"{c:9.6f} ({blo[0]:.6f},{blo[1]:.5f}) "
              f"({bhi[0]:.6f},{bhi[1]:.5f})")
        table[name] = dict(n=n, fires=n1, errs=emin, slope=s,
                           intercept=c, slope_band=[blo[0], bhi[0]])
    # pencil: common intercept across L2 members.  For each (member,
    # slope) sort residuals once; then errors at any intercept come
    # from a binary search over fire/clean prefix counts.
    from bisect import bisect_left
    print("\nPENCIL test (L2_a, L2_b, L2_c common intercept):")
    members = ["L2_a", "L2_b", "L2_c"]
    indep = sum(table[m]["errs"] for m in members)
    m0s = [m0i / 2**16 for m0i in range(int(0.7050 * 2**16),
                                        int(0.7105 * 2**16) + 1)]
    slopes = [si / 32768 for si in range(int(0.050 * 32768),
                                         int(0.090 * 32768) + 1)]
    # per member: err(m0, s) matrix as min over slope later
    per_member = []
    for m in members:
        pts = lines[m]
        best_for_m0 = [(None, None)] * len(m0s)
        for s in slopes:
            rf = sorted(mf - s*XT for XT, XD, mf, o in pts if o)
            rc = sorted(mf - s*XT for XT, XD, mf, o in pts if not o)
            for k, m0 in enumerate(m0s):
                # fire pred iff r < m0: errors = fires with r >= m0
                #                              + cleans with r < m0
                e = (len(rf) - bisect_left(rf, m0)) + \
                    bisect_left(rc, m0)
                if best_for_m0[k][0] is None or e < best_for_m0[k][0]:
                    best_for_m0[k] = (e, s)
        per_member.append(best_for_m0)
    best = None
    for k, m0 in enumerate(m0s):
        tot = sum(per_member[j][k][0] for j in range(3))
        if best is None or tot < best[0]:
            best = (tot, m0, [per_member[j][k][1] for j in range(3)])
    tot, m0, ss = best
    print(f"  independent-fit total errs: {indep}")
    print(f"  common-pivot best: total errs={tot} at m0={m0:.6f} "
          f"slopes={[round(s, 6) for s in ss]}")
    print(f"  1/slopes: {[round(1/s, 4) for s in ss]}")
    d1 = 1/ss[1] - 1/ss[0]
    d2 = 1/ss[2] - 1/ss[1]
    print(f"  1/s arithmetic? diffs {d1:.4f} {d2:.4f}")
    table["pencil"] = dict(total_errs=tot, m0=m0,
                           slopes=ss, indep_errs=indep)
    json.dump(table, open("h508_lines.json", "w"), indent=1)
    print("wrote h508_lines.json")


if __name__ == "__main__":
    main()
