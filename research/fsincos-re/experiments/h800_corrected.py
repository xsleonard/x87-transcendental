#!/usr/bin/env python3
# h800: CORRECTED sine-family frontier — the randv1/rv2 i1=0 residual
# rows are FIRES (output-frame sign slip found via ck14 census); they
# were mislabeled as razor NEGATIVES in h782/h783.  Rebuild the joint
# (m, sq&7) with corrected labels and count remaining violations.
import pickle, collections
from fractions import Fraction
exec(open("h774_bitscan.py").read().split("vrec = pickle.load")[0])
vis = pickle.load(open("h782_vis.pkl","rb"))
vrec = pickle.load(open("h761_state.pkl","rb"))
vm = {}
for r in vrec:
    if r["cls"]=="POS":
        vm[(r["se"],r["sig"],r["insn"])] = (r["mval"], int(float(r["mdef"])))
# deployment fires (h785 census i1=0 rows, randv1+rv2)
DEP = set()
for L in open("h785.log"):
    if " i1=0 " in L and "mo+1" in L:
        t = L.split()
        DEP.add((t[0],t[1],t[2]))
print("deployment fire keys:", len(DEP))
rows = []
for fn, corpus, insn in (("h767_ck1_cos.txt","ck1","cos"),("h767_ck1_sin.txt","ck1","sin"),
                         ("h767_rvl_cos.txt","rvl","cos"),("h767_rvl_sin.txt","rvl","sin")):
    for L in open(fn):
        t = L.split()
        mrow = int(t[8])
        if not (0 <= mrow <= 9): continue
        k = (t[0],t[1],insn)
        if k in vm: cls = "FIRE-miner"
        elif k in DEP: cls = "FIRE-depl"
        else: cls = "NEG"
        rows.append((cls, corpus, k, mrow, wv_val(pw(t[4]))))
print("razor rows:", collections.Counter(c for c,_,_,_,_ in rows))
# joint with corrected labels (visible rows only on the NEG side)
vj = collections.Counter(); nj = collections.Counter()
viol = []
for cls, corpus, k, m, mag in rows:
    s = sigs(mag); v7 = s["sq"]&7
    if cls.startswith("FIRE"):
        vj[(m, v7)] += 1
    elif vis.get(k):
        nj[(m, v7)] += 1
# miner votes not in razor files (they ARE in ck1 files partly; add pool coords)
for k,(mval,m) in vm.items():
    if not any(kk==k for _,_,kk,_,_ in rows):
        s = sigs(mval); vj[(min(m,9), s["sq"]&7)] += 1
print()
print("CORRECTED joint m x sq&7 (fires | visible true-negs):")
for m in range(10):
    print("  m=%d  " % m + " ".join("%3d/%-3d" % (vj.get((m,v),0), nj.get((m,v),0)) for v in range(8)))
# frontier: fire region = cells with any fire; violations = visible negs in those cells
fcells = set(k for k in vj if vj[k]>0)
inreg = sum(nj[c] for c in fcells if c in nj)
tot = sum(nj.values())
print()
print("visible true-negs: %d total, %d inside fire-region cells" % (tot, inreg))
# k-scan on corrected pools
best = None
POSC = [(m, v) for (m,v),c in vj.items() for _ in range(c)]
NEGC = [(m, v) for (m,v),c in nj.items() for _ in range(c)]
for ki in range(8, 41):
    kk = ki/8.0
    miss = sum(1 for m,v in POSC if kk*v < m)
    fire = sum(1 for m,v in NEGC if kk*v >= m)
    if best is None or miss+fire < best[0]: best = (miss+fire, kk, miss, fire)
print("best k=%.3f : fires unmet %d/%d, negs false %d/%d" % (best[1], best[2], len(POSC), best[3], len(NEGC)))
