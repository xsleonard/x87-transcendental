#!/usr/bin/env python3
# h756: beam round 2 — pairs/triples of the zero-collateral leaders.
import pickle, itertools
from fractions import Fraction
exec(open("h755_peredge.py").read().split("CACHE =")[0])
ROWS = pickle.load(open("h755_rows.pkl", "rb"))
npos = sum(1 for r in ROWS if r[0]=="POS")
def score(cfg):
    okp = bad = 0
    for cls, mag, pd, lsb in ROWS:
        pl = chain(mag, cfg)
        if cls == "POS":
            if abs(pl) == abs(pd) + lsb: okp += 1
        else:
            if abs(pl) != abs(pd): bad += 1
    return okp, bad
LEADS = [ (1,65,"chop"), (10,66,"odd"), (10,66,"jam"), (10,66,"away"),
          (1,65,"odd"), (1,65,"jam"), (1,64,"rn"), (1,66,"chop"),
          (11,65,"rn"), (11,66,"chop"), (6,67,"odd"), (6,67,"jam"),
          (6,67,"rn"), (6,67,"away"), (12,65,"rn"), (12,64,"away") ]
best = []
for combo in itertools.combinations(LEADS, 2):
    stages = [c[0] for c in combo]
    if len(set(stages)) != len(stages): continue
    cfg = list(SHIP)
    for si, w, md in combo:
        cfg[si] = (SHIP[si][0], w, md)
    okp, bad = score(cfg)
    best.append((okp, bad, combo))
for combo in itertools.combinations(LEADS, 3):
    stages = [c[0] for c in combo]
    if len(set(stages)) != len(stages): continue
    cfg = list(SHIP)
    for si, w, md in combo:
        cfg[si] = (SHIP[si][0], w, md)
    okp, bad = score(cfg)
    best.append((okp, bad, combo))
best.sort(key=lambda x: (x[1] != 0, -x[0], x[1]))
print("beam-2 top:")
for okp, bad, combo in best[:14]:
    print("  pos %3d/%d broken %2d : %s" % (okp, npos, bad, combo))
