#!/usr/bin/env python3
"""h662n: the sc gate in the EU (paired-lane) frame.

h662m: the sc coin is invisible in the standalone terminal frame.
h594/h577 machinery: the paired lane's natural frame is EU-anchored —
B_full (unchopped right product), APf = (A+P) << F, F = rsh - bshift,
kf = k + F, EU = (APf - B_full) >> kf, sc hw = EU + z, z in [-2..3].
The absolute chop position is unchanged (scale + k), so the 8-bit
block lattice carries over; what changes is the operand tail.

Build the full dual-frame cache (mhex kept this time) and census:
  A. exact-z ladder by (sign, th, standalone-crit, fire_cos)
  B. EU-frame lattice: pm_up_sc = propagate run of ~(APf ^ B_full)
     from kf up; cross-tab fire_sc on (pm_up_sc, phase)
  C. h662g move in the EU frame: single mag_sc bits rel kf-4..kf+16
     vs fire_sc, by sign, within cos-fire rows
Cache: h662n_rows.pkl = (mhex, sign, th, fire_cos, fire_sc, z, w,
phw, pm_up, scale, S, B, F, kf, APf, B_full, ce)
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
CACHE = "h662n_rows.pkl"

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
    mhex, sign, th, fire_cos, fire_sc, ce, hw_sc = args
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
    B_full = fourth[2] * pos[2]
    rsh = max(B_full.bit_length() - 67, 0)
    rdisc = B_full & ((1 << rsh) - 1) if rsh > 0 else 0
    rud = (rdisc << 1) >> rsh if rsh > 0 else 0
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

    # EU frame (h577/h594): unchopped right product
    bshift = right[1] - scale
    F = rsh - bshift
    if F < 0:
        return None
    kf = w + F
    APf = S << F
    mag_sc = APf - B_full
    if mag_sc <= 0:
        return None
    EU = mag_sc >> kf
    z = None
    for zc in range(-3, 5):
        refs = [final_cosine_result(-(EU + zc), ce, md)
                for md in ROUNDING_MODES]
        if hw_sc == refs:
            z = zc
            break
    return (mhex, sign, th, fire_cos, fire_sc, z, min(pm_up, 24), w,
            (scale + w) % 8, scale, S, B, F, kf, APf, B_full, ce)


def load_sc():
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
            continue
        clean = [final_cosine_result(-R, ce, md) for md in ROUNDING_MODES]
        dn = [final_cosine_result(-(R - 1), ce, md) for md in ROUNDING_MODES]
        up = [final_cosine_result(-(R + 1), ce, md) for md in ROUNDING_MODES]
        sl = (0 if hw == clean else 1 if hw == dn
              else 2 if hw == up else -1)
        lab[f[0]] = (sl, ce, hw)
    return lab


def main():
    if os.path.exists(CACHE):
        out = pickle.load(open(CACHE, "rb"))
        print(f"{len(out)} rows from cache", flush=True)
    else:
        sc = load_sc()
        print(f"sc labels: {len(sc)}", flush=True)
        rows = pickle.load(open("h657m_comb7.pkl", "rb"))
        work = []
        for (mhex, theta, dist, s4, side, L, rdisc, sR, label, M,
             sqlow) in rows:
            b1 = 1 if 3 * rdisc >= (1 << sR) else 0
            b2 = 1 if 3 * rdisc >= (1 << (sR + 1)) else 0
            sign = "dn" if theta > 0 else "up"
            if not in_region(sign, abs(theta), (s4, side), dist, L,
                             b1, b2, M):
                continue
            got = sc.get(mhex)
            if got is None or got[0] < 0:
                continue
            sl, ce, hw = got
            fire_cos = int(label == (1 if sign == "dn" else 2))
            fire_sc = int(sl == (1 if sign == "dn" else 2))
            work.append((mhex, sign, abs(theta), fire_cos, fire_sc,
                         ce, hw))
        print(f"region rows: {len(work)}; stats ...", flush=True)
        with Pool(8) as pool:
            out = pool.map(stats, work, chunksize=500)
        out = [o for o in out if o is not None]
        pickle.dump(out, open(CACHE, "wb"))
        print(f"cached {len(out)}", flush=True)

    # A. z ladder census
    print("\n(A) z census by (sign, th, crit, fire_cos)  [None=nomatch]:")
    t = defaultdict(lambda: defaultdict(int))
    for o in out:
        (mhex, sign, th, fc, fs, z, pm, w, phw, scale, S, B, F, kf,
         APf, B_full, ce) = o
        crit = (pm + phw) % 8 == 7 and pm in (7, 8)
        t[(sign, th, crit, fc)][z] += 1
    for k in sorted(t, key=str):
        cen = t[k]
        n = sum(cen.values())
        if n < 50:
            continue
        line = "  ".join(f"z={z}:{cen[z]}" for z in
                         sorted(cen, key=lambda x: (x is None, x)))
        print(f"  {k}: n={n}  {line}")

    # B. EU-frame lattice
    print("\n(B) fire_sc by (sign, pm_up_sc, ph_kf)  [n>=50]:")
    t = defaultdict(lambda: [0, 0])
    for o in out:
        (mhex, sign, th, fc, fs, z, pm, w, phw, scale, S, B, F, kf,
         APf, B_full, ce) = o
        pmask = ~(APf ^ B_full)
        pmsc = 0
        j = kf
        while (pmask >> j) & 1:
            pmsc += 1
            j += 1
        ph = (scale - F + kf) % 8
        t[(sign, min(pmsc, 24), ph)][fs] += 1
    for k in sorted(t, key=str):
        c0, c1 = t[k]
        n = c0 + c1
        if n < 50:
            continue
        sign, pmsc, ph = k
        mark = "  <- crit?" if (pmsc + ph) % 8 == 7 and pmsc in (7, 8) \
            else ""
        print(f"  {sign} pm_sc={pmsc:2d} ph={ph}: n={n:6d} "
              f"rate={c1/n:.4f}{mark}")

    # C. single mag_sc bits, within cos-fire rows
    print("\n(C) fire_sc by mag_sc bit rel kf (cos-fire rows only):")
    for rel in range(-4, 17):
        t = defaultdict(lambda: [0, 0])
        for o in out:
            (mhex, sign, th, fc, fs, z, pm, w, phw, scale, S, B, F,
             kf, APf, B_full, ce) = o
            if not fc:
                continue
            bit = ((APf - B_full) >> (kf + rel)) & 1
            t[(sign, bit)][fs] += 1
        line = []
        flag = ""
        for k in sorted(t, key=str):
            c0, c1 = t[k]
            n = c0 + c1
            if n < 50:
                continue
            r = c1 / n
            if r <= 0.03 or r >= 0.97:
                flag = " *SPLIT*"
            line.append(f"{k}={r:.3f}(n={n})")
        print(f"  rel={rel:+d}:{flag} " + "  ".join(line), flush=True)


if __name__ == "__main__":
    main()
