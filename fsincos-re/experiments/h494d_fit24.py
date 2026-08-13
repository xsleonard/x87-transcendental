#!/usr/bin/env python3
"""h494d: upgraded digit-selection fit — 24ths grid, up to 4 XT
regions, prefix-sum optimized.  Fit ONLY on h491 map data; lock
strata with zero fit errors for fresh validation."""
import json
from collections import defaultdict
from multiprocessing import Pool
from h493_curvefit import build
SC = 60
ONE = 1 << SC
G = 24

def fit_stratum(args):
    cell, pts = args
    tw = [i * ONE // G for i in range(G + 1)] + [ONE * 2]
    NL = len(tw)
    pts = sorted(pts, key=lambda p: p[0])
    n = len(pts)
    xts = [p[0] for p in pts]
    # prefix arrays per level: fires with XD<lv ; cleans with XD>=lv
    pre = []
    for lv in tw:
        a = [0] * (n + 1)
        b = [0] * (n + 1)
        for i, (XT, XD, XP, XE, fire) in enumerate(pts):
            a[i + 1] = a[i] + (1 if fire and XD < lv else 0)
            b[i + 1] = b[i] + (1 if (not fire) and XD >= lv else 0)
        pre.append((a, b))
    import bisect
    cuts = [bisect.bisect_left(xts, t) for t in
            [i * ONE // G for i in range(G + 1)]]
    cuts = sorted(set([0] + cuts + [n]))
    idx = cuts

    def span_best(i, j):
        best = None
        for li in range(NL):
            a, b = pre[li]
            e = (a[j] - a[i]) + (b[j] - b[i])
            if best is None or e < best[0]:
                best = (e, li)
        return best

    span_cache = {}
    def sb(i, j):
        if (i, j) not in span_cache:
            span_cache[(i, j)] = span_best(i, j)
        return span_cache[(i, j)]

    best = None
    K = len(idx)
    for a_ in range(K):
        for b_ in range(a_, K):
            for c_ in range(b_, K):
                i1, i2, i3 = idx[a_], idx[b_], idx[c_]
                e = (sb(0, i1)[0] + sb(i1, i2)[0]
                     + sb(i2, i3)[0] + sb(i3, n)[0])
                if best is None or e < best[0]:
                    best = (e, (i1, i2, i3))
    e, (i1, i2, i3) = best
    lvls = [sb(0, i1)[1], sb(i1, i2)[1], sb(i2, i3)[1],
            sb(i3, n)[1]]
    bps = [xts[i] if i < n else ONE * 2 for i in (i1, i2, i3)]
    # snap breakpoints to the 24ths grid value just above
    bps = [min(range(G + 1),
               key=lambda t: abs(t * ONE // G - bp)) for bp in bps]
    return cell, n, e, bps, lvls

def main():
    rows = []
    with open("h491_mapdata.tsv") as fh:
        fh.readline()
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if f[7] in ("CLEAN", "FIRE"):
                rows.append((f[0], f[7] == "FIRE"))
    with Pool(8) as pool:
        data = pool.map(build, rows, chunksize=500)
    strata = defaultdict(list)
    for cell, XT, XD, XP, XE, fire in data:
        strata[cell].append((XT, XD, XP, XE, fire))
    jobs = [(c, pts) for c, pts in sorted(strata.items())
            if len(pts) >= 500]
    with Pool(8) as pool:
        out = pool.map(fit_stratum, jobs, chunksize=1)
    tables = {}
    for cell, n, e, bps, lvls in out:
        claimed = e == 0
        print(f"  {cell} n={n} fit-errs={e}"
              f"{'  LOCKED' if claimed else ''}  bps/24={bps} "
              f"lvls/24={lvls}")
        if claimed:
            tables["|".join(str(x) for x in cell)] = {
                "bps": bps, "levels": lvls, "n": n}
    with open("h494_locked_v2.json", "w") as fh:
        json.dump(tables, fh, indent=1)
    print(f"\nlocked v2: {len(tables)} strata")

if __name__ == "__main__":
    main()
