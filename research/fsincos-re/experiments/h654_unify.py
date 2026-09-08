#!/usr/bin/env python3
"""h654: unify the per-block integer-bits fits.

Hypothesis: (a, G1, G2, p, Q, K, par) constant per (s4, side) group;
only W carries the dist ladder.  Intersect per-block passing sets within
each group; print shared configs with their W(d) ladders; then look for
cross-group structure.
"""
import pickle
from collections import defaultdict

allpass = pickle.load(open("h653_pass.pkl", "rb"))

groups = defaultdict(list)
for bk in allpass:
    d, s4, side = bk
    groups[(s4, side)].append(bk)

for g in sorted(groups):
    bks = sorted(groups[g])
    sets = []
    for bk in bks:
        m = {}
        for (a, G1, G2, p, Q, K, par, wlo, whi) in allpass[bk]:
            m[(a, G1, G2, p, Q, K, par)] = (wlo, whi)
        sets.append(m)
    shared = set(sets[0])
    for m in sets[1:]:
        shared &= set(m)
    print(f"\n===== group s4={g[0]} side={'hi' if g[1] else 'lo'} "
          f"(blocks {[b[0] for b in bks]}): {len(shared)} shared configs")
    rows = []
    for cfg in shared:
        ws = [sets[i][cfg] for i in range(len(bks))]
        # W ladder step between consecutive dists (interval arithmetic)
        steps = []
        for i in range(len(ws) - 1):
            lo = ws[i + 1][0] - (ws[i][1] - 1)
            hi = (ws[i + 1][1] - 1) - ws[i][0]
            steps.append((lo, hi))
        rows.append((cfg, ws, steps))
    rows.sort(key=lambda r: (r[0][4], r[0][0], r[0][1], r[0][2],
                             abs(r[0][3])))
    for cfg, ws, steps in rows[:25]:
        a, G1, G2, p, Q, K, par = cfg
        wss = " ".join(f"d{bks[i][0]}:[{w[0]},{w[1]})"
                       for i, w in enumerate(ws))
        sts = " ".join(f"[{lo},{hi}]" for lo, hi in steps)
        print(f"  a={a} G1={G1} G2={G2} p={p:+d} Q={Q} K={K} par={par}  "
              f"W: {wss}  step:{sts}")
