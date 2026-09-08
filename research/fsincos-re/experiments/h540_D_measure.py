#!/usr/bin/env python3
"""h540: MEASURE the resolver delta D along the validated law
boundaries (inversion payoff, stage 2).

At theta=0, u-side: req2=+1 (old-frame clean R) requires D >= gap_up;
req2=0 (old fire R-1) requires D < gap_up.  Near a law boundary the
two classes interleave in mf, so within a fine (stratum, XD, XT)
neighborhood the brackets intersect to a narrow interval:
    L = max gap_up over req2=+1 rows   <=  D  <  U = min gap_up over
    req2=0 rows.
Consistent, narrow [L, U) = a direct measurement of D's value there.
Violations (L >= U) measure how much of D is NOT a function of
(stratum, XD, XT) at this resolution.

Output: h540_pins.tsv — one line per neighborhood: counts, L, U
(hex), width in bits, representative row m; census on stdout.
"""
import math
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h539_D_library import qrow
from fcos_tie_rule import boundary

UCUT = 0.002


def work(rows):
    out = defaultdict(lambda: [0, None, 0, None, None, None])
    # key -> [n_lo, L, n_hi, U, mrep_lo, mrep_hi]
    for mhex, theta, lab, ce in rows:
        (m, sqv, f4v, rfv, t4, rdisc, A, P, M, k, R, B_full,
         rsh, bshift, dist, low3) = qrow(mhex)
        F = rsh - bshift
        if F < 0:
            continue
        kf = k + F
        APf = (A + P) << F
        EU = (APf - B_full) >> kf
        Vlow = (APf - B_full) - (EU << kf)
        req2 = (R + {"clean": 0, "down": -1, "up": 1}[lab]) - EU
        if req2 not in (0, 1):
            continue
        gap_up = (1 << kf) - Vlow
        s4 = (sqv * sqv).bit_length() - 67
        XT = t4 / 2**s4
        XD = rdisc / 2**rsh
        mf = m / 2**64
        line = boundary(dist, low3, XT, XD, mf)
        if line is None:
            continue
        s, c = line
        u = mf - s * XT - c
        if abs(u) > UCUT:
            continue
        key = (dist, low3, ce, int(XD * 48), int(XT * 24))
        cell = out[key]
        if req2 == 1:
            cell[0] += 1
            if cell[1] is None or gap_up > cell[1]:
                cell[1] = gap_up
                cell[4] = mhex
        else:
            cell[2] += 1
            if cell[3] is None or gap_up < cell[3]:
                cell[3] = gap_up
                cell[5] = mhex
    return dict(out)


def main():
    rows = []
    seen = set()
    raw = []
    for line in open("ties_comb7.txt"):
        f = line.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        raw.append(f)
    inputs = sorted(f[0] for f in raw)
    order = {m2: i for i, m2 in enumerate(inputs)}
    st = {md: open(f"comb7_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    labeled = []
    for f in raw:
        theta = int(f[9])
        if theta != 0:
            continue
        R, ce = int(f[7], 16), int(f[8])
        i = order[f[0]]
        hw, bad = [], False
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        if bad:
            continue
        refs = {name: [final_cosine_result(-(R + d), ce, md)
                       for md in ROUNDING_MODES]
                for name, d in (("clean", 0), ("down", -1),
                                ("up", 1))}
        for name in ("clean", "down", "up"):
            if hw == refs[name]:
                labeled.append((f[0], theta, name, ce))
                break
    print(f"theta=0 labeled: {len(labeled)}", flush=True)
    chunks = [labeled[i::8] for i in range(8)]
    with Pool(8) as pool:
        parts = pool.map(work, chunks)
    agg = defaultdict(lambda: [0, None, 0, None, None, None])
    for part in parts:
        for key, cell in part.items():
            a = agg[key]
            a[0] += cell[0]
            a[2] += cell[2]
            if cell[1] is not None and (a[1] is None
                                        or cell[1] > a[1]):
                a[1], a[4] = cell[1], cell[4]
            if cell[3] is not None and (a[3] is None
                                        or cell[3] < a[3]):
                a[3], a[5] = cell[3], cell[5]
    npin = nviol = nonesided = 0
    widths = []
    with open("h540_pins.tsv", "w") as fh:
        fh.write("dist\tlow3\tce\txd48\txt24\tn_lo\tn_hi\tL_hex\t"
                 "U_hex\twidth_bits\tm_lo\tm_hi\n")
        for key in sorted(agg):
            n_lo, L, n_hi, U, mlo, mhi = agg[key]
            if L is None or U is None:
                nonesided += 1
                continue
            if L >= U:
                nviol += 1
                wb = -1.0
            else:
                npin += 1
                wb = math.log2(U - L)
                widths.append((wb, math.log2(U)))
            fh.write(f"{key[0]}\t{key[1]}\t{key[2]}\t{key[3]}\t"
                     f"{key[4]}\t{n_lo}\t{n_hi}\t{L:x}\t{U:x}\t"
                     f"{wb:.2f}\t{mlo}\t{mhi}\n")
    print(f"neighborhoods pinned: {npin}, violated: {nviol}, "
          f"one-sided: {nonesided}")
    if widths:
        widths.sort()
        n = len(widths)
        print("pin width bits (log2(U-L)): "
              f"min={widths[0][0]:.1f} med={widths[n//2][0]:.1f} "
              f"p90={widths[9*n//10][0]:.1f}")
        tight = [w for w in widths if w[0] < w[1] - 8]
        print(f"pins tighter than 1/256 of scale: {len(tight)}")


if __name__ == "__main__":
    main()
