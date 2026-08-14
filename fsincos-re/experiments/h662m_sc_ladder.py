#!/usr/bin/env python3
"""h662m: does sincos read the SAME block-start frame, deeper?

h662k closed the cos law: critical <=> pm_up+phw == 7 (mod 8),
pm_up in {7,8}; bs = first block-start >= w+8; up fire <=> bit(bs),
dn fire <=> bit(w+8) & bit(bs).  h660: sc fires are a strict subset
of cos fires, conditional ~3/8 (up) / ~0.43-0.48 (dn) — one more
threshold on the same monotone depth.  Prediction: the sc gate reads
the same frame one block higher (run/bit at bs+8, or a deeper pm_up
band).  Census: (A) fire_sc over the full (pm_up, phw) lattice;
(B) inside cos-critical cells, fire_sc vs bit(bs), bit(bs+8), run1;
(C) inside cos-pure cells (fire_cos = 1), fire_sc vs lattice depth.
comb7 only (the double-captured corpus), OTHER rows excluded.
"""
import os, pickle, sys
from collections import defaultdict
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)

E2M = -66
UNIT = 2**66
CACHE = "h662m_rows.pkl"

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


def load_sc_labels():
    rows, seen = [], set()
    for lineS in open("ties_comb7.txt"):
        f = lineS.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        rows.append(f)
    inputs = sorted(f[0] for f in rows)
    order = {mm: i for i, mm in enumerate(inputs)}
    st = {md: open(f"comb7_sc_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    lab = {}
    for f in rows:
        R, ce, i = int(f[7], 16), int(f[8]), order[f[0]]
        hw, bad = [], False
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[4], 16))
        if bad:
            lab[f[0]] = -1
            continue
        clean = [final_cosine_result(-R, ce, md) for md in ROUNDING_MODES]
        dn = [final_cosine_result(-(R - 1), ce, md) for md in ROUNDING_MODES]
        up = [final_cosine_result(-(R + 1), ce, md) for md in ROUNDING_MODES]
        lab[f[0]] = (0 if hw == clean else 1 if hw == dn
                     else 2 if hw == up else -1)
    return lab


def stats(args):
    mhex, sign, th, fire_cos, fire_sc = args
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
    return (sign, th, fire_cos, fire_sc, min(pm_up, 24), w,
            (scale + w) % 8, scale, S, B)


def main():
    if os.path.exists(CACHE):
        out = pickle.load(open(CACHE, "rb"))
        print(f"{len(out)} rows from cache", flush=True)
    else:
        sc = load_sc_labels()
        print(f"sc labels: {len(sc)}", flush=True)
        rows = pickle.load(open("h657m_comb7.pkl", "rb"))
        work = []
        nother = 0
        for (mhex, theta, dist, s4, side, L, rdisc, sR, label, M,
             sqlow) in rows:
            b1 = 1 if 3 * rdisc >= (1 << sR) else 0
            b2 = 1 if 3 * rdisc >= (1 << (sR + 1)) else 0
            sign = "dn" if theta > 0 else "up"
            if not in_region(sign, abs(theta), (s4, side), dist, L,
                             b1, b2, M):
                continue
            sl = sc.get(mhex, -1)
            if sl < 0:
                nother += 1
                continue
            fire_cos = int(label == (1 if sign == "dn" else 2))
            fire_sc = int(sl == (1 if sign == "dn" else 2))
            work.append((mhex, sign, abs(theta), fire_cos, fire_sc))
        print(f"region rows: {len(work)} (+{nother} OTHER excluded); "
              f"stats ...", flush=True)
        with Pool(2) as pool:
            out = pool.map(stats, work, chunksize=1000)
        out = [o for o in out if o is not None]
        pickle.dump(out, open(CACHE, "wb"))
        print(f"cached {len(out)}", flush=True)

    # sanity: nesting must hold row-wise
    viol = sum(1 for o in out if o[3] and not o[2])
    print(f"nesting violations (sc-fire without cos-fire): {viol}")

    # (A) fire_sc over the (pm_up, phw) lattice
    print("\n(A) fire_sc by (sign, pm_up, phw)  [cos-critical marked]:")
    t = defaultdict(lambda: [0, 0])
    for sign, th, fc, fs, pm, w, phw, scale, S, B in out:
        t[(sign, pm, phw)][fs] += 1
    for k in sorted(t, key=str):
        c0, c1 = t[k]
        n = c0 + c1
        if n < 50:
            continue
        sign, pm, phw = k
        crit = "  <- cos-crit" if (pm + phw) % 8 == 7 and pm in (7, 8) \
            else ""
        lvl2 = "  <- LEVEL2?" if (pm + phw) % 8 == 7 and pm in (15, 16) \
            else ""
        print(f"  {sign} pm={pm:2d} phw={phw}: n={n:6d} "
              f"rate={c1/n:.4f}{crit}{lvl2}")

    # (B) inside cos-critical cells
    print("\n(B) cos-critical rows: fire_sc by (sign, bit(bs), "
          "bit(bs+8), run1 cap 12):")
    t = defaultdict(lambda: [0, 0])
    for sign, th, fc, fs, pm, w, phw, scale, S, B in out:
        if not ((pm + phw) % 8 == 7 and pm in (7, 8)):
            continue
        mag = S - B
        bs = w + 8 + ((8 - phw) % 8)
        run1 = 0
        while (mag >> (w + 8 + run1)) & 1:
            run1 += 1
        t[(sign, (mag >> bs) & 1, (mag >> (bs + 8)) & 1,
           min(run1, 12))][fs] += 1
    for k in sorted(t, key=str):
        c0, c1 = t[k]
        n = c0 + c1
        if n < 50:
            continue
        print(f"  {k}: n={n:6d} rate={c1/n:.4f}")

    # (C) cos-pure rows (fire_cos=1 by law, non-critical): depth scan
    print("\n(C) non-cos-critical rows: fire_sc by (sign, "
          "(pm_up+phw)%8, pm_up//8):")
    t = defaultdict(lambda: [0, 0])
    for sign, th, fc, fs, pm, w, phw, scale, S, B in out:
        if (pm + phw) % 8 == 7 and pm in (7, 8):
            continue
        t[(sign, (pm + phw) % 8, pm // 8)][fs] += 1
    for k in sorted(t, key=str):
        c0, c1 = t[k]
        n = c0 + c1
        if n < 50:
            continue
        print(f"  {k}: n={n:6d} rate={c1/n:.4f}")


if __name__ == "__main__":
    main()
