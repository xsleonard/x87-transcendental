#!/usr/bin/env python3
"""h657h: theta ladder — deep-state probe of the 3/4 discriminator.

h657g: the 3/4 fire rate in the fireable region is flat in every
sq-derived quantity.  This probe recomputes the full replica from mhex
(h657m caches) for the target cells and cross-tabs fire against state
OUTSIDE sq: exact rdisc low digits, the 3*rdisc tap residue (position
between 8/3-lattice taps), rdisc^2 low field (generate-column
recursion), ldisc and its digits, and the discarded tail of the m*m
squaring itself.  Also: fire autocorrelation between m-adjacent
fireable rows (deterministic-fine-hash vs low-frequency structure).
"""
import pickle, sys
from collections import defaultdict
from multiprocessing import Pool

sys.path.insert(0, "/Users/steve/llm/x87-transcendental/fsincos-re/experiments")
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)

E2M = -66
UNIT = 2**66

QUAD = {
    (66, 1): (2, 2, 1,  0, 4, 1, 0, lambda d: -5 * (d - 7)),
    (66, 0): (4, 1, 0,  0, 2, 1, 0, lambda d: -9 - 5 * (d - 9)),
    (67, 0): (4, 2, 1, -2, 4, 2, 1, lambda d: -5 * (d - 7)),
    (67, 1): (2, 2, 3, -3, 8, 2, 1, lambda d: -4 - 2 * (d - 7)),
}

TARGETS = [
    ("dn", 1, 67, 0, 8, 6, 0),
    ("dn", 1, 67, 0, 8, 4, 2),
    ("dn", 1, 66, 1, 9, 7, 2),
    ("dn", 1, 66, 1, 9, 6, 1),
    ("up", -1, 66, 1, 9, 2, 0),
    ("up", -1, 66, 1, 9, 3, 0),
    ("up", -1, 67, 1, 8, 6, 0),
    ("up", -2, 66, 1, 9, 1, 0),
]


def u_closed(dist, s4, side, L, b1, b2):
    a, G1, G2, p, Q, K, par, W = QUAD[(s4, side)]
    return (K * ((a * L + G1 * b1 + G2 * b2 + p * (L % 2) + W(dist)) // Q)
            + par * (L % 2))


def feats(args):
    mhex, fire = args
    m = int(mhex, 16)
    mag = (0, E2M, m)
    square = mul_round(mag, mag, 67, "chop")
    fourth = mul_round(square, square, 67, "chop")
    neg = build_chain(fourth, C6_5, C6_3, C6_1, 67, 64, "rn", False, False, False)
    pos = build_chain(fourth, C6_6, C6_4, C6_2, 67, 64, "rn", False, False, False)
    sq = square[2]
    m2 = m * m
    sh = m2.bit_length() - 67
    m2tail = m2 & ((1 << sh) - 1)
    rprod = fourth[2] * pos[2]
    sR = rprod.bit_length() - 67
    rdisc = rprod & ((1 << sR) - 1)
    lprod = sq * neg[2]
    sL = lprod.bit_length() - 67
    ldisc = lprod & ((1 << sL) - 1)
    f = {}
    f["m0"] = m & 7
    f["m1"] = (m >> 3) & 7
    f["m2t_o"] = (m2tail << 3) >> sh                    # octile of m^2 tail
    f["m2t_b"] = (m2tail << 1) >> sh                    # top bit
    f["rd0"] = rdisc & 7
    f["rd1"] = (rdisc >> 3) & 7
    f["rd2"] = (rdisc >> 6) & 7
    f["r3_o"] = ((3 * rdisc) % (1 << sR)) * 8 // (1 << sR)   # tap residue
    f["rsq_o"] = ((rdisc * rdisc) % (1 << sR)) * 8 // (1 << sR)
    f["ld0"] = ldisc & 7
    f["ld_o"] = (ldisc << 3) >> sL
    f["l3_o"] = ((3 * ldisc) % (1 << sL)) * 8 // (1 << sL)
    f["p4g"] = (fourth[2] & 1)                          # f4 lsb
    f["ng"] = neg[2] & 3
    f["pg"] = pos[2] & 3
    return (mhex, fire, f)


def main():
    tset = set(TARGETS)
    per_cell = defaultdict(list)
    X60 = 1 << 60
    for name in ("comb7", "comb8"):
        rows = pickle.load(open(f"h657m_{name}.pkl", "rb"))
        for mhex, theta, dist, s4, side, L, rdisc, sR, label, M, sqlow in rows:
            xd60 = (rdisc << 60) >> sR
            b1 = 1 if 3 * xd60 >= X60 else 0
            b2 = 1 if 3 * xd60 >= 2 * X60 else 0
            sign = "dn" if theta > 0 else "up"
            key = (sign, theta, s4, side, dist, L, b1 + b2)
            if key not in tset:
                continue
            u = u_closed(dist, s4, side, L, b1, b2)
            if sign == "dn":
                y = (u * UNIT - M) / UNIT
                fire = int(label == 1)
            else:
                y = (M - u * UNIT) / UNIT
                fire = int(label == 2)
            per_cell[key].append((mhex, y, fire))
        print(f"{name} loaded", flush=True)

    for key in TARGETS:
        pts = per_cell.get(key, [])
        if not pts:
            continue
        byband = defaultdict(list)
        for mhex, y, fire in pts:
            byband[int(y) if y >= 0 else int(y) - 1].append((mhex, fire))
        sub = []
        for b, grp in byband.items():
            nf = sum(g[1] for g in grp)
            if 0 < nf < len(grp):
                sub.extend(grp)
        n = len(sub)
        nf = sum(g[1] for g in sub)
        print(f"\n===== {key}: fireable n={n} fires={nf} ({nf/n:.4f}) =====",
              flush=True)

        # m-adjacency autocorrelation (files are m-sorted per segment)
        sub_sorted = sorted(sub)
        agree = tot = 0
        for i in range(1, len(sub_sorted)):
            a, b = sub_sorted[i - 1][1], sub_sorted[i][1]
            agree += int(a == b)
            tot += 1
        p = nf / n
        exp = p * p + (1 - p) * (1 - p)
        print(f"  m-adjacent agreement: {agree/tot:.4f} "
              f"(iid expectation {exp:.4f})")

        with Pool(8) as pool:
            fr = pool.map(feats, sub, chunksize=500)
        tabs = defaultdict(lambda: defaultdict(lambda: [0, 0]))
        for mhex, fire, f in fr:
            for k, v in f.items():
                tabs[k][v][fire] += 1
        for k in sorted(tabs):
            t = tabs[k]
            flag = ""
            rates = []
            for v in sorted(t):
                c0, c1 = t[v]
                tot2 = c0 + c1
                r = c1 / tot2
                rates.append(f"{v}:{tot2}={r:.3f}")
                if tot2 >= 200 and not 0.71 <= r <= 0.79:
                    flag = "  <== STRUCTURE"
            print(f"  {k:>7}: " + "  ".join(rates) + flag, flush=True)


if __name__ == "__main__":
    main()
