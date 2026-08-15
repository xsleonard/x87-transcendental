#!/usr/bin/env python3
"""h662x: residual sc coin — h662g bit hunt, residualized.

The sc model is stratum base x crit x lud2 (h662t-w); the residual
coin is margin-independent and deterministic.  Hunt it the h662g
way — single-bit tables — but residualized: CMH within cells that
pin (sign, th, dist, low3, ce, crit, phw, pm, fc, bit8, bitbs,
lud2), so every known modulator is controlled.  Candidate bits
(~100): mag rel w -2..+18, Vlow top 12, ldisc bits 2..9 below top,
rdisc top 8, t4 top 8, low 6 bits of sq/f4/neg/pos/m, and the
HARDWARE SIN outputs (sincos sin lane: mantissa low 8 + exponent
low 2, rn mode) — shared-schedule state no instrument has touched.
Fit comb7; any |z| >= 4 hit is blind-scored on comb9.
Caches: h662x_<corpus>.pkl.
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


def bitnames():
    names = []
    for i in range(-2, 19):
        names.append(f"mag[w{i:+d}]")
    for i in range(12):
        names.append(f"Vlow[kf-{i+1}]")
    for i in range(2, 10):
        names.append(f"ldisc[top-{i}]")
    for i in range(8):
        names.append(f"rdisc[top-{i}]")
    for i in range(8):
        names.append(f"t4[top-{i}]")
    for q in ("sq", "f4", "neg", "pos", "m"):
        for i in range(6):
            names.append(f"{q}[{i}]")
    for i in range(8):
        names.append(f"sin_m[{i}]")
    for i in range(2):
        names.append(f"sin_se[{i}]")
    return names


NAMES = bitnames()


def work(args):
    mhex, theta, ce, hw_cos, hw_sc, sin_m, sin_se = args
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
    pm = min(pm, 12)
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
    lt8 = (ldisc << 8) >> lsh if lsh >= 8 else ldisc << (8 - lsh)
    lud2 = lt8 >> 6

    bits = []
    for i in range(-2, 19):
        bits.append((mag >> (w + i)) & 1)
    for i in range(12):
        bits.append((Vlow >> (kf - i - 1)) & 1 if kf > i else 0)
    for i in range(2, 10):
        bits.append((lt8 >> (7 - i)) & 1 if i <= 7 else
                    (ldisc >> (lsh - i - 1)) & 1 if lsh > i else 0)
    for i in range(8):
        bits.append((rdisc >> (rsh - i - 1)) & 1 if rsh > i else 0)
    for i in range(8):
        bits.append((t4 >> (s4 - i - 1)) & 1 if s4 > i else 0)
    for q in (sq[2], f4[2], neg[2], pos[2], m):
        for i in range(6):
            bits.append((q >> i) & 1)
    for i in range(8):
        bits.append((sin_m >> i) & 1)
    for i in range(2):
        bits.append((sin_se >> i) & 1)
    packed = 0
    for i, b in enumerate(bits):
        packed |= b << i
    key = (sign, th, dist, low3, ce, crit, phw, pm, fc, bit8,
           bitbs, lud2)
    return (key, cls, packed)


def load(prefix, scpre, base):
    rows, seen = [], set()
    for lineS in open(f"{base}/ties_{prefix}.txt"):
        f = lineS.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        rows.append(f)
    inputs = sorted(f[0] for f in rows)
    order = {mm: i for i, mm in enumerate(inputs)}
    st = {md: open(f"{base}/{prefix}_{md}_status.txt")
          .read().splitlines() for md in ROUNDING_MODES}
    sc = {md: open(f"{base}/{scpre}_{md}_status.txt")
          .read().splitlines() for md in ROUNDING_MODES}
    jobs = []
    for f in rows:
        theta = int(f[9])
        if theta == 0:
            continue
        i = order[f[0]]
        hw_cos, hw_sc, bad = [], [], False
        sin_m = sin_se = 0
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            u = sc[md][i].split()
            if t[0] != "OK" or u[0] != "OK":
                bad = True
                break
            hw_cos.append(int(t[2], 16))
            hw_sc.append(int(u[4], 16))
            if md == "rn":
                sin_se = int(u[1], 16)
                sin_m = int(u[2], 16)
        if bad:
            continue
        jobs.append((f[0], theta, int(f[8]), hw_cos, hw_sc,
                     sin_m, sin_se))
    return jobs


class BitCount:
    def __init__(self):
        self.planes = []

    def add(self, v):
        for i, p in enumerate(self.planes):
            carry = p & v
            self.planes[i] = p ^ v
            v = carry
            if not v:
                return
        if v:
            self.planes.append(v)

    def col(self, j):
        return sum(((p >> j) & 1) << k
                   for k, p in enumerate(self.planes))


def build(corpus, base):
    cache = f"h662x_{corpus}.pkl"
    if os.path.exists(cache):
        return pickle.load(open(cache, "rb"))
    jobs = load(corpus, f"{corpus}_sc", base)
    print(f"{corpus}: {len(jobs)} labeled; work ...", flush=True)
    with Pool(8) as pool:
        rows = pool.map(work, jobs, chunksize=1000)
    rows = [r for r in rows if r is not None]
    pickle.dump(rows, open(cache, "wb"))
    print(f"{corpus}: cached {len(rows)}", flush=True)
    return rows


def cmh_all(rows):
    cells = {}
    for key, cls, packed in rows:
        c = cells.get(key)
        if c is None:
            c = cells[key] = [BitCount(), BitCount(), 0, 0]
        c[0].add(packed)
        if cls:
            c[1].add(packed)
        c[2] += 1
        c[3] += cls
    zs = {}
    for bi in range(len(NAMES)):
        num = den = 0.0
        for c in cells.values():
            n = c[2]
            m1 = c[3]
            n1 = c[0].col(bi)
            if n1 < 3 or n - n1 < 3 or m1 == 0 or m1 == n:
                continue
            b1 = c[1].col(bi)
            num += b1 - n1 * m1 / n
            den += n1 * (n - n1) * m1 * (n - m1) / (n * n * (n - 1))
        zs[bi] = num / math.sqrt(den) if den > 0 else 0.0
    return zs


def main():
    c7 = build("comb7", "/root/h638_mirror")
    c9 = build("comb9", "/root/h491")

    print("\nCMH on comb7 (residualized cells):", flush=True)
    z7 = cmh_all(c7)
    hits = [(abs(z), bi, z) for bi, z in z7.items() if abs(z) >= 4]
    hits.sort(reverse=True)
    top = sorted(z7.items(), key=lambda kv: -abs(kv[1]))[:15]
    for bi, z in top:
        print(f"  {NAMES[bi]:14s}: z = {z:+7.2f}")

    if not hits:
        print("\nno |z| >= 4 candidates on comb7 — hunt is null at "
              "this feature set")
        return
    print(f"\n{len(hits)} candidates at |z| >= 4; BLIND comb9:",
          flush=True)
    z9 = cmh_all(c9)
    for _, bi, z in hits:
        r = z9[bi]
        ok = "REPLICATED" if abs(r) >= 4 and r * z > 0 else "no"
        print(f"  {NAMES[bi]:14s}: comb7 {z:+7.2f} -> comb9 "
              f"{r:+7.2f}  [{ok}]")


if __name__ == "__main__":
    main()
