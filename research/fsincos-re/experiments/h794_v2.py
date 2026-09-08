#!/usr/bin/env python3
# h794: candidate v2 = carry iff act0 AND shortfall <= low3 — scored on
# the definitive pool (h787_state cache labels) + the 19 ck14 rows.
import pickle, collections, subprocess
CACHE = pickle.load(open("h787_state.pkl","rb"))
POS = {}
for fn in ("h753_allvotes.txt","h759_miner2_votes.txt"):
    for L in open(fn):
        t = L.split()
        if t[5].startswith("hw=C2") or t[6].startswith("mo=C2"): continue
        hv = int(t[5].split("/")[-1],16); mv = int(t[6].split("/")[-1],16)
        POS.setdefault((t[3],t[4],t[1]), set()).add("up" if hv>mv else "dn")
NEG = set()
for fn in ("h745_neg_r70.txt","h745_neg_r70b.txt"):
    for L in open(fn):
        t = L.split()
        NEG.add((t[3],t[4],t[1]))
NEG -= set(POS)
def score(name, pred):
    r = collections.Counter(); vio = []
    for k, st in CACHE.items():
        if st is None or st["act"] != 0: continue
        sf = (1<<st["sh"]) - st["disc"]
        cls = None
        if k in POS:
            ds = POS[k]
            if len(ds)==1:
                mech = "CARRY" if ((ds.copy().pop()=="up") == (st["neg"]==0)) else "BORROW"
                if mech=="CARRY": cls = True
        elif k in NEG: cls = False
        if cls is None: continue
        f = pred(st, sf)
        r[(cls, f)] += 1
        if f != cls: vio.append((k, st, sf))
    tp = r[(True,True)]; fn_ = r[(True,False)]; fp = r[(False,True)]; tn = r[(False,False)]
    print("%s: CARRY %d/%d  NEG %d/%d" % (name, tp, tp+fn_, tn, tn+fp))
    return vio
v = score("v2 sf<=low3", lambda st, sf: sf <= st["low3"])
for k, st, sf in v[:15]:
    print("   VIO %s run=%d low3=%d sh=%d sf=%d neg=%d" % (k, st["run"], st["low3"], st["sh"], sf, st["neg"]))
score("v2b sf<low3", lambda st, sf: sf < st["low3"])
score("v2c sf<=low3 & sh<=8", lambda st, sf: sf <= st["low3"] and st["sh"] <= 8)
score("bit-form (R72)", lambda st, sf: (st["low3"] << st["run"]) > 128)
