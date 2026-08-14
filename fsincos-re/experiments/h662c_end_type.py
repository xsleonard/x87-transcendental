#!/usr/bin/env python3
"""h662c: theta ladder — what decides the block-edge coin?

h662b in the (scale+w)%8 frame: 23 pure cells, 4 mixed — all four at
pm_up + phase == 7 (mod 8), i.e. the propagate run terminating exactly
at a block's top bit, each at rate ~1/2.  One balanced bit remains, in
exactly the block-edge-critical case.

Candidates (this pass caches them all): the run TERMINATOR type at
j = w + pm_up — generate (S_j=1,B_j=0) vs kill (S_j=0,B_j=1); and the
(S,B)-pair types at j-2..j+2.  Inside a propagate run S_i == B_i, so
each run position carries a (0,0)-vs-(1,1) bit invisible to exact
carry logic — exactly what a speculative block scheme could read.

Cache: h662c_rows.pkl =
  (sign, th, fire, pm_up, w, scale8, phw, types[j-2..j+2])
  type: 0 = p0 (S=B=0), 1 = p1 (S=B=1), 2 = g, 3 = k.
"""
import os, pickle, sys
from collections import defaultdict
from multiprocessing import Pool

sys.path.insert(0, "/Users/steve/llm/x87-transcendental/fsincos-re/experiments")
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)

E2M = -66
UNIT = 2**66
CACHE = "h662c_rows.pkl"

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
        d8 = (lp8 - payload) & 0xFF
        if d8 >= 128:
            d8 -= 256
        if d8 == -2:
            payload = lp8
    if active and distance == 8 and low3 == 7 and ud >= 3:
        lane_shift = (left[1] - 8) - right[1]
        lane = (right[2] >> lane_shift) if lane_shift >= 0 \
            else (right[2] << -lane_shift)
        lp8 = lane & 0xFF
        d8 = (lp8 - payload) & 0xFF
        if d8 >= 128:
            d8 -= 256
        if d8 == 0:
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
    w = mag.bit_length() - 67
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

    def ptype(i):
        if i < 0:
            return 4
        si, bi = (S >> i) & 1, (B >> i) & 1
        if si == bi:
            return si            # 0 = p0, 1 = p1
        return 2 if si else 3    # 2 = g (S=1,B=0), 3 = k (S=0,B=1)

    types = tuple(ptype(j + d) for d in (-2, -1, 0, 1, 2))
    return (sign, th, fire, min(pm_up, 24), w, scale % 8,
            (scale + w) % 8, types)


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

    TN = {0: "p0", 1: "p1", 2: "g", 3: "k", 4: "--"}

    # the four mixed cells of h662b: (pm_up, phw) with pm_up+phw == 7 mod 8
    def is_mixed_cell(o):
        return (o[3] + o[6]) % 8 == 7 and o[3] in (7, 8)

    sub = [o for o in out if is_mixed_cell(o)]
    n = len(sub)
    nf = sum(o[2] for o in sub)
    print(f"\nblock-edge-critical rows: {n}, fires {nf} ({nf/n:.4f})")

    # 1) terminator type
    for tag, pos in (("terminator j", 2), ("j-1 (last run bit)", 1),
                     ("j-2", 0), ("j+1", 3), ("j+2", 4)):
        t = defaultdict(lambda: [0, 0])
        for o in sub:
            t[(o[0], o[1], TN[o[7][pos]])][o[2]] += 1
        print(f"\n  [{tag}] fire by (sign, theta, type):")
        for k in sorted(t, key=str):
            c0, c1 = t[k]
            nn = c0 + c1
            if nn < 100:
                continue
            r = c1 / nn
            mark = "  <== SPLIT" if (r <= 0.05 or r >= 0.95) else ""
            print(f"    {k}: n={nn} rate={r:.4f}{mark}", flush=True)

    # 2) joint terminator x (j-1)
    t = defaultdict(lambda: [0, 0])
    for o in sub:
        t[(o[0], TN[o[7][2]], TN[o[7][1]])][o[2]] += 1
    print("\n  [terminator x j-1] fire by (sign, tj, tjm1):")
    for k in sorted(t, key=str):
        c0, c1 = t[k]
        nn = c0 + c1
        if nn < 100:
            continue
        r = c1 / nn
        mark = "  <== SPLIT" if (r <= 0.05 or r >= 0.95) else ""
        print(f"    {k}: n={nn} rate={r:.4f}{mark}", flush=True)

    # 3) sanity: the pure region stays pure under the same features
    pure = [o for o in out if not is_mixed_cell(o)]
    t = defaultdict(lambda: [0, 0])
    for o in pure:
        thr = 8 - o[6] if o[6] else 8   # not used; census only
        t[(o[0], o[3] >= 8 - (o[6] % 8) + (0 if o[6] else 0))][o[2]] += 1
    print("\n(pure-region census by sign for reference)")
    for k in sorted(t, key=str):
        c0, c1 = t[k]
        print(f"    {k}: n={c0 + c1} rate={c1/(c0+c1):.4f}")


if __name__ == "__main__":
    main()
