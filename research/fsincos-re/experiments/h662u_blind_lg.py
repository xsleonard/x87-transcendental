#!/usr/bin/env python3
"""h662u: BLIND replication of the l_g causal screen on comb9.

h662t (comb7, 148,871 class-observable rows, pinned-cell CMH):
l_g (left-product discard guard) z = -3.25; f4_g +1.79; all other
candidates null.  comb9 (fresh corpus, sincos captured today,
never touched by any sc analysis) is the blind set.

LOCKED PREDICTIONS (before scoring):
  P1 (primary):   l_g pooled CMH z <= -2 on comb9 (same direction)
  P2 (secondary): f4_g pooled CMH z >= +2
  P3:             f4_b2, f4_b3, r_g, r_b2, l_b2 all |z| < 2.5

Pipeline identical to h662t: 3-way cos labels (standalone frame),
h658 region gate, Z-set sc class ([z>=1] up / [z<=-1] dn, mixed
dropped), identical pinned-cell key, identical CMH.
"""
import math, os, pickle, sys
from collections import defaultdict
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)

E2M = -66
UNIT = 2**66
PIV = 0.70710678118654752
CACHE = "h662u_comb9.pkl"

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
VNAMES = ("f4_g", "f4_b2", "f4_b3", "r_g", "r_b2", "l_g", "l_b2")


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


def work(args):
    mhex, theta, ce, hw_cos, hw_sc = args
    m = int(mhex, 16)
    mag0 = (0, E2M, m)
    sq = mul_round(mag0, mag0, 67, "chop")
    f4 = mul_round(sq, sq, 67, "chop")
    neg = build_chain(f4, C6_5, C6_3, C6_1, 67, 64, "rn",
                      False, False, False)
    pos = build_chain(f4, C6_6, C6_4, C6_2, 67, 64, "rn",
                      False, False, False)
    left = mul_round(sq, neg, 67, "chop")
    right = mul_round(f4, pos, 67, "chop")
    low3 = sq[2] & 7
    dist = abs(left[1] - right[1])
    f4_full = sq[2] * sq[2]
    s4 = f4_full.bit_length() - 67
    t4 = f4_full & ((1 << s4) - 1)
    sqlow = sq[2] - (1 << 66)
    M = low3 * sqlow - t4
    B_full = f4[2] * pos[2]
    rsh = B_full.bit_length() - 67
    rdisc = B_full & ((1 << rsh) - 1)
    side = 0 if m / 2**64 < PIV else 1
    b1 = 1 if 3 * rdisc >= (1 << rsh) else 0
    b2 = 1 if 3 * rdisc >= (1 << (rsh + 1)) else 0
    sign = "dn" if theta > 0 else "up"
    th = abs(theta)
    if not in_region(sign, th, (s4, side), dist, low3, b1, b2, M):
        return None

    # cos 3-way label (standalone frame)
    L_full = sq[2] * neg[2]
    lsh = L_full.bit_length() - 67
    ldisc = L_full & ((1 << lsh) - 1)
    product = L_full
    shift = max(product.bit_length() - 67, 0)
    discarded = product & ((1 << shift) - 1) if shift > 0 else 0
    ud = (discarded << 3) >> shift if shift > 0 else 0
    u5d = (discarded << 5) >> shift if shift > 0 else 0
    rud = (rdisc << 1) >> rsh if rsh > 0 else 0
    active = 1 if (low3 and (ud or (dist == 7 and u5d))) else 0
    payload = low3 + 8 - dist if active else 0
    if active and dist == 10 and low3 == 6 and rud:
        lane_shift = (left[1] - 8) - right[1]
        lane = (right[2] >> lane_shift) if lane_shift >= 0 \
            else (right[2] << -lane_shift)
        lp8 = lane & 0xFF
        d8 = (lp8 - payload) & 0xFF
        if d8 >= 128:
            d8 -= 256
        if d8 == -2:
            payload = lp8
    if active and dist == 8 and low3 == 7 and ud >= 3:
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
    R = mag >> w
    refs = {z: [final_cosine_result(-(R + z), ce, md)
                for md in ROUNDING_MODES] for z in (-1, 0, 1)}
    if hw_cos == refs[0]:
        fc = 0
    elif hw_cos == refs[-1 if sign == "dn" else 1]:
        fc = 1
    else:
        return None

    Z = []
    for z in range(-4, 6):
        r = refs.get(z) or [final_cosine_result(-(R + z), ce, md)
                            for md in ROUNDING_MODES]
        if hw_sc == r:
            Z.append(z)
    if not Z:
        return None
    if sign == "up":
        cs = set(1 if z >= 1 else 0 for z in Z)
    else:
        cs = set(1 if z <= -1 else 0 for z in Z)
    if len(cs) != 1:
        return None
    cls = cs.pop()

    pmask_all = ~(S ^ B)
    pm = 0
    j = w
    while (pmask_all >> j) & 1:
        pm += 1
        j += 1
    pm = min(pm, 24)
    phw = (scale + w) % 8
    crit = (pm + phw) % 8 == 7 and pm in (7, 8)
    bs = w + 8 + ((8 - phw) % 8)
    bit8 = (mag >> (w + 8)) & 1
    bitbs = (mag >> bs) & 1
    bshift = right[1] - scale
    F = rsh - bshift
    if F < 0:
        return None
    kf = w + F
    APf = S << F
    EU = (APf - B_full) >> kf
    Vlow = (APf - B_full) - (EU << kf)

    f4_g = (t4 >> (s4 - 1)) & 1
    f4_b2 = (t4 >> (s4 - 2)) & 1 if s4 >= 2 else 0
    f4_b3 = (t4 >> (s4 - 3)) & 1 if s4 >= 3 else 0
    r_g = (rdisc >> (rsh - 1)) & 1
    r_b2 = (rdisc >> (rsh - 2)) & 1 if rsh >= 2 else 0
    l_g = (ldisc >> (lsh - 1)) & 1
    l_b2 = (ldisc >> (lsh - 2)) & 1 if lsh >= 2 else 0
    return (sign, th, fc, cls, dist, low3, crit, phw, min(pm, 12),
            bit8, bitbs, (Vlow * 64 >> kf),
            (f4_g, f4_b2, f4_b3, r_g, r_b2, l_g, l_b2))


