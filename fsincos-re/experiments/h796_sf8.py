#!/usr/bin/env python3
# h796: threshold table in sf8 units (top-8-anchored shortfall):
# sf8 = 2^8 - D8, D8 = top 8 bits of the discard extended to 8 bits.
import pickle, collections
CACHE = pickle.load(open("h787_state.pkl","rb"))
POS = {}
for fn in ("h753_allvotes.txt","h759_miner2_votes.txt"):
    for L in open(fn):
        t = L.split()
        if t[5].startswith("hw=C2") or t[6].startswith("mo=C2"): continue
        hv = int(t[5].split("/")[-1],16); mv = int(t[6].split("/")[-1],16)
        POS.setdefault((t[3],t[4],t[1]), set()).add("up" if hv>mv else "dn")
NEGk = set()
for fn in ("h745_neg_r70.txt","h745_neg_r70b.txt"):
    for L in open(fn):
        t = L.split()
        NEGk.add((t[3],t[4],t[1]))
NEGk -= set(POS)
def sf8_of(st):
    sh, disc = st["sh"], st["disc"]
    if sh >= 8: D8 = disc >> (sh-8)
    else: D8 = disc << (8-sh)
    return 256 - D8
recs = []
for (se,sg,insn), ds in POS.items():
    st = CACHE.get((se,sg,insn))
    if st and st["act"]==0 and len(ds)==1:
        mech = "CARRY" if ((ds.copy().pop()=="up") == (st["neg"]==0)) else "BORROW"
        if mech=="CARRY": recs.append((True, st))
for k in NEGk:
    st = CACHE.get(k)
    if st and st["act"]==0: recs.append((False, st))
for fn, cls in (("ck14_fixed.txt",True),("ck14_broken.txt",False)):
    for L in open(fn):
        t = L.split()
        st = CACHE.get((t[3],t[4],t[0]))
        if st and st["act"]==0: recs.append((cls, st))
tab = collections.defaultdict(lambda: ([],[]))
for cls, st in recs:
    tab[(st["neg"], st["low3"])][0 if cls else 1].append(sf8_of(st))
print("sf8 units:  per (neg, low3): CARRY | NEG    [clean iff max(C) < min(N)]")
T = {}
for k in sorted(tab):
    c, n = tab[k]
    c.sort(); n.sort()
    ok = (not c or not n or max(c) < min(n))
    T[k] = (max(c) if c else None, min(n) if n else None)
    print("  neg=%d low3=%d : C(%2d) %-30s | N(%2d) %-26s %s" % (k[0], k[1], len(c),
        ",".join(map(str,c[:15])), len(n), ",".join(map(str,n[:13])), "OK" if ok else "OVERLAP"))
print()
print("threshold bands (maxC, minN):")
for k in sorted(T):
    print("  neg=%d low3=%d : fire iff sf8 <= T, T in [%s, %s)" % (k[0], k[1], T[k][0], T[k][1]))
