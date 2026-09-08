#!/usr/bin/env python3
"""h605: attack on the residual pockets — steep-family twins
((9,1)/(9,2)@-73 up, W1) and the (8,x,-72) up family
([0xC8,0xF0)).

AUTOPSY: with the current selector form (affine per xd12 zone +
c in [-3,3] per (zone, state)): where do held-out misses live
(xd12, mf octile, theta, |j - nearest feasible|)?

EXTENSIONS (same fit/test discipline; steep twins split by
position parity, (8,x) by m-hash half):
  V0: xd12 zones, c +-3          (current form)
  V1: (xd12, mf8) zones, c +-3   (piecewise-mf = curvature)
  V2: (xd12, mf2) zones, c +-3
  V3: xd12 zones, c +-6
  V4: (xd12, mf8) zones, c +-6
Report held-out per pocket stratum per variant.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h598_jframe import QGRID, AGRID

CAP = 20000
POCKETS_86 = {(8, 1, -72, "up"), (8, 2, -72, "up"),
              (8, 4, -72, "up"), (8, 5, -72, "up"),
              (8, 6, -72, "up"), (8, 7, -72, "up")}
POCKETS_W1 = {(9, 1, -73, "up"), (9, 2, -73, "up"),
              (9, 4, -73, "dn"), (9, 5, -73, "dn")}


def fit_zone(args):
    zid, rows = args
    fitr = rows if len(rows) <= CAP else rows[::len(rows)
                                             // CAP + 1]
    for j in range(-16, 17):
        if all(jlo <= j <= jhi for tau, mf, jlo, jhi, st
               in fitr if jlo <= jhi):
            return zid, (0.0, 0.0, float(j))
    best = (-1, None)
    for q in QGRID:
        for a in AGRID:
            ev = []
            for (tau, mf, jlo, jhi, st) in fitr:
                if jlo > jhi:
                    continue
                x = q * tau + a * mf
                ev.append((jlo - 0.5 - x, 1))
                ev.append((jhi + 0.5 - x, -1))
            if not ev:
                continue
            ev.sort()
            cur = 0
            bc = -1
            bb = 0.0
            for pos, d in ev:
                cur += d
                if cur > bc:
                    bc = cur
                    bb = pos + 1e-9
            if bc > best[0]:
                best = (bc, (q, a, bb))
    return zid, best[1]


def run_variant(rows, zonef, crange, pool):
    """rows: (istrain, tau, mf, jlo, jhi, st, xd12, theta).
    Returns (heldout_acc, missrows)."""
    zrows = defaultdict(list)
    for r in rows:
        if r[0]:
            zrows[zonef(r)].append((r[1], r[2], r[3], r[4],
                                    r[5]))
    fits = dict(pool.map(fit_zone, sorted(zrows.items(),
                                          key=lambda kv:
                                          str(kv[0])),
                         chunksize=1))
    coff = defaultdict(lambda: defaultdict(int))
    for r in rows:
        if not r[0] or r[3] > r[4]:
            continue
        z = zonef(r)
        f = fits.get(z)
        if f is None:
            continue
        q, a, b = f
        x = q * r[1] + a * r[2] + b
        for c in range(-crange, crange + 1):
            if r[3] <= round(x + c) <= r[4]:
                coff[(z, r[5])][c] += 1
    cbest = {k: max(v, key=v.get) for k, v in coff.items()}
    ok = n = 0
    miss = []
    for r in rows:
        if r[0]:
            continue
        n += 1
        z = zonef(r)
        f = fits.get(z)
        if f is None:
            continue
        q, a, b = f
        x = q * r[1] + a * r[2] + b + cbest.get((z, r[5]), 0)
        j = round(x)
        if r[3] <= j <= r[4]:
            ok += 1
        else:
            dist = min(abs(j - r[3]), abs(j - r[4]))
            miss.append((r[6], min(7, int(r[2] * 8)), r[7],
                         dist))
    return ok / max(n, 1), miss


def main():
    data = defaultdict(list)
    for line in open("h602_rows.tsv"):
        f = line.split()
        key = (int(f[1]), int(f[2]), int(f[3]), f[4])
        if key not in POCKETS_86:
            continue
        data[key].append((int(f[5]) == 0, float(f[6]),
                          float(f[7]), int(f[8]), int(f[9]),
                          int(f[10]), int(f[11]), 0))
    for line in open("h604_rows.tsv"):
        f = line.split()
        key = (int(f[1]), int(f[2]), int(f[3]), f[4])
        if key not in POCKETS_W1:
            continue
        data[key].append((int(f[5]) % 2 == 0, float(f[6]),
                          float(f[7]), int(f[8]), int(f[9]),
                          int(f[10]), int(f[11]), 0))
    VARIANTS = [
        ("V1 xd12xmf8/c3", lambda r: (r[6],
                                      min(7, int(r[2] * 8))),
         3),
        ("V5 xd12xmf16/c3", lambda r: (r[6],
                                       min(15,
                                           int(r[2] * 16))),
         3),
        ("V6 xd12xmf32/c3", lambda r: (r[6],
                                       min(31,
                                           int(r[2] * 32))),
         3),
        ("V7 xd12xmf16/c6", lambda r: (r[6],
                                       min(15,
                                           int(r[2] * 16))),
         6),
    ]
    with Pool(15) as pool:
        for key in sorted(data, key=str):
            rows = data[key]
            n_te = sum(1 for r in rows if not r[0])
            line = f"{str(key):20s} n_te={n_te:7d} "
            missv0 = None
            for name, zf, cr in VARIANTS:
                acc, miss = run_variant(rows, zf, cr, pool)
                line += f"{name.split()[0]}={acc:.4f} "
                if name.startswith("V1"):
                    missv0 = miss
            print(line, flush=True)
            if missv0:
                byxd = defaultdict(int)
                bymf = defaultdict(int)
                bydist = defaultdict(int)
                for xd, mf8, theta, dist in missv0:
                    byxd[xd] += 1
                    bymf[mf8] += 1
                    bydist[min(dist, 4)] += 1
                print(f"   V0 misses: xd12={dict(sorted(byxd.items()))} "
                      f"mf8={dict(sorted(bymf.items()))} "
                      f"jdist={dict(sorted(bydist.items()))}",
                      flush=True)


if __name__ == "__main__":
    main()
