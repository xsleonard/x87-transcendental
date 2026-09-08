#!/usr/bin/env python3
# h957: characterize the SNAP class (324 ops whose hw terminal sits
# EXACTLY on the ulp point that the F/D compositions bracket).
# Contrast SNAP vs FIRE vs DECL on the model coordinates + product
# tails; look for an exact relation (does some composition land
# exactly on the grid?).
import pickle, sys
from collections import Counter, defaultdict

table = pickle.load(open("h949_features.pkl", "rb"))
vlab = pickle.load(open("h956b_vlab.pkl", "rb"))

def geo(r):
    d = r["tc_dist"]
    ls, le2, lsig = r["tc_left"]; rs, re2, rsig = r["tc_right"]
    mask = (1 << d) - 1
    rlow = rsig & mask
    grl = (rlow if rlow else (1 << d)) if ls != rs else ((1 << d) - rlow)
    g = 64 if grl > 64 else int(grl)
    s1, e1, m1 = r["tc_mul"]; s2, e2, m2 = r["tc_lf"]
    P = m1 * m2; pe = e1 + e2
    sh = le2 - pe
    ltail = P & ((1 << sh) - 1) if sh > 0 else 0
    lt8 = (ltail >> (sh - 8)) & 0xFF if sh >= 8 else -1
    return dict(cell=(d, r["tc_mul"][1]), g=g, pay=r["tc_payload"],
                low3=r["tc_low3"], ud=r["tc_ud"], rsh=r["tc_rsh"],
                act=r.get("b81_act", -1),
                top8=(r["acc_d60"] >> 52) & 0xFF,
                lt8=lt8, sub=ls != rs, rud=r["tc_rud"],
                u5d=r["tc_u5d"], via=r.get("corr_via", "?"))

cls = defaultdict(list)
for r in table:
    vl = vlab.get((r["insn"], r["op"]))
    cls[vl].append((r, geo(r)))
print({k: len(v) for k, v in cls.items()})

def dist(name, sel):
    print("--- %s ---" % name)
    for lab in ("SNAP", "FIRE", "DECL"):
        c = Counter(sel(g_) for _, g_ in cls[lab])
        tot = sum(c.values())
        top = ", ".join("%s:%.0f%%" % (k, 100 * v / tot)
                        for k, v in c.most_common(8))
        print("  %-5s %s" % (lab, top))

dist("cell", lambda g: g["cell"])
dist("pay", lambda g: g["pay"])
dist("g(clamp16)", lambda g: g["g"] if g["g"] <= 16 else 17)
dist("low3", lambda g: g["low3"])
dist("sum8=top8+low3", lambda g: g["top8"] + g["low3"])
dist("act", lambda g: g["act"])
dist("ud", lambda g: g["ud"])
dist("rsh", lambda g: g["rsh"])
dist("sub", lambda g: g["sub"])
dist("lt8 quartile", lambda g: -1 if g["lt8"] < 0 else g["lt8"] // 64)
dist("via", lambda g: g["via"])

# tuple context of SNAP ops: are they in mixed or pure tuples?
base = defaultdict(Counter)
for lab in ("FIRE", "DECL"):
    for r, g_ in cls[lab]:
        base[(g_["cell"], g_["g"], g_["pay"])][lab] += 1
inmix = inpure = absent = 0
for r, g_ in cls["SNAP"]:
    c = base.get((g_["cell"], g_["g"], g_["pay"]))
    if c is None: absent += 1
    elif len(c) > 1: inmix += 1
    else: inpure += 1
print("SNAP tuple context: mixed=%d pureFD=%d ownTuple=%d"
      % (inmix, inpure, absent))
