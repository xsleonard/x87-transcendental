#!/usr/bin/env python3
"""h659: theta ladder — pairwise/XOR mining for the 3/4 pair-bit.

h657g/h tested MARGINALS only; fire = OR/XOR of two hidden balanced
bits is flat in every marginal by construction but glaring in joint
2-bit tables (one of the four cells sits at rate ~0 or ~1 with ~1/4
mass).  This script: over EVERY fireable-band row (region = the h658
tap table, all quadrants and thetas, both corpora), extract ~116
replica bit-features, scan all pairs' joint fire-rate tables, rank by
max deviation z, and verify the top candidates on the m-parity
held-out half.

Smoking-gun criterion: a joint cell with n >= 500 and rate <= 0.02 or
>= 0.98 replicated on the held-out half.
"""
import pickle, sys
from collections import defaultdict
from multiprocessing import Pool

import numpy as np

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

# h658 tap table: (sign, atheta, quad) -> (c0, cb1, cb2, clp, cd)
TAPS = {
    ("dn", 1, (66, 1)): (8, 1, -1, 1, -3),
    ("dn", 1, (67, 0)): (8, 1, -1, 1, -3),
    ("dn", 1, (67, 1)): (2, 1, 0, 0, 4),
    ("dn", 2, (66, 1)): (18, 0, 0, 0, -6),
    ("dn", 2, (67, 0)): (18, 0, 0, 0, -6),
    ("up", 1, (66, 1)): (6, -1, 0, 1, -1),
    ("up", 1, (67, 0)): (6, -1, 0, 1, -1),
    ("up", 1, (67, 1)): (6, 1, 0, -2, 0),
    ("up", 2, (66, 1)): (6, 0, 0, 1, 0),
    ("up", 2, (67, 0)): (6, 0, 0, 1, 0),
    ("up", 2, (67, 1)): (12, 0, 0, 0, 0),
}


