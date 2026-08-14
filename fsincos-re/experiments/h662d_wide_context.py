#!/usr/bin/env python3
"""h662d: theta ladder — the block-edge coin, wide-context hunt.

State: fire = 1 everywhere in the h658 region EXCEPT pm_up+phase == 7
(mod 8) (run ends at a block top), where it is a perfect 1/2 coin flat
in all local terminator bits (h662c).  The 3/4 was 1 x (non-critical)
+ 1/2 x (critical), exactly.

This pass caches the FULL (S,B)-type array around the boundary
(positions w-10 .. j+16; type 0=p0,1=p1,2=g,3=k, 2 bits each) so every
further statistic is computable without terminal rebuilds.  First
analysis: run-p1 parity/count, discard-top types, block-aggregate P/G
of the blocks above and below, and global popcount parities.

Cache: h662d_rows.pkl =
  (sign, th, fire, pm_up, w, phw, base, arr)
  base = w-10 (absolute aligned position of arr[0]);
  arr = int, 2-bit fields, field t = type at position base+t.
"""
import os, pickle, sys
from collections import defaultdict
from multiprocessing import Pool

sys.path.insert(0, "/Users/steve/llm/x87-transcendental/fsincos-re/experiments")
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)

E2M = -66
UNIT = 2**66
CACHE = "h662d_rows.pkl"

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
    pmask_all = ~(S ^ B)
    pm_up = 0
    j = w
    while (pmask_all >> j) & 1:
        pm_up += 1
        j += 1
    base = w - 10
    arr = 0
    for t in range(pm_up + 27):          # base .. j+16
        i = base + t
        if i < 0:
            ty = 0
        else:
            si, bi = (S >> i) & 1, (B >> i) & 1
            ty = si if si == bi else (2 if si else 3)
        arr |= ty << (2 * t)
    return (sign, th, fire, min(pm_up, 24), w, (scale + w) % 8, base, arr)


def get(arr, base, i):
    t = i - base
    return (arr >> (2 * t)) & 3 if t >= 0 else 0


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

    crit = [o for o in out if (o[3] + o[5]) % 8 == 7 and o[3] in (7, 8)]
    n = len(crit)
    print(f"\ncritical rows: {n}, fire rate "
          f"{sum(o[2] for o in crit)/n:.4f}", flush=True)

    def xtab(tag, fn):
        t = defaultdict(lambda: [0, 0])
        for o in crit:
            t[(o[0], fn(o))][o[2]] += 1
        flag = False
        lines = []
        for k in sorted(t, key=str):
            c0, c1 = t[k]
            nn = c0 + c1
            if nn < 150:
                continue
            r = c1 / nn
            mark = ""
            if r <= 0.1 or r >= 0.9:
                mark = "  <== SPLIT"
                flag = True
            elif not 0.45 <= r <= 0.55:
                mark = "  <== lean"
                flag = True
            lines.append(f"    {k}: n={nn} rate={r:.4f}{mark}")
        print(f"\n  [{tag}]" + (" FLAGGED" if flag else ""))
        for ln in lines[:20]:
            print(ln, flush=True)

    def run_p1_count(o):
        sign, th, fire, pm_up, w, phw, base, arr = o
        c = 0
        for i in range(w, w + pm_up):
            if get(arr, base, i) == 1:
                c += 1
        return c

    xtab("run p1 parity", lambda o: run_p1_count(o) & 1)
    xtab("run p1 count mod4", lambda o: run_p1_count(o) & 3)
    xtab("discard top type w-1", lambda o: get(o[7], o[6], o[4] - 1))
    xtab("discard types (w-1,w-2)",
         lambda o: (get(o[7], o[6], o[4] - 1), get(o[7], o[6], o[4] - 2)))
    xtab("discard types (w-3,w-4)",
         lambda o: (get(o[7], o[6], o[4] - 3), get(o[7], o[6], o[4] - 4)))

    def block_above_agg(o):
        # aggregate of the 8 positions above the terminator's block:
        # j is at block top; block above = j+1 .. j+8
        sign, th, fire, pm_up, w, phw, base, arr = o
        j = w + pm_up
        allp = True
        firstg = None
        for i in range(j + 1, j + 9):
            ty = get(arr, base, i)
            if ty >= 2:
                allp = False
                if firstg is None:
                    firstg = ty
        return ("allP" if allp else f"first{'g' if firstg == 2 else 'k'}")

    xtab("block-above aggregate", block_above_agg)

    def p1_in_block_above(o):
        sign, th, fire, pm_up, w, phw, base, arr = o
        j = w + pm_up
        return sum(1 for i in range(j + 1, j + 9)
                   if get(arr, base, i) == 1) & 1

    xtab("p1 parity in block above", p1_in_block_above)

    def below_p1_parity(o):
        sign, th, fire, pm_up, w, phw, base, arr = o
        return sum(1 for i in range(max(0, w - 8), w)
                   if get(arr, base, i) == 1) & 1

    xtab("p1 parity in 8 below boundary", below_p1_parity)

    def type_at_next_block_top(o):
        # terminator at a block top; next block's top = j+8
        sign, th, fire, pm_up, w, phw, base, arr = o
        j = w + pm_up
        return get(arr, base, j + 8)

    xtab("type at next block top (j+8)", type_at_next_block_top)

    def run_first_p1_off(o):
        sign, th, fire, pm_up, w, phw, base, arr = o
        for i in range(w, w + pm_up):
            if get(arr, base, i) == 1:
                return min(i - w, 9)
        return -1

    xtab("first p1 offset in run", run_first_p1_off)
    xtab("theta", lambda o: o[1])
    xtab("pm_up (7 vs 8)", lambda o: o[3])


if __name__ == "__main__":
    main()
