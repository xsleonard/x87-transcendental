#!/usr/bin/env python3
"""h652: per-block exhaustive fit, then unify.

Per block (d, s4, side): enumerate
    u = K*floor((a*L*2^64 + P*xd60*2^(e-60) + W)/2^66) + par*(L%2)
with a in 1..8 (L-slope in 2^64 units), P in {1,3}, e in 60..67,
K in {1,2}, par in {0,1}; W fitted exactly (interval).  Boundary-sliver
rows (|3XD - k| < 1e-4) excluded.  Report every passing config per
block with its W interval, so the cross-block pattern can be read off.
"""
import pickle
from collections import defaultdict

NAMES = ["comb4", "comb3", "comb5", "comb6", "comb7", "comb8"]


def ceil_div(a, b):
    return -((-a) // b)


def main():
    cells = defaultdict(list)
    for nm in NAMES:
        for (dist, s4, side, L, xd60, sR, fire, req) in pickle.load(
                open(f"h649_{nm}.pkl", "rb")):
            cells[(dist, s4, side, L)].append((xd60, sR, fire, req))

    frontier = {}
    for k, rows in cells.items():
        if len(rows) < 300:
            continue
        sR = rows[0][1]

        def nearthird(xd):
            v = 3 * xd / 2**60
            return min(abs(v - 1), abs(v - 2)) < 1e-4
        fr = sorted((xd, req) for xd, s, f, req in rows
                    if f and not nearthird(xd))
        cl = sorted((xd, req) for xd, s, f, req in rows
                    if not f and not nearthird(xd))
        fF = []; mx = None
        for xd, req in fr:
            if mx is None or req > mx:
                fF.append((xd, req)); mx = req
        cF = []; mn = None
        for xd, req in reversed(cl):
            if mn is None or req < mn:
                cF.append((xd, req)); mn = req
        frontier[k] = (sR, fF, cF)

    blocks = defaultdict(list)
    for k in frontier:
        d, s4, side, L = k
        blocks[(d, s4, side)].append(k)

    for bk in sorted(blocks):
        d, s4, side = bk
        sR = frontier[blocks[bk][0]][0]
        passing = []
        for a in range(1, 9):
            for P in (1, 3):
                for e in range(60, 68):
                    for K in (1, 2):
                        for par in (0, 1):
                            wlo = None; whi = None
                            ok = True
                            for ck in blocks[bk]:
                                L = ck[3]
                                _, fF, cF = frontier[ck]
                                base = a * L << 64
                                pv = par * (L % 2)
                                for xd, req in fF:
                                    X = base + P * (xd << (e - 60))
                                    g = ceil_div(req - pv, K)
                                    w = (g << 66) - X
                                    wlo = w if wlo is None else max(wlo, w)
                                for xd, req in cF:
                                    X = base + P * (xd << (e - 60))
                                    g = (req - pv) // K
                                    w = ((g + 1) << 66) - X
                                    whi = w if whi is None else min(whi, w)
                                if (wlo is not None and whi is not None
                                        and wlo >= whi):
                                    ok = False
                                    break
                            if not ok:
                                continue
                            if wlo is None and whi is None:
                                continue
                            if wlo is None:
                                wlo = whi - (1 << 62)
                            if whi is None:
                                whi = wlo + (1 << 62)
                            if wlo < whi:
                                passing.append((a, P, e, K, par, wlo, whi))
        print(f"\nblock {bk} sR={sR}: {len(passing)} configs pass")
        # prefer minimal forms: sort by (K, par, P, a, e)
        for a, P, e, K, par, wlo, whi in sorted(passing)[:40]:
            print(f"   a={a} P={P} e={e} K={K} par={par}  "
                  f"W in [{wlo/2**64:+.4f}, {whi/2**64:+.4f}) *2^64")


if __name__ == "__main__":
    main()