def load(prefix, scpre):
    rows, seen = [], set()
    for lineS in open(f"ties_{prefix}.txt"):
        f = lineS.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        rows.append(f)
    inputs = sorted(f[0] for f in rows)
    order = {mm: i for i, mm in enumerate(inputs)}
    st = {md: open(f"{prefix}_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    sc = {md: open(f"{scpre}_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    jobs = []
    for f in rows:
        theta = int(f[9])
        if theta == 0:
            continue
        i = order[f[0]]
        hw_cos, hw_sc, bad = [], [], False
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            u = sc[md][i].split()
            if t[0] != "OK" or u[0] != "OK":
                bad = True
                break
            hw_cos.append(int(t[2], 16))
            hw_sc.append(int(u[4], 16))
        if bad:
            continue
        jobs.append((f[0], theta, int(f[8]), hw_cos, hw_sc))
    return jobs


def main():
    if os.path.exists(CACHE):
        rows = pickle.load(open(CACHE, "rb"))
        print(f"{len(rows)} rows from cache", flush=True)
    else:
        jobs = load("comb9", "comb9_sc")
        print(f"{len(jobs)} labeled theta!=0; work ...", flush=True)
        with Pool(8) as pool:
            rows = pool.map(work, jobs, chunksize=1000)
        rows = [r for r in rows if r is not None]
        pickle.dump(rows, open(CACHE, "wb"))
        print(f"cached {len(rows)} class-observable", flush=True)

    print("\nBLIND CMH on comb9 (locked: l_g z<=-2; f4_g z>=+2; "
          "others |z|<2.5):")
    for vi, vn in enumerate(VNAMES):
        cells = defaultdict(lambda: [[0, 0], [0, 0]])
        for (sign, th, fc, cls, dist, low3, crit, phw, pm, bit8,
             bitbs, mb64, vs) in rows:
            key = (sign, th, dist, low3, crit, phw, pm, fc, bit8,
                   bitbs, mb64)
            cells[key][vs[vi]][cls] += 1
        num = den = 0.0
        used = 0
        for tab in cells.values():
            (a0, b0), (a1, b1) = tab
            n0 = a0 + b0
            n1 = a1 + b1
            n = n0 + n1
            if n0 < 3 or n1 < 3:
                continue
            used += 1
            m1 = b0 + b1
            num += b1 - n1 * m1 / n
            den += n1 * n0 * m1 * (n - m1) / (n * n * (n - 1))
        z = num / math.sqrt(den) if den > 0 else 0.0
        print(f"  {vn:6s}: CMH z = {z:+6.2f}  (cells {used})",
              flush=True)


if __name__ == "__main__":
    main()
