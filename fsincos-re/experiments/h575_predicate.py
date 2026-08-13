#!/usr/bin/env python3
"""h575: ZERO-PARAMETER PREDICATE TEST + THE LDISC SHOT.

From h574d band edges (smooth, constant-free to 0.003 quarters):
  dist=8 up:  fire(+1) <=> Vlow >= 2^kf - rdisc*2^(64-rsh)
  dist=9@-72 dn: edges lo=-6120-12XD, hi=11.875-12XD -> derive
  the analogous predicate with its exact constants.
Test at INTEGER precision, variants: exact fractional rdisc
scaling vs floor((rdisc << 64) >> rsh)-style truncation; also
+-1 column.  Score: exact hit rate on the easy sides (target
1.0000).
THE LDISC SHOT: on the HARD sides (dist=8 dn, dist=9 up), after
subtracting the rdisc term, fit the residual threshold against
ldisc = (sq*neg-chain product) discard at fixed columns 60..67
(both signs) — if the hidden component is ldisc-at-a-column the
hard side collapses.  Report per stratum/side accuracy for the
best ldisc column and the no-ldisc baseline.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5,
                                 C6_6, build_chain, mul_round)

E2M = -66


def qrow2(mhex):
    m = int(mhex, 16)
    mag = (0, E2M, m)
    sq = mul_round(mag, mag, 67, "chop")
    f4 = mul_round(sq, sq, 67, "chop")
    neg = build_chain(f4, C6_5, C6_3, C6_1, 67, 64, "rn",
                      False, False, False)
    pos = build_chain(f4, C6_6, C6_4, C6_2, 67, 64, "rn",
                      False, False, False)
    low3 = sq[2] & 7
    L_full = sq[2] * neg[2]
    lsh = L_full.bit_length() - 67
    ldisc = L_full & ((1 << lsh) - 1)
    B_full = f4[2] * pos[2]
    rsh = B_full.bit_length() - 67
    rdisc = B_full & ((1 << rsh) - 1)
    left = mul_round(sq, neg, 67, "chop")
    right = mul_round(f4, pos, 67, "chop")
    dist = abs(left[1] - right[1])
    payload = low3 + 8 - dist
    scale = min(left[1], right[1], left[1] - 8)
    A = left[2] << (left[1] - scale)
    P = payload << (left[1] - 8 - scale)
    M = A + P - (right[2] << (right[1] - scale))
    k = M.bit_length() - 67
    R = M >> k
    return (m, R, A, P, B_full, rsh, rdisc, lsh, ldisc,
            right[1] - scale, k, dist, low3)


def work(rows):
    out = []
    for mhex, theta, lab, ce in rows:
        (m, R, A, P, B_full, rsh, rdisc, lsh, ldisc, bshift,
         k, dist, low3) = qrow2(mhex)
        F = rsh - bshift
        if F < 0:
            continue
        kf = k + F
        APf = (A + P) << F
        res_hw = R + {"clean": 0, "down": -1, "up": 1}[lab]
        EU = (APf - B_full) >> kf
        req2 = res_hw - EU
        Vlow = (APf - B_full) - (EU << kf)
        strat = (dist, low3, ce)
        side = "up" if theta <= 0 else "dn"
        half = (m * 2654435761) & 1
        out.append((strat, side, half, kf, Vlow, rsh, rdisc,
                    lsh, ldisc, req2))
    return out


def main():
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
    stride = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    labeled = []
    for j, f in enumerate(raw):
        if j % stride:
            continue
        R, ce, theta = int(f[7], 16), int(f[8]), int(f[9])
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
    print(f"labeled sample: {len(labeled)}", flush=True)
    chunks = [labeled[i::8] for i in range(8)]
    with Pool(8) as pool:
        parts = pool.map(work, chunks)
    recs = [r for part in parts for r in part]
    # A. zero-param predicate, dist=8 up side
    print("\nA. dist=8 up: req2==+1 <=> Vlow >= 2^kf - "
          "rdisc*2^(64-rsh)  (variants: col 63/64/65, exact-frac)")
    for col in (63, 64, 65):
        agg = defaultdict(lambda: [0, 0])
        for strat, side, half, kf, Vlow, rsh, rdisc, lsh, \
                ldisc, req2 in recs:
            if strat[0] != 8 or side != "up":
                continue
            thr = (1 << kf) - (rdisc << col >> rsh)
            pred = 1 if Vlow >= thr else 0
            a = agg[strat]
            a[1] += 1
            if pred == req2:
                a[0] += 1
        tot = [0, 0]
        for strat in sorted(agg):
            o, n = agg[strat]
            tot[0] += o
            tot[1] += n
        print(f"  col={col}: TOTAL {tot[0]}/{tot[1]} "
              f"({tot[0]/max(tot[1],1):.5f})  " +
              " ".join(f"{s}:{agg[s][0]/agg[s][1]:.5f}"
                       for s in sorted(agg)))
    # B. dist=9@-72 dn: req2 in {0,-1}; predicate from band:
    # down-fire(-1) <=> Vlow < c1 + rdisc*2^(63-rsh)-ish
    print("\nB. dist=9@-72 dn: req2==-1 <=> Vlow < "
          "rdisc*2^(63-rsh) + c ; c scanned small")
    for col in (62, 63, 64):
        for cq in (-16, -12, -8, -4, 0, 4, 8, 12, 16):
            agg = [0, 0]
            for strat, side, half, kf, Vlow, rsh, rdisc, lsh, \
                    ldisc, req2 in recs:
                if strat[:1] != (9,) or strat[2] != -72 or \
                        side != "dn" or strat[1] > 4:
                    continue
                thr = (rdisc << col >> rsh) + \
                    (cq << kf >> 8)  # cq/256 of a unit
                pred = -1 if Vlow < thr else 0
                agg[1] += 1
                if pred == req2:
                    agg[0] += 1
            if agg[1]:
                r = agg[0] / agg[1]
                if r > 0.99:
                    print(f"  col={col} c={cq}/256: "
                          f"{agg[0]}/{agg[1]} ({r:.5f})")
    # C. hard sides: residual vs ldisc columns
    print("\nC. HARD sides: pred with rdisc term + s*ldisc*"
          "2^(cl-lsh); best (s, cl) per stratum")
    for (d0, sideH, colR) in ((8, "dn", 64), (9, "up", 63)):
        for strat0 in sorted(set(r[0] for r in recs
                                 if r[0][0] == d0)):
            rows2 = [r for r in recs
                     if r[0] == strat0 and r[1] == sideH]
            if len(rows2) < 2000:
                continue
            base = [0, 0]
            best = (0.0, None)
            for s in (0, 1, -1):
                cls = (0,) if s == 0 else range(58, 68)
                for cl in cls:
                    ok = n = 0
                    for _, _, half, kf, Vlow, rsh, rdisc, lsh, \
                            ldisc, req2 in rows2:
                        lt = 0 if s == 0 else \
                            s * (ldisc << cl >> lsh)
                        if sideH == "up":
                            thr = (1 << kf) - \
                                (rdisc << colR >> rsh) + lt
                            pred = 1 if Vlow >= thr else 0
                        else:
                            thr = (rdisc << colR >> rsh) + lt
                            pred = -1 if Vlow < thr else 0
                        n += 1
                        if pred == req2:
                            ok += 1
                    r2 = ok / max(n, 1)
                    if s == 0:
                        base = [ok, n]
                    if r2 > best[0]:
                        best = (r2, (s, cl))
            print(f"  {strat0} {sideH}: no-ldisc "
                  f"{base[0]/max(base[1],1):.5f}  best "
                  f"{best[0]:.5f} at {best[1]}")


if __name__ == "__main__":
    main()
