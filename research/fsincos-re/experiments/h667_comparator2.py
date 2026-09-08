#!/usr/bin/env python3
"""h667: comparator analysis round 2 — all votes with exact rdisc.

Sources (all rows carry mhex + exact rdisc):
  theta=0: h666_comb3/4/5/6/7 + comb9/11/12 rows from h665/h664 caches
           (comb8 theta0 == comb3, skipped)
  theta!=0: h657m_comb7/8 + comb9/11/12 theta rows

Outputs: stratified brackets, truncated-3x grid, and the per-row
carry-structure autopsy of every sliver row (|ratio - j/3| < 3e-5).
"""
import pickle
import sys
import os
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h665_comparator import (QUAD, TAPS, u_of, in_region, sched_frame,
                             pred_theta, near_j, vote_theta0, vote_thetaN,
                             UNIT)


def collect():
    cache = "h667_votes.pkl"
    if os.path.exists(cache):
        return pickle.load(open(cache, "rb"))
    votes, anom = [], []
    srcs = [(nm, pickle.load(open(f"h666_{nm}.pkl", "rb")))
            for nm in ("comb3", "comb4", "comb5", "comb6", "comb7")]
    srcs += [("comb9", pickle.load(open("h665_comb9.pkl", "rb"))),
             ("comb11", pickle.load(open("h664_comb11.pkl", "rb"))),
             ("comb12", pickle.load(open("h664_comb12.pkl", "rb")))]
    # comb7 theta rows come from h657m (h666_comb7 has them too if the
    # ties file carries theta; guard with per-mhex dedupe)
    srcs += [("comb7m", pickle.load(open("h657m_comb7.pkl", "rb"))),
             ("comb8m", pickle.load(open("h657m_comb8.pkl", "rb")))]
    seen = set()
    for nm, rows in srcs:
        n = 0
        for row in rows:
            mhex, theta, d, s4, side, L, rdisc, sR, label, M, _ = row
            if label == -1:
                continue
            key = (mhex, theta)
            if key in seen:
                continue
            js = near_j(3 * rdisc, 1 << sR)
            if not js:
                continue
            seen.add(key)
            for j in js:
                n += 1
                if theta == 0:
                    if label == 2:
                        continue
                    req = M // UNIT + (1 if label == 1 else 0)
                    vote_theta0(nm, (s4, side), d, L, sR, label == 1,
                                req, j, "rd", rdisc, mhex, votes, anom)
                else:
                    vote_thetaN(nm, row, j, votes, anom)
        print(f"{nm}: {n} near rows", flush=True)
    pickle.dump((votes, anom), open(cache, "wb"))
    return votes, anom


def ratio(v):
    j, num = v[1], v[8]
    return 3 * num / (j * 2 ** v[3]) - 1


def dirclass(th):
    return "t0" if th == 0 else ("dn" if th > 0 else "up")


def main():
    votes, anom = collect()
    print(f"votes {len(votes)} anomalies {len(anom)}")

    for dc in ("t0", "dn", "up"):
        sel = [v for v in votes if dirclass(v[6]) == dc]
        groups = defaultdict(lambda: [None, None, 0, 0])
        for v in sel:
            g = groups[(v[1], v[2], v[3])]
            r = ratio(v)
            if v[9] == 0:
                g[2] += 1
                if g[0] is None or r > g[0]:
                    g[0] = r
            else:
                g[3] += 1
                if g[1] is None or r < g[1]:
                    g[1] = r
        print(f"\n===== {dc} brackets (1e-6 units) =====")
        for key in sorted(groups, key=str):
            j, quad, sR = key
            lo, hi, n0, n1 = groups[key]
            los = f"{lo*1e6:+9.3f}" if lo is not None else "     none"
            his = f"{hi*1e6:+9.3f}" if hi is not None else "     none"
            fl = "  << CONTRA" if (lo is not None and hi is not None
                                   and lo > hi) else ""
            print(f"  j={j} quad={quad} sR={sR}: n0={n0:5d} n1={n1:5d}"
                  f" lo{los} hi{his}{fl}")

    # truncated-3x grid on theta0 votes only, then all
    def pred_trunc(j, sR, rdisc, t, conv):
        mask = (1 << t) - 1 if t > 0 else 0
        comp = 3 * rdisc - ((2 * rdisc) & mask) - (rdisc & mask)
        bound = j << sR
        return (1 if comp >= bound else 0) if conv == "ge" else \
            (1 if comp > bound else 0)

    for dc in ("t0", "all"):
        sel = votes if dc == "all" else \
            [v for v in votes if dirclass(v[6]) == "t0"]
        print(f"\n===== truncated-3x sweep on {dc} "
              f"({len(sel)} votes) =====")
        for conv in ("ge", "gt"):
            for t in range(40, 52):
                viol = [v for v in sel
                        if pred_trunc(v[1], v[3], v[8], t, conv) != v[9]]
                vt = [v for v in viol if dirclass(v[6]) == "t0"]
                print(f"  {conv} t={t}: viol {len(viol)} (t0 {len(vt)})")

    # sliver autopsy: every theta0 vote within 3e-5, with carry info
    print("\n===== theta0 sliver autopsy (|ratio| < 3e-5) =====")
    sel = [v for v in votes
           if dirclass(v[6]) == "t0" and abs(ratio(v)) < 3e-5]
    sel.sort(key=lambda v: (str(v[2]), v[1], ratio(v)))
    for v in sel:
        corpus, j, quad, sR, d, L, th, kind, rdisc, vote, mhex = v
        g = 3 * rdisc - (j << sR)
        print(f"  q={quad} j={j} sR={sR} d={d} L={L} v={vote} "
              f"g={g:+16d} {mhex} {corpus}")

    if anom:
        print(f"\nanomalies ({len(anom)}):")
        for a in anom[:20]:
            print(f"  {a}")


if __name__ == "__main__":
    main()
