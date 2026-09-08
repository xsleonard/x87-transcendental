#!/usr/bin/env python3
"""h623a: THE SCHEDULE-INFORMED PREDECESSOR-RESIDUE TEST.

The experiment models the standalone cosine terminal subtraction
FSUB(A, B), with A = sq*neg and B produced by the other terminal
multiplication. It tests an asymmetric predecessor-state hypothesis:
the unexplained residual reads A's redundant state (the h587d
left-tree elimination ran on corrupted labels and is suspect).

Features per row (winner-tree proxy for the A-multiply):
  (S_A, C_A) = split_words(sq, neg); lsh = width(sq*neg) - 67;
  stA6  = ((S_A + C_A) >> (lsh - 59)) & 63     (A-side SUM6)
  stA12 = ((S_A + C_A) >> (lsh - 65)) & 4095
  ldt8  = ldisc >> (lsh - 8)                   (value control)

Part 1 — miss-row separability (h619c protocol + new vars):
per cell with >= 3 misses, AUC + zero-FP isolation of miss vs
correct rows on stA6 / stA12 / ldt8.
Part 2 — global comparator gain: per-(stratum-side, stA6)
offsets in [-2, 2] on top of the current model's x, fit on
train half, held-out gain vs current.
Rows: h616 + h619 labeled sets (alias-robust J-intervals).
"""
import bisect
import json
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import E2M
from h453_chain_variants import (C6_1, C6_3, C6_5, C6_2, C6_4,
                                 C6_6, build_chain, mul_round)
from h588_select import split_words
from h598_jframe import jinterval
from h609_ref_predictor import load_model, V5_KEYS

FITS = CBEST = None


def initp():
    global FITS, CBEST
    FITS, CBEST = load_model()


def prep(args):
    m, key_hint, hw = args
    mag = (0, E2M, m)
    sq = mul_round(mag, mag, 67, "chop")
    f4 = mul_round(sq, sq, 67, "chop")
    neg = build_chain(f4, C6_5, C6_3, C6_1, 67, 64, "rn",
                      False, False, False)
    pos = build_chain(f4, C6_6, C6_4, C6_2, 67, 64, "rn",
                      False, False, False)
    B_full = f4[2] * pos[2]
    rsh = B_full.bit_length() - 67
    L_full = sq[2] * neg[2]
    lsh = L_full.bit_length() - 67
    ldisc = L_full & ((1 << lsh) - 1)
    f4_full = sq[2] * sq[2]
    s4 = f4_full.bit_length() - 67
    t4 = f4_full & ((1 << s4) - 1)
    rdisc = B_full & ((1 << rsh) - 1)
    left = mul_round(sq, neg, 67, "chop")
    right = mul_round(f4, pos, 67, "chop")
    low3 = sq[2] & 7
    dist = abs(left[1] - right[1])
    payload = low3 + 8 - dist
    scale = min(left[1], right[1], left[1] - 8)
    A = left[2] << (left[1] - scale)
    P = payload << (left[1] - 8 - scale)
    M = A + P - (right[2] << (right[1] - scale))
    k = M.bit_length() - 67
    ce = scale + k
    bshift = right[1] - scale
    F = rsh - bshift
    kf = k + F
    APf = (A + P) << F
    EU = (APf - B_full) >> kf
    Vlow = (APf - B_full) - (EU << kf)
    ivs = []
    for z in (-2, -1, 0, 1, 2):
        refs = [final_cosine_result(-(EU + z), ce, md)
                for md in ROUNDING_MODES]
        if refs == hw:
            lo, hi = jinterval(Vlow, kf, pos[2], z)
            if lo <= hi:
                ivs.append((lo, hi))
    if not ivs:
        return None
    jlo = min(l for l, h in ivs)
    jhi = max(h for l, h in ivs)
    S, C = split_words(f4[2], pos[2])
    st = ((S + C) >> max(rsh - 59, 0)) & 63
    SA, CA = split_words(sq[2], neg[2])
    sumA = SA + CA
    stA6 = (sumA >> max(lsh - 59, 0)) & 63
    stA12 = (sumA >> max(lsh - 65, 0)) & 4095
    ldt8 = int(ldisc >> max(lsh - 8, 0))
    tau = t4 / (1 << s4)
    mf = (m & ((1 << 63) - 1)) / (1 << 63)
    xd12 = min(11, (rdisc * 12) >> rsh)
    disc = M & ((1 << k) - 1)
    theta = disc if disc <= 2 else disc - (1 << k)
    side = "up" if theta <= 0 else "dn"
    key = (dist, low3, ce, side)
    if key in V5_KEYS:
        zid = (key, xd12, min(15, int(mf * 16)))
    else:
        zid = (key, xd12)
    f = FITS.get(zid)
    if f is None:
        return None
    q, a, b = f
    c = CBEST.get((zid, st), 0)
    x = q * tau + a * mf + b + c
    j0 = round(x)
    lo3, hi3 = jinterval(Vlow, kf, pos[2], 0)
    correct = 0
    for l, h in ivs:
        if l <= j0 <= h:
            correct = 1
    half = (m * 2654435761 >> 16) & 1
    mf16 = min(15, int(mf * 16))
    return (key, xd12, mf16, half, correct, x, jlo, jhi,
            int(stA6), int(stA12), ldt8)


