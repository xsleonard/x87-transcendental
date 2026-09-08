#!/usr/bin/env python3
"""h662e: theta ladder — where does the block-edge coin's information live?

Every hand-picked statistic is flat at 1/2 (h662c/d).  Change of
method: cache the COMPLETE aligned terminal operands (S, B) per
critical row, then measure within-group fire purity for groups of rows
with IDENTICAL (S,B) content over windows of increasing width around
the chop boundary.

  - groups pure at width W  => the coin is a deterministic function of
    the window; exhaustive function search over that window becomes
    feasible.
  - groups still mixed at the widest window => the coin reads state
    outside the terminal operand values (upstream arrangement /
    another operand) — the h479 constructed-pair instrument takes over,
    with matched pairs already in hand from these groups.

Cache: h662e_rows.pkl = (sign, th, fire, pm_up, w, phw, scale, S, B).
"""
import os, pickle, sys
from collections import defaultdict
from multiprocessing import Pool

sys.path.insert(0, "/Users/steve/llm/x87-transcendental/fsincos-re/experiments")
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)

E2M = -66
UNIT = 2**66
CACHE = "h662e_rows.pkl"

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
    pmask_all = ~(S ^ B)
    pm_up = 0
    j = w
    while (pmask_all >> j) & 1:
        pm_up += 1
        j += 1
    return (sign, th, fire, min(pm_up, 24), w, (scale + w) % 8, scale,
            S, B)


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
    print(f"\ncritical rows: {len(crit)}, fire rate "
          f"{sum(o[2] for o in crit)/len(crit):.4f}", flush=True)

    # purity vs window width: key = (sign, th, pm_up, phw,
    #   S-window bits, B-window bits) around the boundary [w-lo, w+hi)
    print(f"\n{'window':>16} {'grps>=2':>8} {'mixed':>7} {'mixrows':>8} "
          f"{'purity':>8}")
    for lo, hi in ((8, 16), (16, 24), (24, 32), (40, 40), (64, 56),
                   (96, 72), (200, 120)):
        groups = defaultdict(lambda: [0, 0])
        for sign, th, fire, pm_up, w, phw, scale, S, B in crit:
            maskspan = (1 << (lo + hi)) - 1
            sw = (S >> max(0, w - lo)) & maskspan
            bw = (B >> max(0, w - lo)) & maskspan
            groups[(sign, th, pm_up, phw, sw, bw)][fire] += 1
        multi = {k: v for k, v in groups.items() if v[0] + v[1] >= 2}
        mixed = {k: v for k, v in multi.items() if v[0] and v[1]}
        mixrows = sum(v[0] + v[1] for v in mixed.values())
        allrows = sum(v[0] + v[1] for v in multi.values())
        print(f"  [{lo:>3},+{hi:>3}) {len(multi):>8} {len(mixed):>7} "
              f"{mixrows:>8} "
              f"{1 - mixrows/allrows if allrows else 0:>8.4f}", flush=True)

    # the decisive extreme: FULL S and B as the key
    groups = defaultdict(lambda: [0, 0])
    for sign, th, fire, pm_up, w, phw, scale, S, B in crit:
        groups[(sign, S, B, scale)][fire] += 1
    multi = {k: v for k, v in groups.items() if v[0] + v[1] >= 2}
    mixed = {k: v for k, v in multi.items() if v[0] and v[1]}
    print(f"\nFULL-(S,B,scale) key: {len(multi)} groups>=2, "
          f"{len(mixed)} mixed ({sum(v[0]+v[1] for v in mixed.values())} "
          f"rows)")
    if mixed:
        print("  -> the coin reads state OUTSIDE the terminal operand"
              " values (constructed-pair instrument takes over)")
        for k, v in list(mixed.items())[:5]:
            print(f"    example: sign={k[0]} scale={k[3]} counts={v}")
    else:
        print("  -> the coin IS a function of the terminal operands"
              " (window search continues)")


if __name__ == "__main__":
    main()
