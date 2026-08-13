#!/usr/bin/env python3
"""h433: product-level aliasing inversion.

For every informative (non-add-consistent) row, test whether perturbing
the left or right chop67 product by +-1 retained unit — or re-rounding it
(RN67/away67/odd67 recomputed from the exact full product) — with the
standard payload machinery reproduces hardware in all three modes.
"""
from collections import Counter
from multiprocessing import Pool

exec(open("h431_enriched.py").read().split("def build")[0])

def build_inv(args):
    d, hws = args
    p = int(d["payload"])
    le2, re2 = int(d["le2"]), int(d["re2"])
    ls, rs = int(d["ls"], 16), int(d["rs"], 16)
    lsign, rsign = int(d["lsign"]), int(d["rsign"])
    mul, lf = int(d["mul"], 16), int(d["lf"], 16)
    f4, rf = int(d["f4"], 16), int(d["rf"], 16)

    def terminal(lsv, rsv):
        scale = min(le2, re2)
        if p:
            scale = min(scale, le2 - 8)
        acc = (-1 if lsign else 1) * (lsv << (le2 - scale)) \
            + (-1 if rsign else 1) * (rsv << (re2 - scale))
        if p:
            acc += (-1 if lsign else 1) * (p << (le2 - 8 - scale))
        return chop67(acc, scale)

    def ok(lsv, rsv):
        c, e = terminal(lsv, rsv)
        return all(final_cos(c, e, m) == hws[m] for m in MODES)

    if ok(ls, rs):
        return None                      # add-consistent, not informative

    # re-roundings from exact products
    pl, pr = mul * lf, f4 * rf
    shl = max(pl.bit_length() - 67, 0)
    shr = max(pr.bit_length() - 67, 0)
    reml, remr = pl & ((1 << shl) - 1), pr & ((1 << shr) - 1)
    halfl, halfr = 1 << (shl - 1) if shl else 0, 1 << (shr - 1) if shr else 0
    ls_rn = ls + (1 if shl and (reml > halfl or (reml == halfl and ls & 1)) else 0)
    rs_rn = rs + (1 if shr and (remr > halfr or (remr == halfr and rs & 1)) else 0)
    ls_aw = ls + (1 if reml else 0)
    rs_aw = rs + (1 if remr else 0)
    ls_od = ls | (1 if reml else 0)
    rs_od = rs | (1 if remr else 0)

    cands = {
        "L-1": (ls - 1, rs), "L+1": (ls + 1, rs),
        "R-1": (ls, rs - 1), "R+1": (ls, rs + 1),
        "L-1R-1": (ls - 1, rs - 1), "L+1R+1": (ls + 1, rs + 1),
        "L-1R+1": (ls - 1, rs + 1), "L+1R-1": (ls + 1, rs - 1),
        "L_rn": (ls_rn, rs), "R_rn": (ls, rs_rn),
        "L_aw": (ls_aw, rs), "R_aw": (ls, rs_aw),
        "L_od": (ls_od, rs), "R_od": (ls, rs_od),
    }
    good = tuple(sorted(name for name, (a, b) in cands.items() if ok(a, b)))
    return (int(d["dist"]), int(d["low3"]), good)

if __name__ == "__main__":
    with Pool(8) as pool:
        res = pool.map(build_inv, load(), chunksize=2000)
    inv = [r for r in res if r is not None]
    print(f"informative rows: {len(inv)}")
    unexplained = sum(1 for *_, g in inv if not g)
    print(f"rows with NO single-product explanation: {unexplained}")
    cnt = Counter()
    for dist, low3, good in inv:
        cnt[good] += 1
    for g, n in sorted(cnt.items(), key=lambda t: -t[1])[:15]:
        print(f"  n={n}  works: {g}")