def main():
    rows = []
    locked = json.load(open("h616_locked.json"))
    st6 = {md: open(f"h616_{md}_status.txt").read()
           .splitlines() for md in ROUNDING_MODES}
    for i, rec in enumerate(locked):
        hw = [int(st6[md][i].split()[2], 16)
              for md in ROUNDING_MODES]
        rows.append((int(rec["m"], 16), None, hw))
    recs = json.load(open("h619_rows.json"))
    st9 = {md: open(f"h619_{md}_status.txt").read()
           .splitlines() for md in ROUNDING_MODES}
    for i, rec in enumerate(recs):
        t = [st9[md][i].split() for md in ROUNDING_MODES]
        if any(x[0] != "OK" for x in t):
            continue
        rows.append((int(rec["m"], 16), None,
                     [int(x[2], 16) for x in t]))
    print(f"rows: {len(rows)}", flush=True)
    with Pool(14, initializer=initp) as pool:
        ps = pool.map(prep, rows, chunksize=200)
    ps = [p for p in ps if p is not None]
    print(f"usable: {len(ps)}", flush=True)

    # Part 1: separability
    cells = defaultdict(lambda: ([], []))
    for p in ps:
        (key, xd12, mf16, half, correct, x, jlo, jhi, stA6,
         stA12, ldt8) = p
        cells[(key, xd12, mf16)][correct].append(
            (stA6, stA12, ldt8))
    VN = ("stA6", "stA12", "ldt8")
    sep = defaultdict(lambda: [0, 0])
    auc = defaultdict(list)
    nm = ncell = 0
    for cell, (miss, corr) in cells.items():
        if len(miss) < 3 or len(corr) < 20:
            continue
        ncell += 1
        nm += len(miss)
        for vi, name in enumerate(VN):
            mv = sorted(r[vi] for r in miss)
            cv = sorted(r[vi] for r in corr)
            s = sum(bisect.bisect_left(cv, v) for v in mv)
            a = s / (len(mv) * len(cv))
            auc[name].append(max(a, 1 - a))
            lo_iso = sum(1 for v in mv if v < cv[0])
            hi_iso = sum(1 for v in mv if v > cv[-1])
            sep[name][0] += max(lo_iso, hi_iso)
            sep[name][1] += len(mv)
    print(f"\nPART 1 (cells {ncell}, misses {nm}):")
    for name in VN:
        aa = auc[name]
        print(f"  {name:6s}: mean AUC "
              f"{sum(aa) / max(len(aa), 1):.3f}  zero-FP "
              f"{sep[name][0]}/{sep[name][1]}")

    # Part 2: global A-side comparator gain
    coff = defaultdict(lambda: defaultdict(int))
    for p in ps:
        (key, xd12, mf16, half, correct, x, jlo, jhi, stA6,
         stA12, ldt8) = p
        if half:
            continue
        for cA in range(-2, 3):
            if jlo <= round(x + cA) <= jhi:
                coff[(key, stA6)][cA] += 1
    cbestA = {k: max(v, key=lambda c: (v[c], -abs(c)))
              for k, v in coff.items()}
    ok0 = okA = n = 0
    for p in ps:
        (key, xd12, mf16, half, correct, x, jlo, jhi, stA6,
         stA12, ldt8) = p
        if not half:
            continue
        n += 1
        ok0 += correct
        cA = cbestA.get((key, stA6), 0)
        okA += jlo <= round(x + cA) <= jhi
    print(f"\nPART 2 held-out (n={n}): current "
          f"{ok0 / max(n, 1):.4f}  +A-comparator "
          f"{okA / max(n, 1):.4f}")


if __name__ == "__main__":
    main()
