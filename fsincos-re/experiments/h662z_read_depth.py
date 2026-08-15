#!/usr/bin/env python3
"""h662z: the sc coin's read depth — purity vs agreement depth.

h662y: sc class mixed (0.57) where cos was 71/71 pure.  Measure the
read-depth curve: group rows agreeing on ALL (S, B) bits at
positions >= w - c (agreement extending c bits below the chop
boundary; high bits fully matched), sweep c, and record sc-class
purity and pairwise agreement per c.  The cos fire label rides
along as calibration — it must go pure once c covers its window.
Pool: comb7 + comb9 sc-labeled region rows (~505k).
comb9 cache: h662z_comb9.pkl = (sign, th, fc, cls, pm, w, phw,
scale, S, B).
"""
import os, pickle, sys
from collections import defaultdict
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)
from h662v_fold import in_region, load

E2M = -66
PIV = 0.70710678118654752


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
    L_full = sq[2] * neg[2]
    lsh = L_full.bit_length() - 67
    ldisc = L_full & ((1 << lsh) - 1)
    ud = (ldisc << 3) >> lsh if lsh > 0 else 0
    u5d = (ldisc << 5) >> lsh if lsh > 0 else 0
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
    return (sign, th, fc, cls, min(pm, 24), w, (scale + w) % 8,
            scale, S, B)


def build9():
    cache = "h662z_comb9.pkl"
    if os.path.exists(cache):
        return pickle.load(open(cache, "rb"))
    jobs = load("comb9", "comb9_sc", "/root/h491")
    print(f"comb9: {len(jobs)} labeled; work ...", flush=True)
    with Pool(8) as pool:
        rows = pool.map(work, jobs, chunksize=1000)
    rows = [r for r in rows if r is not None]
    pickle.dump(rows, open(cache, "wb"))
    print(f"comb9: cached {len(rows)}", flush=True)
    return rows


def main():
    rec = list(build9())
    n9 = len(rec)
    nrows = pickle.load(open("h662n_rows.pkl", "rb"))
    zmap = pickle.load(open("h662o_rows.pkl", "rb"))
    for o in nrows:
        (mhex, sign, th, fc, fs, z1, pm, w, phw, scale, S, B, F,
         kf, APf, B_full, ce) = o
        Z = zmap[mhex]
        if sign == "up":
            cs = set(1 if z >= 1 else 0 for z in Z)
        else:
            cs = set(1 if z <= -1 else 0 for z in Z)
        if len(cs) != 1:
            continue
        rec.append((sign, th, fc, cs.pop(), pm, w, phw, scale,
                    S, B))
    print(f"pool: {len(rec)} rows (comb9 {n9} + comb7 "
          f"{len(rec) - n9})", flush=True)

    # w is only 8-10: there are almost no bits BELOW the boundary.
    # h662y's mixed groups differed only ABOVE w+16 => the coin
    # reads HIGH.  Ladder climbs upward: match all bits < w+H
    # (everything at and below), free the bits above; purity rises
    # to 1 when H covers the coin's read positions.
    print(f"\nread-HEIGHT ladder (agreement on all bits < w+H):")
    print(f"{'H':>4} {'grps>=2':>8} {'pairs':>7} {'sc-mixed':>9} "
          f"{'sc-purity':>9} {'sc-agree':>9} {'cos-agree':>9}")
    for H in (8, 12, 16, 20, 24, 28, 32, 40, 48):
        groups = defaultdict(list)
        for sign, th, fc, cls, pm, w, phw, scale, S, B in rec:
            mask = (1 << (w + H)) - 1
            groups[(sign, th, pm, phw, w,
                    S & mask, B & mask)].append((cls, fc))
        multi = {k: v for k, v in groups.items() if len(v) >= 2}
        mixed = agree = tot = cagree = ctot = 0
        mrows = arows = 0
        for v in multi.values():
            cl = [x[0] for x in v]
            fcs = [x[1] for x in v]
            if len(set(cl)) > 1:
                mixed += 1
                mrows += len(v)
            arows += len(v)
            for i in range(len(v)):
                for j in range(i + 1, len(v)):
                    tot += 1
                    agree += cl[i] == cl[j]
                    ctot += 1
                    cagree += fcs[i] == fcs[j]
        purity = 1 - mrows / arows if arows else 0
        print(f"{H:>4} {len(multi):>8} {tot:>7} {mixed:>9} "
              f"{purity:>9.4f} "
              f"{agree / tot if tot else 0:>9.4f} "
              f"{cagree / ctot if ctot else 0:>9.4f}", flush=True)


if __name__ == "__main__":
    main()
