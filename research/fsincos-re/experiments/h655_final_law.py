#!/usr/bin/env python3
"""h655: the closed-form u-table — final assembly and full verification.

    M = low3*sqlow - (sqlow^2 mod 2^s4)
    tt = [3*rdisc >= 2^sR] + 2^(sR-63) * [3*rdisc >= 2^(sR+1)]
    u  = K*floor((a*L + tt + p*(L%2) + W)/4) + par*(L%2)
    fire <=> M < u * 2^66

    (K,par) = (1,0) s4=66 / (2,1) s4=67
    a per quadrant (66hi:2, 66lo:4, 67hi:1, 67lo:4)
    p per quadrant, W per (quadrant, dist) — this script pins (p, W),
    tests the W dist-ladder, then verifies the whole law on every
    theta=0 row of all six corpora.
"""
import pickle
from collections import defaultdict

NAMES = ["comb4", "comb3", "comb5", "comb6", "comb7", "comb8"]
T60 = 1 << 60
A = {(66, 1): 2, (66, 0): 4, (67, 1): 1, (67, 0): 4}


def ceil_div(a, b):
    return -((-a) // b)


def main():
    cells = defaultdict(list)
    for nm in NAMES:
        for (dist, s4, side, L, xd60, sR, fire, req) in pickle.load(
                open(f"h649_{nm}.pkl", "rb")):
            cells[(dist, s4, side, L)].append((xd60, sR, fire, req))

    # frontiers per (cell, tt) — tt computed with sR-dependent weight
    cons = defaultdict(lambda: [None, None])
    srmap = {}
    for k, rows in cells.items():
        if len(rows) < 300:
            continue
        sR = rows[0][1]
        srmap[k[:3]] = sR
        w2 = 2 if sR == 64 else 1
        agg = defaultdict(lambda: defaultdict(int))
        for xd, _, fire, req in rows:
            v3 = 3 * xd
            if xd == 0 or min(abs(v3 - T60), abs(v3 - 2 * T60)) < (T60 >> 16):
                continue
            tt = (1 if v3 >= T60 else 0) + w2 * (1 if v3 >= 2 * T60 else 0)
            agg[tt][("F" if fire else "C", req)] += 1
        for tt, d_ in agg.items():
            ge = le = None
            for (sflag, req), cnt in d_.items():
                if cnt <= 3:        # identified anomalous singletons
                    # only drop if it's an extreme vs the rest
                    others = [r for (s2, r), c2 in d_.items()
                              if s2 == sflag and (r != req or c2 > 3)]
                    if sflag == "F" and others and req > max(others):
                        continue
                    if sflag == "C" and others and req < min(others):
                        continue
                if sflag == "F":
                    ge = req if ge is None else max(ge, req)
                else:
                    le = req if le is None else min(le, req)
            cons[(k, tt)] = [ge, le]

    blocks = defaultdict(list)
    for (k, tt), v in cons.items():
        blocks[k[:3]].append((k[3], tt, v))

    # pin (p, W) per block for the fixed structure
    print("per-block (p, W) fits with fixed a/K/par/tap-weights:")
    fits = defaultdict(dict)
    for bk in sorted(blocks):
        d, s4, side = bk
        a = A[(s4, side)]
        K, par = (1, 0) if s4 == 66 else (2, 1)
        opts = []
        for p in range(-4, 5):
            wlo = whi = None
            ok = True
            for L, tt, (ge, le) in blocks[bk]:
                X = a * L + tt + p * (L % 2)
                pv = par * (L % 2)
                if ge is not None:
                    w = ceil_div(ge - pv, K) * 4 - X
                    wlo = w if wlo is None else max(wlo, w)
                if le is not None:
                    w = ((le - pv) // K + 1) * 4 - X
                    whi = w if whi is None else min(whi, w)
                if wlo is not None and whi is not None and wlo >= whi:
                    ok = False
                    break
            if ok and wlo is not None and whi is not None:
                opts.append((p, wlo, whi))
        fits[bk] = opts
        os = " ".join(f"p={p:+d}:W[{lo},{hi})" for p, lo, hi in opts)
        print(f"  {bk} sR={srmap[bk]} a={a}: {os}")

    # ---- full-row verification for a chosen assignment ----
    # (p, W) per quadrant: choose from the fits; W-ladder step per dist
    print("\nfull verification: choose per-quadrant p, per-block W")
    choice = {}
    for bk, opts in fits.items():
        if not opts:
            print(f"  {bk}: NO FIT")
            continue
        # prefer smallest |p|
        p, lo, hi = sorted(opts, key=lambda o: abs(o[0]))[0]
        choice[bk] = (p, lo)
    tot = bad = 0
    badrows = defaultdict(int)
    for k, rows in cells.items():
        bk = k[:3]
        if bk not in choice or len(rows) < 300:
            continue
        d, s4, side = bk
        L = k[3]
        a = A[(s4, side)]
        K, par = (1, 0) if s4 == 66 else (2, 1)
        p, W = choice[bk]
        sR = srmap[bk]
        w2 = 2 if sR == 64 else 1
        for xd, _, fire, req in rows:
            v3 = 3 * xd
            tt = (1 if v3 >= T60 else 0) + w2 * (1 if v3 >= 2 * T60 else 0)
            u = K * ((a * L + tt + p * (L % 2) + W) // 4) + par * (L % 2)
            pred_fire_ok = (u >= req) if fire else (u <= req)
            tot += 1
            if not pred_fire_ok:
                bad += 1
                badrows[k] += 1
    print(f"  total rows {tot}, mismatches {bad}")
    for k in sorted(badrows):
        print(f"    {k}: {badrows[k]}")
    print("\nchosen (p, W) per block:")
    for bk in sorted(choice):
        print(f"  {bk}: p={choice[bk][0]:+d} W={choice[bk][1]}")


if __name__ == "__main__":
    main()
