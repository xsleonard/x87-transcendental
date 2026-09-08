#!/usr/bin/env python3
"""h492: conditional-map screen over the 134,621-tie dense dataset.

For each schedule (FCOS, FSINCOS): baseline predictor = per-pixel
majority (pixel = cell x t4 top-4 x rdisc top-4).  For each candidate
variable V (binned to <=16 values): predictor = majority per
(pixel, V).  Train on a random half, test on the other half; report
test accuracy gain over baseline.  The variable that narrows the
FCOS mixing band (and the one that gives FSINCOS structure) is the
next gate input.  Run from /tmp/stageA.
"""
import random
from collections import defaultdict
from multiprocessing import Pool
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)
E2M = -66

def enrich(args):
    mhex, = args
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
    lprod = square[2] * negative[2]
    sL = lprod.bit_length() - 67
    ldisc = lprod & ((1 << sL) - 1)
    P = t4 * positive[2]
    XE = ((rdisc << s4) + P)
    sE = sR + s4
    return {
        "m_lo4": m & 0xF, "m_b4_7": (m >> 4) & 0xF,
        "rf_lo4": positive[2] & 0xF,
        "rf_b4_7": (positive[2] >> 4) & 0xF,
        "rf_b8_11": (positive[2] >> 8) & 0xF,
        "lf_lo4": negative[2] & 0xF,
        "sq_lo4": square[2] & 0xF,
        "ls_b8_11": (left[2] >> 8) & 0xF,
        "rs_b8_11": (right[2] >> 8) & 0xF,
        "rs_b12_15": (right[2] >> 12) & 0xF,
        "t4_b12_15": (t4 >> (s4 - 16)) & 0xF if s4 >= 16 else 0,
        "rd_b12_15": (rdisc >> (sR - 16)) & 0xF if sR >= 16 else 0,
        "ld_hi4": (ldisc >> (sL - 4)) & 0xF if sL >= 4 else 0,
        "XE_fr4": (XE >> (sE - 4)) & 0xF if sE >= 4 else 0,
        "P_hi4": (P >> (s4 + 64 - 4)) & 0xF,
        "le2_off": (left[1] + 74) & 0xF,
        "f4_lo4": fourth[2] & 0xF,
        "ls_lo4": left[2] & 0xF,
    }

def main():
    rows = []
    with open("h491_mapdata.tsv") as fh:
        fh.readline()
        for line in fh:
            f = line.rstrip("\n").split("\t")
            rows.append(f)
    ms = [(f[0],) for f in rows]
    with Pool(8) as pool:
        feats = pool.map(enrich, ms, chunksize=500)
    names = sorted(feats[0])
    rnd = random.Random(492)
    halves = [rnd.random() < 0.5 for _ in rows]

    for which, idx in (("FCOS", 7), ("FSINCOS", 8)):
        data = []
        for f, ft, h in zip(rows, feats, halves):
            if f[idx] not in ("CLEAN", "FIRE"):
                continue
            pixel = (f[1], f[2], f[3], f[4],
                     int(f[5], 16) >> 8, int(f[6], 16) >> 8)
            data.append((pixel, ft, f[idx] == "FIRE", h))
        n_test = sum(1 for d in data if d[3])
        print(f"\n=== {which}: rows {len(data)}, test {n_test} ===")

        def acc(keyfn):
            rule = defaultdict(lambda: [0, 0])
            for pixel, ft, fire, h in data:
                if not h:
                    rule[keyfn(pixel, ft)][fire] += 1
            hit = tot = 0
            for pixel, ft, fire, h in data:
                if h:
                    k = keyfn(pixel, ft)
                    if k in rule:
                        pred = rule[k][1] > rule[k][0]
                        hit += pred == fire
                        tot += 1
            return hit / tot, tot

        base, bt = acc(lambda p, ft: p)
        print(f"  baseline (pixel majority): {base:.4f} on {bt}")
        scored = []
        for nm in names:
            a, t = acc(lambda p, ft, nm=nm: (p, ft[nm]))
            scored.append((a - base, nm, a, t))
        scored.sort(reverse=True)
        for gain, nm, a, t in scored[:10]:
            print(f"  +{gain:+.4f}  {nm:10s} acc={a:.4f} (n={t})")

if __name__ == "__main__":
    main()
