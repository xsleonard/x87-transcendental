#!/usr/bin/env python3
"""h662b: theta ladder — pm_up block-phase test (the 8-bit lattice).

h662: fire <=> pm_up (propagate run above the chop boundary) crosses a
threshold: >=9 always fires (exact), 7 fires at 1/2, 8 direction-
dependent.  Hypothesis: the hardware adder resolves carries in 8-bit
blocks on a FIXED lattice; the borrow is mispredicted iff the
propagate run crosses a block edge.  Then the true threshold in pm_up
is 8 - phase + const where phase = the chop boundary's position mod 8
in the right alignment frame — and the residual 1/2-mixing at
pm_up in {7,8} is the phase varying row to row.

Cross-tab fire by (sign, theta, pm_up, phase) for candidate phase
frames: scale%8, (scale+w)%8, w%8, bitlen%8, le%8, (le-scale)%8.
Rows cached to h662b_rows.pkl for iteration.
"""
import os, pickle, sys
from collections import defaultdict
from multiprocessing import Pool

sys.path.insert(0, "/Users/steve/llm/x87-transcendental/fsincos-re/experiments")
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)

E2M = -66
UNIT = 2**66
CACHE = "h662b_rows.pkl"

QUAD = {
    (66, 1): (2, 2, 1,  0, 4, 1, 0, lambda d: -5 * (d - 7)),
    (66, 0): (4, 1, 0,  0, 2, 1, 0, lambda d: -9 - 5 * (d - 9)),
    (67, 0): (4, 2, 1, -2, 4, 2, 1, lambda d: -5 * (d - 7)),
    (67, 1): (2, 2, 3, -3, 8, 2, 1, lambda d: -4 - 2 * (d - 7)),
}
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


def stats(args):
    mhex, sign, th, fire = args
    m = int(mhex, 16)
    mag0 = (0, E2M, m)
    square = mul_round(mag0, mag0, 67, "chop")
    fourth = mul_round(square, square, 67, "chop")
    neg = build_chain(fourth, C6_5, C6_3, C6_1, 67, 64, "rn", False, False, False)
    pos = build_chain(fourth, C6_6, C6_4, C6_2, 67, 64, "rn", False, False, False)
    left = mul_round(square, neg, 67, "chop")
    right = mul_round(fourth, pos, 67, "chop")
    product = square[2] * neg[2]
    shift = max(product.bit_length() - 67, 0)
    discarded = product & ((1 << shift) - 1) if shift > 0 else 0
    ud = (discarded << 3) >> shift if shift > 0 else 0
    u5d = (discarded << 5) >> shift if shift > 0 else 0
    rproduct = fourth[2] * pos[2]
    rshift = max(rproduct.bit_length() - 67, 0)
    rdisc = rproduct & ((1 << rshift) - 1) if rshift > 0 else 0
    rud = (rdisc << 1) >> rshift if rshift > 0 else 0
    low3 = square[2] & 7
    distance = abs(left[1] - right[1])
    active = 1 if (low3 and (ud or (distance == 7 and u5d))) else 0
    payload = low3 + 8 - distance if active else 0
    if active and distance == 10 and low3 == 6 and rud:
        lane_shift = (left[1] - 8) - right[1]
        lane = (right[2] >> lane_shift) if lane_shift >= 0 \
            else (right[2] << -lane_shift)
        lp8 = lane & 0xFF
        diffc = (lp8 - payload) & 0xFF
        if diffc >= 128:
            diffc -= 256
        if diffc == -2:
            payload = lp8
    if active and distance == 8 and low3 == 7 and ud >= 3:
        lane_shift = (left[1] - 8) - right[1]
        lane = (right[2] >> lane_shift) if lane_shift >= 0 \
            else (right[2] << -lane_shift)
        lp8 = lane & 0xFF
        diffc = (lp8 - payload) & 0xFF
        if diffc >= 128:
            diffc -= 256
        if diffc == 0:
            payload -= 1
    scale = min(left[1], right[1])
    if payload and left[1] - 8 < scale:
        scale = left[1] - 8
    A = left[2] << (left[1] - scale)
    B = right[2] << (right[1] - scale)
    P = (payload << (left[1] - 8 - scale)) if payload else 0
    S = A + P
    mag = S - B
    if mag <= 0:
        return None
    bl = mag.bit_length()
    w = bl - 67
    if w <= 0:
        return None
    Wd = max(S.bit_length(), B.bit_length()) + 2
    maskW = (1 << Wd) - 1
    pmask = (~(S ^ B)) & maskW
    pm_up = 0
    j = w
    while (pmask >> j) & 1:
        pm_up += 1
        j += 1
    return (sign, th, fire, min(pm_up, 24), w, scale % 8,
            (scale + w) % 8, bl % 8, left[1] % 8, (left[1] - scale) % 8)


PH = ["scale%8", "(scale+w)%8", "bitlen%8", "le%8", "(le-scale)%8"]


def main():
    if os.path.exists(CACHE):
        out = pickle.load(open(CACHE, "rb"))
        print(f"{len(out)} rows from cache", flush=True)
    else:
        work = []
        for name in ("comb7", "comb8"):
            rows = pickle.load(open(f"h657m_{name}.pkl", "rb"))
            for (mhex, theta, dist, s4, side, L, rdisc, sR, label, M,
                 sqlow) in rows:
                b1 = 1 if 3 * rdisc >= (1 << sR) else 0
                b2 = 1 if 3 * rdisc >= (1 << (sR + 1)) else 0
                sign = "dn" if theta > 0 else "up"
                if not in_region(sign, abs(theta), (s4, side), dist, L,
                                 b1, b2, M):
                    continue
                fire = int(label == (1 if sign == "dn" else 2))
                work.append((mhex, sign, abs(theta), fire))
            print(f"{name} loaded", flush=True)
        with Pool(8) as pool:
            out = pool.map(stats, work, chunksize=2000)
        out = [o for o in out if o is not None]
        pickle.dump(out, open(CACHE, "wb"))
        print(f"cached {len(out)}", flush=True)

    # joint (pm_up, phase) tables per candidate phase frame
    for pi, pname in enumerate(PH):
        t = defaultdict(lambda: [0, 0])
        for o in out:
            sign, th, fire, pm_up, wv = o[0], o[1], o[2], o[3], o[4]
            ph = o[5 + pi]
            t[(sign, pm_up, ph)][fire] += 1
        # exactness: count cells that are pure 0 or pure 1
        pure = mixed = 0
        mixrows = 0
        lines = []
        for k in sorted(t, key=str):
            c0, c1 = t[k]
            n = c0 + c1
            if n < 200:
                continue
            r = c1 / n
            if r <= 0.005 or r >= 0.995:
                pure += 1
            else:
                mixed += 1
                mixrows += n
                lines.append(f"      MIXED {k}: n={n} rate={r:.4f}")
        print(f"\n[{pname}] pure cells {pure}, mixed {mixed} "
              f"({mixrows} rows):")
        for ln in lines[:25]:
            print(ln, flush=True)


if __name__ == "__main__":
    main()
