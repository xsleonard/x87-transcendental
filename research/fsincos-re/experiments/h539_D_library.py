#!/usr/bin/env python3
"""h539: identify the resolver's value-delta D against a structural
candidate library (h538 model-free frame).

fire(row) <=> gap(row) <= D(row),  D = j * Q(m) >> h.
For each (stratum, side-merged) x (Q, j): compute per-row
h_row = log2(j*Q) - log2(gap); then errors(h) for ALL h at once from
the sorted h_row lists (predicted fire <=> h <= h_row).
One D must explain ALL theta strata simultaneously (the 44/18/4.5
decay is P(D >= gap)); strata are (dist, low3, ce) only.

Reports per stratum per candidate: best h, its error count, and the
error at the best SINGLE GLOBAL h for that candidate.
"""
import math
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)

E2M = -66


def qrow(mhex):
    m = int(mhex, 16)
    mag = (0, E2M, m)
    sq = mul_round(mag, mag, 67, "chop")
    f4 = mul_round(sq, sq, 67, "chop")
    neg = build_chain(f4, C6_5, C6_3, C6_1, 67, 64, "rn",
                      False, False, False)
    pos = build_chain(f4, C6_6, C6_4, C6_2, 67, 64, "rn",
                      False, False, False)
    left = mul_round(sq, neg, 67, "chop")
    right = mul_round(f4, pos, 67, "chop")
    low3 = sq[2] & 7
    dist = abs(left[1] - right[1])
    payload = low3 + 8 - dist
    scale = min(left[1], right[1], left[1] - 8)
    A = left[2] << (left[1] - scale)
    P = payload << (left[1] - 8 - scale)
    Bres = right[2] << (right[1] - scale)
    M = A + P - Bres
    k = M.bit_length() - 67
    R = M >> k
    B_full = f4[2] * pos[2]
    rsh = B_full.bit_length() - 67
    f4_full = sq[2] * sq[2]
    s4 = f4_full.bit_length() - 67
    t4 = f4_full & ((1 << s4) - 1)
    rdisc = B_full & ((1 << rsh) - 1)
    return (m, sq[2], f4[2], pos[2], t4, rdisc, A, P, M, k, R,
            B_full, rsh, right[1] - scale, dist, low3)


QNAMES = ["f4", "rf", "sq", "m", "t4", "rdisc", "t4rf", "one"]
JS = [1, 3]


def work(rows):
    # out[(stratum, qname, j, side)] = list of (h_row, isfire)
    out = defaultdict(list)
    for mhex, theta, lab, ce in rows:
        (m, sqv, f4v, rfv, t4, rdisc, A, P, M, k, R, B_full,
         rsh, bshift, dist, low3) = qrow(mhex)
        F = rsh - bshift
        if F < 0:
            continue
        kf = k + F
        APf = (A + P) << F
        EU = (APf - B_full) >> kf
        Vlow = (APf - B_full) - (EU << kf)
        req2 = (R + {"clean": 0, "down": -1, "up": 1}[lab]) - EU
        gap_dn = Vlow + 1
        gap_up = (1 << kf) - Vlow
        if req2 == 1:
            sides = [("u", gap_up, 1)]
        elif req2 == -1:
            sides = [("d", gap_dn, 1)]
        else:
            sides = [("u", gap_up, 0), ("d", gap_dn, 0)]
        qvals = {"f4": f4v, "rf": rfv, "sq": sqv, "m": m,
                 "t4": t4 if t4 else 1, "rdisc": rdisc if rdisc
                 else 1, "t4rf": (t4 * rfv) if t4 else 1, "one": 1}
        strat = (dist, low3, ce)
        for side, gap, isfire in sides:
            lg = math.log2(gap)
            for qn in QNAMES:
                lq = math.log2(qvals[qn])
                for j in JS:
                    h_row = lq + math.log2(j) - lg
                    out[(strat, qn, j, side)].append((h_row, isfire))
    return out


def main():
    rows = []
    seen = set()
    raw = []
    for line in open("ties_comb7.txt"):
        f = line.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        raw.append(f)
    inputs = sorted(f[0] for f in raw)
    order = {m2: i for i, m2 in enumerate(inputs)}
    st = {md: open(f"comb7_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    stride = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    labeled = []
    for j, f in enumerate(raw):
        if j % stride:
            continue
        R, ce, theta = int(f[7], 16), int(f[8]), int(f[9])
        i = order[f[0]]
        hw, bad = [], False
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        if bad:
            continue
        refs = {name: [final_cosine_result(-(R + d), ce, md)
                       for md in ROUNDING_MODES]
                for name, d in (("clean", 0), ("down", -1),
                                ("up", 1))}
        for name in ("clean", "down", "up"):
            if hw == refs[name]:
                labeled.append((f[0], theta, name, ce))
                break
    print(f"labeled {len(labeled)} rows", flush=True)
    chunks = [labeled[i::8] for i in range(8)]
    with Pool(8) as pool:
        parts = pool.map(work, chunks)
    agg = defaultdict(list)
    for part in parts:
        for kk, v in part.items():
            agg[kk].extend(v)
    # for each key: errors(h) over the h grid via sort
    # predicted fire <=> h <= h_row; errors(h) = fires with
    # h_row < h  +  cleans with h_row >= h.
    # sweep candidate thresholds between sorted h_row values.
    results = defaultdict(dict)
    for (strat, qn, j, side), pts in agg.items():
        pts.sort()
        n = len(pts)
        nf = sum(p[1] for p in pts)
        # walking h from -inf (predict all fire; errors = ncln) up:
        # crossing a point with h_row=x flips its prediction to
        # clean: fire point -> +1 error, clean -> -1.
        best = (n + 1, None)
        errs = n - nf          # h = -inf: all predicted fire
        prev = None
        curve = {}
        for x, isf in pts:
            # threshold just above x
            errs += 1 if isf else -1
            curve[x] = errs
            if errs < best[0]:
                best = (errs, x)
        never = errs           # h = +inf: predict none fire = nf
        results[(strat, side)][(qn, j)] = (best[0], best[1], nf,
                                           n - nf, never)
    print(f"\n{'stratum/side':22s} {'cand':>8s} {'best_err':>8s} "
          f"{'@h':>7s} {'nf':>7s} {'nc':>7s} {'nvr':>7s}")
    for key in sorted(results, key=str):
        strat, side = key
        cands = sorted(results[key].items(), key=lambda kv: kv[1][0])
        for (qn, j), (be, bh, nf, nc, never) in cands[:3]:
            tag = f"{strat}/{side}"
            print(f"{tag:22s} {qn+'*'+str(j):>8s} {be:8d} "
                  f"{bh:7.2f} {nf:7d} {nc:7d} {never:7d}")
    # global-h consistency per candidate: sum over strata of the
    # error at one shared h (grid 0.25 steps over [-10, 90])
    print("\nGLOBAL single-h per candidate (all strata+sides):")
    for qn in QNAMES:
        for j in JS:
            pool_pts = []
            for (strat, qn2, j2, side), pts in agg.items():
                if qn2 == qn and j2 == j:
                    pool_pts.extend(pts)
            pool_pts.sort()
            n = len(pool_pts)
            nf = sum(p[1] for p in pool_pts)
            errs = n - nf
            best = (n + 1, None)
            for x, isf in pool_pts:
                errs += 1 if isf else -1
                if errs < best[0]:
                    best = (errs, x)
            print(f"  {qn}*{j}: best {best[0]}/{n} at h={best[1]:.2f}"
                  f" (never-fire {nf})")


if __name__ == "__main__":
    main()
