#!/usr/bin/env python3
"""h663: wide-window near-collision campaign — consolidated census.

Consolidates the three probes run inline after h662z's ladder:
  A. read-HEIGHT ladder (in h662z): bits < w+16 carry ZERO sc
     information (58k pairs at chance; cos calibration 1.0 at
     H=12).
  B. HIGH-field grouping: rows agreeing on all bits >= w+L (low
     free): L=16 gives sc-agreement 0.8251 (2,121 pairs) vs 0.51
     for the complementary cut — the coin is high-state/smooth
     (caveat: such pairs are input-neighbors).
  C. second-level lattice candidates (bit bs+8, bs+16, runs above
     bs): flat everywhere.
  D. THE EXACT LAW found in C's conditioning: critical AND fc=0
     determines the sc class: dn -> cls=0 (never below-cell),
     up -> cls=1 (ALWAYS up-cell).  Exact on comb9 both sides and
     comb7 dn; comb7 up-crit-fc0 rows are all Z-ambiguous
     (cell-geometry asymmetry of the shifted grids — on record).
Pool: h662z_comb9.pkl + h662n/h662o comb7 assembly.
"""
import pickle
from collections import defaultdict


def load_pool():
    rec = list(pickle.load(open("h662z_comb9.pkl", "rb")))
    n9 = len(rec)
    nrows = pickle.load(open("h662n_rows.pkl", "rb"))
    zmap = pickle.load(open("h662o_rows.pkl", "rb"))
    for o in nrows:
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
    return rec, n9


def run_from(v, p):
    r = 0
    while (v >> (p + r)) & 1:
        r += 1
    return r


def main():
    rec, n9 = load_pool()
    print(f"pool {len(rec)} (comb9 {n9})")

    print("\nB. HIGH-field grouping (agree on all bits >= w+L):")
    print("L grps pairs mixed purity sc-agree cos-agree")
    for L in (8, 12, 16, 20):
        groups = defaultdict(list)
        for sign, th, fc, cls, pm, w, phw, scale, S, B in rec:
            groups[(sign, th, pm, phw, w, S >> (w + L),
                    B >> (w + L))].append((cls, fc))
        multi = {k: v for k, v in groups.items() if len(v) >= 2}
        mixed = mrows = arows = tot = agree = cagree = 0
        for v in multi.values():
            cl = [x[0] for x in v]
            fcs = [x[1] for x in v]
            if len(set(cl)) > 1:
                mixed += 1
                mrows += len(v)
            arows += len(v)
            for i in range(len(v)):
                for j in range(i + 1, len(v)):
                    tot += 1
                    agree += cl[i] == cl[j]
                    cagree += fcs[i] == fcs[j]
        purity = 1 - mrows / arows if arows else 0
        print(L, len(multi), tot, mixed, round(purity, 4),
              round(agree / tot, 4) if tot else 0,
              round(cagree / tot, 4) if tot else 0, flush=True)

    print("\nC/D. second-level candidates + the exact law "
          "[(sign, crit, fc) x candidate]:")
    t = defaultdict(lambda: [0, 0])
    law = defaultdict(lambda: [0, 0])
    for sign, th, fc, cls, pm, w, phw, scale, S, B in rec:
        mag = S - B
        crit = (pm + phw) % 8 == 7 and pm in (7, 8)
        if crit and fc == 0:
            law[(sign, th)][cls] += 1
        bs = w + 8 + ((8 - phw) % 8)
        t[(sign, int(crit), fc, "bs+8",
           (mag >> (bs + 8)) & 1)][cls] += 1
        t[(sign, int(crit), fc, "run bs+1",
           min(run_from(mag, bs + 1), 6))][cls] += 1
    print("exact law census (crit & fc=0):")
    for k in sorted(law, key=str):
        c0, c1 = law[k]
        print(f"  {k}: cls0={c0} cls1={c1}")
    print("candidate flatness (n>=2000 cells):")
    for k in sorted(t, key=str):
        c0, c1 = t[k]
        n = c0 + c1
        if n < 2000:
            continue
        print(f"  {k}: n={n} rate={c1/n:.4f}")


if __name__ == "__main__":
    main()
