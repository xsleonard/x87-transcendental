#!/usr/bin/env python3
"""h662y: sc-class window purity — the h662e test for the sc coin.

h662x: residualized single-bit hunt over 105 features (incl. the
hardware sin lane) is NULL.  Run the instrument that justified the
cos g-hunt: within-group sc-class purity for rows with IDENTICAL
(S, B) content over windows of increasing width around the chop
boundary (+ discrete context).  For cos this gave 71/71 agreement
=> deterministic function of the terminal operands => the bit scan
was guaranteed to terminate.  If sc groups stay MIXED at wide
windows, the sc coin provably reads state OUTSIDE the standalone
terminal frame — closing the value-function question for the
paired lane the way h488 closed it for schedules.
Uses h662n_rows.pkl (mhex, S, B, scale kept) + h662o Z-sets.
"""
import pickle
from collections import defaultdict

NCACHE = "h662n_rows.pkl"
ZCACHE = "h662o_rows.pkl"


def main():
    rows = pickle.load(open(NCACHE, "rb"))
    zmap = pickle.load(open(ZCACHE, "rb"))
    rec = []
    for o in rows:
        (mhex, sign, th, fc, fs, z1, pm, w, phw, scale, S, B, F,
         kf, APf, B_full, ce) = o
        Z = zmap[mhex]
        if sign == "up":
            cs = set(1 if z >= 1 else 0 for z in Z)
        else:
            cs = set(1 if z <= -1 else 0 for z in Z)
        if len(cs) != 1:
            continue
        rec.append((sign, th, fc, cs.pop(), pm, w, phw, scale,
                    S, B))
    print(f"{len(rec)} class-observable rows")

    print(f"\n{'window':>16} {'grps>=2':>8} {'mixed':>7} "
          f"{'mixrows':>8} {'purity':>8}")
    for lo, hi in ((8, 16), (16, 24), (24, 32), (40, 40),
                   (64, 56), (96, 72), (200, 120)):
        groups = defaultdict(lambda: [0, 0])
        for sign, th, fc, cls, pm, w, phw, scale, S, B in rec:
            span = (1 << (lo + hi)) - 1
            sw = (S >> max(0, w - lo)) & span
            bw = (B >> max(0, w - lo)) & span
            groups[(sign, th, fc, pm, phw, sw, bw)][cls] += 1
        multi = {k: v for k, v in groups.items()
                 if v[0] + v[1] >= 2}
        mixed = {k: v for k, v in multi.items() if v[0] and v[1]}
        mixrows = sum(v[0] + v[1] for v in mixed.values())
        allrows = sum(v[0] + v[1] for v in multi.values())
        print(f"  [{lo:>3},+{hi:>3}) {len(multi):>8} "
              f"{len(mixed):>7} {mixrows:>8} "
              f"{1 - mixrows / allrows if allrows else 0:>8.4f}",
              flush=True)

    groups = defaultdict(lambda: [0, 0])
    for sign, th, fc, cls, pm, w, phw, scale, S, B in rec:
        groups[(sign, S, B, scale)][cls] += 1
    multi = {k: v for k, v in groups.items() if v[0] + v[1] >= 2}
    mixed = {k: v for k, v in multi.items() if v[0] and v[1]}
    print(f"\nFULL-(S,B,scale) key: {len(multi)} groups>=2, "
          f"{len(mixed)} mixed "
          f"({sum(v[0]+v[1] for v in mixed.values())} rows)")
    if mixed:
        print("  -> sc coin reads state OUTSIDE the standalone "
              "terminal operands")
    else:
        print("  -> insufficient multiplicity or coin is operand-"
              "determined (see window rows above)")


if __name__ == "__main__":
    main()
