#!/usr/bin/env python3
"""h495e: (1) holdout ceiling of (stratum, m-bins, T, D) tables;
(2) cross-stratum boundary alignment — at each stratum's fitted
m-threshold, print the values of m, rf, R, sq at the boundary; the
quantity that is ~constant across strata is the physical one."""
import random
from collections import defaultdict
from multiprocessing import Pool
from h495d_magnitude import build
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result

def main():
    # reuse merged labels via h495d's loader logic (duplicated here)
    rows = []
    with open("h491_mapdata.tsv") as fh:
        fh.readline()
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if f[7] in ("CLEAN", "FIRE"):
                rows.append((f[0], f[7] == "FIRE"))
    fresh = []
    seen = set()
    for line in open("ties_fresh.txt"):
        f = line.split()
        if f[0] not in seen:
            seen.add(f[0])
            fresh.append(f)
    inputs = sorted(f[0] for f in fresh)
    order = {mm: i for i, mm in enumerate(inputs)}
    st = {md: open(f"fcos2_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    for f in fresh:
        R = int(f[7], 16)
        ce = int(f[8])
        i = order[f[0]]
        hw = []
        bad = False
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        if bad:
            continue
        clean = [final_cosine_result(-R, ce, md)
                 for md in ROUNDING_MODES]
        fired = [final_cosine_result(-(R-1), ce, md)
                 for md in ROUNDING_MODES]
        if hw == clean:
            rows.append((f[0], False))
        elif hw == fired:
            rows.append((f[0], True))
    dedup = {}
    for mhex, fire in rows:
        dedup[mhex] = fire
    rows = sorted(dedup.items())
    with Pool(8) as pool:
        data = pool.map(build, rows, chunksize=500)
    # need XT/XD too: recompute quickly from m via h493 build
    from h493_curvefit import build as build93
    with Pool(8) as pool:
        d93 = pool.map(build93, rows, chunksize=500)

    merged = []
    for (stratum, m, R, ls, rf, sq, fire), \
            (cell, XT, XD, XP, XE, _f) in zip(data, d93):
        merged.append((stratum[:2] + (stratum[3],), m, XT, XD, rf, R,
                       sq, fire))
    rnd = random.Random(495)
    halves = [rnd.random() < 0.5 for _ in merged]

    def acc(keyfn):
        rule = defaultdict(lambda: [0, 0])
        for d, h in zip(merged, halves):
            if not h:
                rule[keyfn(d)][d[-1]] += 1
        hit = tot = 0
        for d, h in zip(merged, halves):
            if h:
                k = keyfn(d)
                if k in rule:
                    r = rule[k]
                    hit += (r[1] > r[0]) == d[-1]
                    tot += 1
        return hit / tot, tot

    print("=== holdout ladder with m-bins ===")
    for name, fn in (
        ("strat+T4+D4", lambda d: (d[0], d[2] >> 56, d[3] >> 56)),
        ("strat+m4+T4+D4", lambda d: (d[0], d[1] >> 60,
                                      d[2] >> 56, d[3] >> 56)),
        ("strat+m5+T4+D4", lambda d: (d[0], d[1] >> 59,
                                      d[2] >> 56, d[3] >> 56)),
        ("strat+m6+T4+D4", lambda d: (d[0], d[1] >> 58,
                                      d[2] >> 56, d[3] >> 56)),
        ("strat+m6+T3+D3", lambda d: (d[0], d[1] >> 58,
                                      d[2] >> 57, d[3] >> 57)),
        ("strat+m7+T3+D3", lambda d: (d[0], d[1] >> 57,
                                      d[2] >> 57, d[3] >> 57)),
    ):
        a, t = acc(fn)
        print(f"  {name:16s} {a:.4f} (n={t})")

    print("\n=== cross-stratum boundary alignment ===")
    strata = defaultdict(list)
    for d in merged:
        strata[d[0]].append(d)
    print(f"{'stratum':16s} {'n':>6s} {'m50':>18s} {'rf50':>18s} "
          f"{'R50':>19s}")
    for s in sorted(strata):
        pts = sorted(strata[s], key=lambda d: d[1])
        n = len(pts)
        n1 = sum(d[-1] for d in pts)
        if n < 500 or n1 == 0 or n1 == n:
            continue
        # 50 percent crossing in m via binned rates
        bins = defaultdict(lambda: [0, 0])
        for d in pts:
            b = bins[d[1] >> 57]
            b[0] += 1
            b[1] += d[-1]
        rates = [(b, bins[b][1] / bins[b][0]) for b in sorted(bins)
                 if bins[b][0] >= 30]
        mth = None
        for i in range(len(rates) - 1):
            if rates[i][1] > 0.5 >= rates[i + 1][1]:
                mth = (rates[i][0] + 0.5) * (1 << 57)
                break
        if mth is None:
            continue
        # values of rf, R at rows nearest the m boundary
        near = min(pts, key=lambda d: abs(d[1] - mth))
        print(f"{str(s):16s} {n:6d} {mth/2**64:18.6f} "
              f"{near[4]/2**64:18.6f} {near[5]/2**67:19.6f}")

if __name__ == "__main__":
    main()
