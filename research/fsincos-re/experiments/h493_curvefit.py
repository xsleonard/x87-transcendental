#!/usr/bin/env python3
"""h493: boundary curve fitting on the dense map.

Per (dist, low3, le2, rud) stratum:
  a) extract theta_D(XT) at 24 XT-bins (50 percent crossings);
  b) free-angle linear boundary in THREE planes: (XT, XD),
     (XP, XD) with XP = t4*rf exact fraction, (XE, XT);
     whichever plane straightens the boundary names the correct
     variable pairing;
  c) residuals of the best linear fit per XT-bin (staircase check).
Prints per-stratum winners + total errors per plane; boundary curves
for the two biggest strata.  Run from /tmp/stageA.
"""
import math
from collections import defaultdict
from multiprocessing import Pool
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)
from h492c_le2_threshold import step_errs
E2M = -66
SC = 60

def build(args):
    mhex, fire = args
    m = int(mhex, 16)
    mag = (0, E2M, m)
    square = mul_round(mag, mag, 67, "chop")
    fourth = mul_round(square, square, 67, "chop")
    negative = build_chain(fourth, C6_5, C6_3, C6_1, 67, 64, "rn",
                           False, False, False)
    positive = build_chain(fourth, C6_6, C6_4, C6_2, 67, 64, "rn",
                           False, False, False)
    left = mul_round(square, negative, 67, "chop")
    right = mul_round(fourth, positive, 67, "chop")
    f4_full = square[2] * square[2]
    s4 = f4_full.bit_length() - 67
    t4 = f4_full & ((1 << s4) - 1)
    rprod = fourth[2] * positive[2]
    sR = rprod.bit_length() - 67
    rdisc = rprod & ((1 << sR) - 1)
    low3 = square[2] & 7
    dist = abs(left[1] - right[1])
    rud = rdisc >> (sR - 1)
    XT = (t4 << SC) >> s4
    XD = (rdisc << SC) >> sR
    XP = ((t4 * positive[2]) << SC) >> (s4 + 64)
    XE = (((rdisc << s4) + t4 * positive[2]) << SC) >> (sR + s4)
    return ((dist, low3, left[1], rud), XT, XD, XP, XE, fire)

def sweep(pts, xi, yi):
    n1 = sum(p[-1] for p in pts)
    best = min(n1, len(pts) - n1)
    besta = None
    for i in range(-24, 73):
        a = i * math.pi / 96
        ca, sa = math.cos(a), math.sin(a)
        e, _ = step_errs([(ca * p[xi] + sa * p[yi], p[-1])
                          for p in pts])
        if e < best:
            best, besta = e, a
    return best, besta

def fit_stratum(args):
    cell, pts = args
    e_td, a_td = sweep(pts, 0, 1)
    e_pd, a_pd = sweep(pts, 2, 1)
    e_et, a_et = sweep(pts, 3, 0)
    return cell, len(pts), e_td, e_pd, e_et, a_td, a_pd, a_et

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
            if len(pts) >= 500
            and 0 < sum(p[-1] for p in pts) < len(pts)]
    with Pool(8) as pool:
        out = pool.map(fit_stratum, jobs, chunksize=1)
    t_td = t_pd = t_et = tn = 0
    print(f"{'stratum':22s} {'n':>6s} {'(XT,XD)':>8s} {'(XP,XD)':>8s} "
          f"{'(XE,XT)':>8s}  winner")
    for cell, n, e_td, e_pd, e_et, a_td, a_pd, a_et in out:
        tn += n
        t_td += e_td
        t_pd += e_pd
        t_et += e_et
        w = min((e_td, "TD"), (e_pd, "PD"), (e_et, "ET"))
        print(f"{str(cell):22s} {n:6d} {e_td:8d} {e_pd:8d} "
              f"{e_et:8d}  {w[1]} ({w[0]/n:.3f})")
    print(f"\nTOTALS over {tn}: (XT,XD) {t_td} "
          f"({1-t_td/tn:.4f}) | (XP,XD) {t_pd} ({1-t_pd/tn:.4f}) | "
          f"(XE,XT) {t_et} ({1-t_et/tn:.4f})")

    # boundary curves + linear residuals, two biggest strata
    for cell, pts in sorted(strata.items(),
                            key=lambda kv: -len(kv[1]))[:2]:
        print(f"\n--- boundary theta_D(XT), stratum {cell} "
              f"n={len(pts)} ---")
        bins = defaultdict(list)
        for XT, XD, XP, XE, fire in pts:
            bins[XT * 24 >> SC].append((XD, fire))
        curve = []
        for b in sorted(bins):
            sub = bins[b]
            if len(sub) < 60:
                continue
            db = defaultdict(lambda: [0, 0])
            for d, fi in sub:
                x = db[d * 48 >> SC]
                x[0] += 1
                x[1] += fi
            rates = [(x, db[x][1] / db[x][0]) for x in sorted(db)
                     if db[x][0] >= 4]
            th = None
            for i in range(len(rates) - 1):
                if rates[i][1] < 0.5 <= rates[i + 1][1]:
                    th = (rates[i][0] + rates[i + 1][0]) / 2
                    break
            curve.append((b, len(sub), th))
        for b, n, th in curve:
            bar = "" if th is None else " " * int(th) + "*"
            print(f"  XTbin={b:2d} n={n:4d} thD48="
                  f"{'%5.1f' % th if th is not None else '  n/a'} "
                  f"{bar}")

if __name__ == "__main__":
    main()