def in_region(sign, th, quad, dist, L, b1, b2, M):
    tap = TAPS.get((sign, th, quad))
    if tap is None:
        return False
    a, G1, G2, p, Q, K, par, W = QUAD[quad]
    lp = L % 2
    base = a * L + G1 * b1 + G2 * b2 + p * lp + W(dist)
    c0, cb1, cb2, clp, cd = tap
    T = c0 + cb1 * b1 + cb2 * b2 + clp * lp + cd * (dist - 7)
    if sign == "dn":
        u = K * ((base - T) // Q) + par * lp
        return M < u * UNIT
    u = K * ((base + T) // Q) + par * lp
    return M >= u * UNIT


FEATNAMES = []


def _names():
    n = []
    n += [f"m{i}" for i in range(16)]
    n += [f"sql{i}" for i in range(16)]
    n += [f"sqh{i}" for i in range(60, 66)]
    n += [f"t4l{i}" for i in range(8)]
    n += [f"t4h{i}" for i in range(8)]          # top bits of t4 field
    n += [f"rd{i}" for i in range(16)]
    n += [f"rdh{i}" for i in range(8)]          # top bits of rdisc field
    n += [f"ld{i}" for i in range(8)]
    n += [f"ldh{i}" for i in range(8)]
    n += [f"m2t{i}" for i in range(8)]          # top bits of m^2 tail
    n += [f"f4b{i}" for i in range(4)]
    n += [f"ngb{i}" for i in range(4)]
    n += [f"psb{i}" for i in range(4)]
    n += ["ypar", "srpar", "slpar", "theta2"]
    return n


def feats(args):
    (mhex, sign, th, fire) = args
    m = int(mhex, 16)
    mag = (0, E2M, m)
    square = mul_round(mag, mag, 67, "chop")
    fourth = mul_round(square, square, 67, "chop")
    neg = build_chain(fourth, C6_5, C6_3, C6_1, 67, 64, "rn", False, False, False)
    pos = build_chain(fourth, C6_6, C6_4, C6_2, 67, 64, "rn", False, False, False)
    sq = square[2]
    f4 = sq * sq
    s4 = f4.bit_length() - 67
    t4 = f4 & ((1 << s4) - 1)
    sqlow = sq - (1 << 66)
    M = (sq & 7) * sqlow - t4
    m2 = m * m
    sh = m2.bit_length() - 67
    m2t = m2 & ((1 << sh) - 1)
    rprod = fourth[2] * pos[2]
    sR = rprod.bit_length() - 67
    rd = rprod & ((1 << sR) - 1)
    lprod = sq * neg[2]
    sL = lprod.bit_length() - 67
    ld = lprod & ((1 << sL) - 1)
    q = M // UNIT
    bits = []
    bits += [(m >> i) & 1 for i in range(16)]
    bits += [(sqlow >> i) & 1 for i in range(16)]
    bits += [(sqlow >> i) & 1 for i in range(60, 66)]
    bits += [(t4 >> i) & 1 for i in range(8)]
    bits += [(t4 >> (s4 - 1 - i)) & 1 for i in range(8)]
    bits += [(rd >> i) & 1 for i in range(16)]
    bits += [(rd >> (sR - 1 - i)) & 1 for i in range(8)]
    bits += [(ld >> i) & 1 for i in range(8)]
    bits += [(ld >> (sL - 1 - i)) & 1 for i in range(8)]
    bits += [(m2t >> (sh - 1 - i)) & 1 for i in range(8)]
    bits += [(fourth[2] >> i) & 1 for i in range(4)]
    bits += [(neg[2] >> i) & 1 for i in range(4)]
    bits += [(pos[2] >> i) & 1 for i in range(4)]
    bits += [q & 1, sR & 1, sL & 1, int(th == 2)]
    return (bits, fire, m & 1)


def main():
    global FEATNAMES
    FEATNAMES = _names()
    F = len(FEATNAMES)
    work = []
    for name in ("comb7", "comb8"):
        rows = pickle.load(open(f"h657m_{name}.pkl", "rb"))
        for mhex, theta, dist, s4, side, L, rdisc, sR, label, M, sqlow in rows:
            b1 = 1 if 3 * rdisc >= (1 << sR) else 0
            b2 = 1 if 3 * rdisc >= (1 << (sR + 1)) else 0
            sign = "dn" if theta > 0 else "up"
            if not in_region(sign, abs(theta), (s4, side), dist, L, b1, b2, M):
                continue
            fire = int(label == (1 if sign == "dn" else 2))
            work.append((mhex, sign, abs(theta), fire))
        print(f"{name} scanned; region rows so far {len(work)}", flush=True)

    with Pool(8) as pool:
        out = pool.map(feats, work, chunksize=2000)
    X = np.array([o[0] for o in out], dtype=np.uint8)
    y = np.array([o[1] for o in out], dtype=np.uint8)
    mp = np.array([o[2] for o in out], dtype=np.uint8)
    n = len(y)
    p = y.mean()
    print(f"features ready: n={n} F={F} fire-rate {p:.4f}", flush=True)

    # marginal sanity
    worst = 0.0
    for i in range(F):
        r1 = y[X[:, i] == 1].mean() if (X[:, i] == 1).any() else p
        worst = max(worst, abs(r1 - p))
    print(f"worst marginal deviation: {worst:.4f}", flush=True)

    def scan(mask, tag):
        Xh, yh = X[mask], y[mask]
        ph = yh.mean()
        results = []
        for i in range(F):
            xi = Xh[:, i].astype(np.int8)
            for j in range(i + 1, F):
                v = (xi << 1) | Xh[:, j]
                cnt = np.bincount((v.astype(np.int16) << 1) | yh,
                                  minlength=8).astype(np.float64)
                z = 0.0
                det = []
                for vv in range(4):
                    c0, c1 = cnt[2 * vv], cnt[2 * vv + 1]
                    tot = c0 + c1
                    if tot < 200:
                        continue
                    r = c1 / tot
                    zz = abs(r - ph) * np.sqrt(tot) / np.sqrt(ph * (1 - ph))
                    det.append((vv, int(tot), r))
                    z = max(z, zz)
                results.append((z, i, j, det))
        results.sort(reverse=True)
        print(f"\n[{tag}] top pairs by joint-cell z:")
        for z, i, j, det in results[:15]:
            d = "  ".join(f"{vv:02b}:{t}={r:.3f}" for vv, t, r in det)
            print(f"  z={z:6.2f}  {FEATNAMES[i]} x {FEATNAMES[j]}: {d}",
                  flush=True)
        return results

    resA = scan(mp == 0, "even-m half")
    # verify top-50 on the held-out half
    top = [(i, j) for _, i, j, _ in resA[:50]]
    Xh, yh = X[mp == 1], y[mp == 1]
    ph = yh.mean()
    print("\n[held-out odd-m] replication of top-50 even-m pairs:")
    hits = 0
    for i, j in top[:10]:
        v = (Xh[:, i].astype(np.int16) << 1) | Xh[:, j]
        cnt = np.bincount((v << 1) | yh, minlength=8).astype(np.float64)
        z = 0.0
        det = []
        for vv in range(4):
            c0, c1 = cnt[2 * vv], cnt[2 * vv + 1]
            tot = c0 + c1
            if tot < 200:
                continue
            r = c1 / tot
            z = max(z, abs(r - ph) * np.sqrt(tot) / np.sqrt(ph * (1 - ph)))
            det.append((vv, int(tot), r))
        d = "  ".join(f"{vv:02b}:{t}={r:.3f}" for vv, t, r in det)
        print(f"  z={z:6.2f}  {FEATNAMES[i]} x {FEATNAMES[j]}: {d}",
              flush=True)
        if z > 6:
            hits += 1
    print(f"\nreplicated (z>6) among top-10: {hits}")
    # smoking gun census on full data
    print("\nsmoking-gun scan (any joint cell n>=500 rate<=0.02 or >=0.98):")
    found = 0
    for z, i, j, det in resA[:200]:
        for vv, tot, r in det:
            if tot >= 500 and (r <= 0.02 or r >= 0.98):
                print(f"  {FEATNAMES[i]} x {FEATNAMES[j]} cell {vv:02b}: "
                      f"n={tot} rate={r:.4f}")
                found += 1
    if not found:
        print("  none")


if __name__ == "__main__":
    main()
