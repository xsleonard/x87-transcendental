#!/usr/bin/env python3
"""h617: replace the per-(zone, st) offset TABLE with a
per-zone STEP  c(st) = c_lo + (c_hi - c_lo) * [st >= t],
c in [-8, 8], t in 0..64 — motivated by h613 (1,090/1,327
zones are exact 2-level steps; 2,576 offsets clipped at the
old [-3,3] edge; thresholds on an 8/3 lattice).

Fit on train half (same hash as h602), score held-out
j-interval coverage:
  J1  = zone (q,a,b) + offset table (current model semantics,
        refit here for comparability)
  JS  = zone (q,a,b) + step (c_lo, c_hi, t)
  JS3 = JS with t restricted to the 8/3 lattice
        (t in {0, 3, 6, 8, 11, 14, 16, 19, 22, 24, 27, 30, 32,
         35, 38, 40, 43, 46, 48, 51, 54, 56, 59, 62} ~ round(8k/3))
Rows: h602_rows.tsv + h604_rows.tsv (all stratum-sides).
"""
from collections import defaultdict
from multiprocessing import Pool

LAT = sorted(set(round(8 * k / 3) for k in range(25)))


def load():
    zones = defaultdict(list)
    for fn in ("h602_rows.tsv", "h604_rows.tsv"):
        for line in open(fn):
            f = line.split()
            key = (int(f[1]), int(f[2]), int(f[3]), f[4])
            half, tau, mf = int(f[5]), float(f[6]), float(f[7])
            jlo, jhi, st, xd12 = (int(f[8]), int(f[9]),
                                  int(f[10]), int(f[11]))
            if jlo > jhi:
                continue
            zones[(key, xd12)].append((half, tau, mf, jlo, jhi,
                                       st))
    return zones


def fit_zone(args):
    zid, rows = args
    from h598_jframe import QGRID, AGRID
    tr = [(t, m, lo, hi, s) for h, t, m, lo, hi, s in rows
          if h == 0]
    te = [(t, m, lo, hi, s) for h, t, m, lo, hi, s in rows
          if h == 1]
    if not tr or not te:
        return zid, None
    if len(tr) > 20000:
        tr = tr[::len(tr) // 20000 + 1]
    # base (q, a, b) by interval stabbing (const-j fast path)
    best = (-1, None)
    for j in range(-16, 17):
        n = sum(1 for t, m, lo, hi, s in tr if lo <= j <= hi)
        if n == len(tr):
            best = (n, (0.0, 0.0, float(j)))
            break
    if best[1] is None:
        for q in QGRID:
            for a in AGRID:
                ev = []
                for (t, m, lo, hi, s) in tr:
                    x = q * t + a * m
                    ev.append((lo - 0.5 - x, 1))
                    ev.append((hi + 0.5 - x, -1))
                ev.sort()
                cur, bc, bb = 0, -1, 0.0
                for pos, d in ev:
                    cur += d
                    if cur > bc:
                        bc, bb = cur, pos + 1e-9
                if bc > best[0]:
                    best = (bc, (q, a, bb))
    q, a, b = best[1]
    # J1 table: per-st best c in [-8, 8]
    coff = defaultdict(lambda: defaultdict(int))
    for (t, m, lo, hi, s) in tr:
        x = q * t + a * m + b
        for c in range(-8, 9):
            if lo <= round(x + c) <= hi:
                coff[s][c] += 1
    ctab = {s: max(v, key=lambda c: (v[c], -abs(c)))
            for s, v in coff.items()}
    # step fits: residual coverage per (s, c) reused
    def step_fit(lattice):
        bs = (-1, None)
        cvals = sorted(set(ctab.values()) | {0})
        for t0 in (lattice if lattice else range(0, 65)):
            for clo in cvals:
                for chi in cvals:
                    n = 0
                    for s, v in coff.items():
                        c = clo if s < t0 else chi
                        n += v.get(c, 0)
                    if n > bs[0]:
                        bs = (n, (t0, clo, chi))
        return bs[1]
    stp = step_fit(None)
    stp3 = step_fit(LAT)
    # held-out
    ok1 = oks = oks3 = 0
    for (t, m, lo, hi, s) in te:
        x = q * t + a * m + b
        c1 = ctab.get(s, 0)
        ok1 += lo <= round(x + c1) <= hi
        t0, clo, chi = stp
        oks += lo <= round(x + (clo if s < t0 else chi)) <= hi
        t0, clo, chi = stp3
        oks3 += lo <= round(x + (clo if s < t0 else chi)) <= hi
    return zid, (len(te), ok1, oks, oks3, stp3)


def main():
    zones = load()
    print(f"zones: {len(zones)}", flush=True)
    jobs = sorted(zones.items(), key=lambda kv: str(kv[0]))
    with Pool(14) as pool:
        res = pool.map(fit_zone, jobs, chunksize=1)
    per_key = defaultdict(lambda: [0, 0, 0, 0])
    thr_census = defaultdict(int)
    for zid, r in res:
        if r is None:
            continue
        nte, ok1, oks, oks3, stp3 = r
        pk = per_key[zid[0]]
        pk[0] += nte
        pk[1] += ok1
        pk[2] += oks
        pk[3] += oks3
        if stp3 and stp3[1] != stp3[2]:
            thr_census[stp3[0]] += 1
    g = [0, 0, 0, 0]
    print(f"{'stratum-side':22s} {'n_te':>8s} {'J1c8':>7s} "
          f"{'JS':>7s} {'JS3':>7s}")
    for key in sorted(per_key, key=str):
        n, o1, os_, o3 = per_key[key]
        if n == 0:
            continue
        print(f"{str(key):22s} {n:8d} {o1 / n:7.4f} "
              f"{os_ / n:7.4f} {o3 / n:7.4f}")
        for i in range(4):
            g[i] += per_key[key][i]
    print(f"{'GLOBAL':22s} {g[0]:8d} {g[1] / g[0]:7.4f} "
          f"{g[2] / g[0]:7.4f} {g[3] / g[0]:7.4f}")
    print("step thresholds (8/3-lattice fits, non-degenerate):",
          dict(sorted(thr_census.items())))


if __name__ == "__main__":
    main()
