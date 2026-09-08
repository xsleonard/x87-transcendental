#!/usr/bin/env python3
"""h662v: fold the left-tail field into the sc margin; re-derive.

h662t/u: lud2 (top two discarded left-product bits) biases z_sc
upward, monotone, all strata, blind-replicated.  Mechanism model:
the sincos terminal keeps k extra left-tail columns, so its V is
    V_sc = Vlow + ltail_k << (alsb - k + d)
where alsb = left1 - scale + F is the column of A's LSB in APf
units (the tail's natural position), k = kept bits, d = column
offset (h490 suggests k=2, d=0).  Fit: per-stratum threshold on
the corrected margin (fit_thr, split-half held-out) on comb7,
scan (k, d); blind-transfer the winner to comb9 with thresholds
trained on ALL of comb7.  Baseline = k=0 (no fold).

Worker cache per corpus: h662v_<corpus>.pkl =
(sign, th, dist, low3, ce, fc, cls, crit, phw, pm, bit8, bitbs,
 kf, Vlow, alsb, lt8, half)
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
    shift = lsh
    discarded = ldisc
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
    alsb = left[1] - scale + F
    lt8 = (ldisc << 8) >> lsh if lsh >= 8 else ldisc << (8 - lsh)
    half = (m * 2654435761) & 1
    return (sign, th, dist, low3, ce, fc, cls, crit, phw, pm,
            bit8, bitbs, kf, Vlow, alsb, lt8, half)


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


def build(corpus, base):
    cache = f"h662v_{corpus}.pkl"
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


def fit_thr(pts):
    hist = defaultdict(lambda: [0, 0])
    for mb, f in pts:
        hist[mb][f] += 1
    cands = sorted(hist)
    cands.append(cands[-1] + 1)
    best = (-1, 0, 1)
    for t in cands:
        accge = sum((n1 if mb >= t else n0)
                    for mb, (n0, n1) in hist.items())
        acclt = sum((n1 if mb < t else n0)
                    for mb, (n0, n1) in hist.items())
        if accge > best[0]:
            best = (accge, t, 1)
        if acclt > best[0]:
            best = (acclt, t, -1)
    return best[1], best[2]


def margin(r, k, d):
    kf, Vlow, alsb, lt8 = r[12], r[13], r[14], r[15]
    if k == 0:
        V = Vlow
    else:
        col = alsb - k + d
        if col < 0:
            V = Vlow
        else:
            V = Vlow + ((lt8 >> (8 - k)) << col)
    return V * 4096 >> kf


def keyf(r):
    return (r[0], r[1], r[2], r[3], r[4], r[7])


def held_out(rows, k, d):
    tr = defaultdict(list)
    for r in rows:
        if r[16] == 0:
            tr[keyf(r)].append((margin(r, k, d), r[6]))
    ths = {kk: fit_thr(p) for kk, p in tr.items()}
    ok = n = 0
    for r in rows:
        if r[16] != 1:
            continue
        got = ths.get(keyf(r))
        if got is None:
            continue
        t, sgn = got
        mb = margin(r, k, d)
        pred = 1 if (mb >= t if sgn == 1 else mb < t) else 0
        ok += pred == r[6]
        n += 1
    return ok / max(n, 1), n


def main():
    c7 = build("comb7", "/root/h638_mirror")
    c9 = build("comb9", "/root/h491")

    print("\n(k, d) scan on comb7 (held-out threshold acc, "
          "key = stratum+crit):")
    results = []
    for k in (0, 1, 2, 3):
        for d in ((0,) if k == 0 else (-2, -1, 0, 1, 2)):
            acc, n = held_out(c7, k, d)
            results.append((acc, k, d, n))
            print(f"  k={k} d={d:+d}: acc={acc:.4f} (n={n})",
                  flush=True)
    results.sort(reverse=True)
    acc0 = [r for r in results if r[1] == 0][0][0]
    accb, kb, db, _ = results[0]
    print(f"\nbaseline (no fold) {acc0:.4f}; winner k={kb} d={db} "
          f"{accb:.4f} (+{accb-acc0:.4f})")

    # blind transfer: thresholds trained on ALL comb7, tested comb9
    for k, d, tag in ((0, 0, "baseline"), (kb, db, "winner")):
        tr = defaultdict(list)
        for r in c7:
            tr[keyf(r)].append((margin(r, k, d), r[6]))
        ths = {kk: fit_thr(p) for kk, p in tr.items()}
        ok = n = 0
        by = defaultdict(lambda: [0, 0])
        for r in c9:
            got = ths.get(keyf(r))
            if got is None:
                continue
            t, sgn = got
            mb = margin(r, k, d)
            pred = 1 if (mb >= t if sgn == 1 else mb < t) else 0
            good = pred == r[6]
            ok += good
            n += 1
            by[r[0]][good] += 1
        parts = "  ".join(f"{s}:{g[1]/(g[0]+g[1]):.4f}"
                          for s, g in sorted(by.items()))
        print(f"COMB9 BLIND [{tag} k={k} d={d}]: {ok/max(n,1):.4f} "
              f"(n={n})  [{parts}]", flush=True)

    # distribution view: biggest stratum, rate vs corrected margin
    big = defaultdict(int)
    for r in c9:
        big[keyf(r)] += 1
    top = sorted(big, key=big.get, reverse=True)[:3]
    for kk in top:
        print(f"\ncomb9 stratum {kk} (n={big[kk]}): class rate by "
              f"margin bucket, raw vs folded (k={kb},d={db}):")
        t0 = defaultdict(lambda: [0, 0])
        t1 = defaultdict(lambda: [0, 0])
        for r in c9:
            if keyf(r) != kk:
                continue
            t0[margin(r, 0, 0) // 64] [r[6]] += 1
            t1[margin(r, kb, db) // 64][r[6]] += 1
        buckets = sorted(set(t0) | set(t1))
        for b in buckets:
            def s(t):
                c0, c1 = t.get(b, (0, 0))
                n = c0 + c1
                return f"{c1/n:.3f}({n})" if n >= 50 else "-"
            print(f"  bkt {b:3d}: raw {s(t0):>12s}  folded "
                  f"{s(t1):>12s}")


if __name__ == "__main__":
    main()
