#!/usr/bin/env python3
"""h650: extended u-table extraction + joint (base, jump) model search.

From the h649 caches, per cell (dist, s4, side, low3): extract exactly
  u0        — lattice threshold as XD -> 0 (pin or bound)
  jumps     — [(pos_in_3XD (validated k/1 on the thirds lattice), du)]
using fine bins (1/48) + exact bracketing.  Print the extended table in
several frames (XD-relative, absolute via sR, binade units).

Then search joint models:  u(cell, XD) = K*floor((A*L + B*d + C*sd +
D*(3XD) + E)/Q) + R*(L%2)  — a model must match u0 AND every jump
position/height, and respect bounds, across ALL cells of its scope.
"""
import pickle, sys
from collections import defaultdict
from itertools import product

NAMES = ["comb4", "comb3", "comb5", "comb6", "comb7", "comb8"]
NB = 48


def bin_pin(rows):
    ge = None; le = None
    for xd, fire, req in rows:
        if fire:
            ge = req if ge is None else max(ge, req)
        else:
            le = req if le is None else min(le, req)
    return ge, le


def main():
    cells = defaultdict(list)
    for nm in NAMES:
        for (dist, s4, side, L, xd60, sR, fire, req) in pickle.load(
                open(f"h649_{nm}.pkl", "rb")):
            cells[(dist, s4, side, L)].append((xd60, sR, fire, req))

    table = {}
    print("EXTENDED TABLE  (u in 2^66 units; jump pos in 3*XD; "
          "pos_abs = pos * 2^(sR-63))")
    print(f"{'cell':>22} {'sR':>3} {'u0':>6} {'jumps':>30}")
    for key in sorted(cells):
        rows = cells[key]
        if len(rows) < 300:
            continue
        d, s4, side, L = key
        sR = rows[0][1]
        bins = defaultdict(list)
        for xd, _, fire, req in rows:
            bins[min(NB - 1, (xd * NB) >> 60)].append((xd, fire, req))
        prof = [bin_pin(bins.get(i, [])) for i in range(NB)]
        # u0: from the lowest informative bins
        u0 = None; u0b = None
        for i in range(NB):
            ge, le = prof[i]
            if ge is not None and le is not None and ge == le:
                u0 = ge
                break
            if ge is not None or le is not None:
                u0b = ("ge", ge) if ge is not None else ("le", le)
                break
        # jumps: transitions between successive pinned values
        jumps = []
        pinned = [(i, prof[i][0]) for i in range(NB)
                  if prof[i][0] is not None and prof[i][0] == prof[i][1]]
        # also treat one-sided runs adjacent to pins as jump evidence
        for j in range(len(pinned) - 1):
            i1, u1 = pinned[j]
            i2, u2 = pinned[j + 1]
            if u1 == u2:
                continue
            seg = [r for i in range(i1, i2 + 1) for r in bins.get(i, [])]
            lmax = None; rmin = None
            for xd, fire, req in seg:
                v1 = (fire and req > u1) or ((not fire) and req < u1)
                v2 = (fire and req > u2) or ((not fire) and req < u2)
                if v1 and not v2:
                    rmin = xd if rmin is None else min(rmin, xd)
                if v2 and not v1:
                    lmax = xd if lmax is None else max(lmax, xd)
            pos = None
            if lmax is not None and rmin is not None:
                lo3, hi3 = 3 * lmax / 2**60, 3 * rmin / 2**60
                # snap to thirds lattice k (integer in 3XD units)
                k = round((lo3 + hi3) / 2)
                pos = k if abs(lo3 - k) < 0.01 and abs(hi3 - k) < 0.01 \
                    else (lo3 + hi3) / 2
            jumps.append((pos, u2 - u1))
        # bound-to-pin transitions (jump position for cells whose left part
        # is only bounded): detect first pinned value differing from a
        # preceding one-sided bound run
        table[key] = (sR, u0 if u0 is not None else u0b, jumps)
        js = " ".join(f"@{p}+{du}" if isinstance(p, int)
                      else f"@{p if p is None else round(p,4)}+{du}"
                      for p, du in jumps)
        posabs = " ".join(
            f"[abs {p * 2**(sR-63)}]" for p, du in jumps
            if isinstance(p, int))
        u0s = u0 if u0 is not None else (f"{u0b[0]}{u0b[1]}" if u0b else "?")
        print(f"{str(key):>22} {sR:>3} {str(u0s):>6} {js:>30} {posabs}")

    pickle.dump(table, open("h650_table.pkl", "wb"))

    # ---------- joint model search ----------
    # constraints per cell from full row data, evaluated on the fly
    print("\nJOINT SEARCH: u = K*floor((A*L + B*d + C*sd + D*(3XD) + E)/Q)"
          " + R*(L%2)")
    scopes = {
        "s4=66": lambda k: k[1] == 66,
        "s4=67": lambda k: k[1] == 67,
        "GLOBAL": lambda k: True,
    }
    # Pareto constraint frontiers per cell (u monotone nondecreasing in XD):
    #   fire rows bind as (small xd, large req):  need u(xd) >= req
    #   clean rows bind as (large xd, small req): need u(xd) <= req
    frontiers = {}
    for k, rows in cells.items():
        if len(rows) < 300:
            continue
        fr = sorted((xd, req) for xd, _, f, req in rows if f)
        cl = sorted((xd, req) for xd, _, f, req in rows if not f)
        fF = []
        mx = None
        for xd, req in fr:
            if mx is None or req > mx:
                fF.append((xd, req)); mx = req
        cF = []
        mn = None
        for xd, req in reversed(cl):
            if mn is None or req < mn:
                cF.append((xd, req)); mn = req
        frontiers[k] = (fF, cF)

    for scname, scf in scopes.items():
        items = [(k, frontiers[k]) for k in frontiers if scf(k)]
        conf = []
        for K, Q in product((1, 2), (2, 3, 4, 6)):
            for A in (1, 2, 3):
                for B in (-6, -4, -3, -2, -1, 0):
                    for C in (0, 1, 2, 3, 4, 6):
                        for D in (1, 2, 3):
                            for R in (0, 1):
                                for E in range(-80, 81):
                                    ok = True
                                    for (d, s4, side, L), (fF, cF) in items:
                                        base = (A * L + B * d + C * side
                                                + E) << 60
                                        par = R * (L % 2)
                                        for xd, req in fF:
                                            u = K * ((base + D * 3 * xd)
                                                     // (Q << 60)) + par
                                            if u < req:
                                                ok = False; break
                                        if not ok:
                                            break
                                        for xd, req in cF:
                                            u = K * ((base + D * 3 * xd)
                                                     // (Q << 60)) + par
                                            if u > req:
                                                ok = False; break
                                        if not ok:
                                            break
                                    if ok:
                                        conf.append((K, Q, A, B, C, D, R, E))
        print(f"  scope {scname}: {len(conf)} formulas pass ALL constraints")
        for K, Q, A, B, C, D, R, E in conf[:15]:
            print(f"    u = {K}*floor(({A}L {B:+d}d {C:+d}sd "
                  f"+ {D}*(3XD) {E:+d})/{Q}) {'+ (L%2)' if R else ''}")


if __name__ == "__main__":
    main()
