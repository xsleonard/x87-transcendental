#!/usr/bin/env python3
# h795: empirical carry threshold T(neg, low3): sf values of CARRY vs
# NEG rows (act0), pool + ck14, split by neg.
import pickle, collections, subprocess
CACHE = pickle.load(open("h787_state.pkl","rb"))
def parse_wv(s):
    sg,e2,hx = s.split(":")
    return (int(sg), int(e2), int(hx,16))
def tcstate(se, sig, insn):
    k = (se,sig,insn)
    if k in CACHE and CACHE[k] is not None: return CACHE[k]
    flag = "--fcos-standalone" if insn=="cos" else "--fsin-standalone"
    p = subprocess.run(["./model_h235","--batch",flag,"--dump-internals"],
                       input="%s %s\n"%(se,sig), capture_output=True, text=True)
    tc = corr = fin = None
    for L in p.stderr.splitlines():
        if L.startswith("DI_TC "): tc = dict(x.split("=",1) for x in L.split()[1:] if "=" in x)
        if L.startswith("DI_CORR"): corr = dict(x.split("=",1) for x in L.split()[1:] if "=" in x)
        if L.startswith("DI_FIN"): fin = dict(x.split("=",1) for x in L.split()[1:] if "=" in x)
    out = None
    if tc and corr and corr.get("via")=="default" and fin is not None:
        left = parse_wv(tc["left"]); right = parse_wv(tc["right"])
        dl = left[1]-right[1]
        payload = int(tc.get("payload","0"))
        if 0 < dl <= 40:
            S = (left[2]<<dl) + ((payload<<(dl-8)) if payload and dl>=8 else 0)
            D = S - right[2]
            sh = D.bit_length()-67
            if sh > 0:
                disc = D & ((1<<sh)-1)
                rl = 0
                for b in range(sh-1,-1,-1):
                    if (disc>>b)&1: rl += 1
                    else: break
                out = dict(sh=sh, disc=disc, run=rl, act=int(tc.get("active","0")),
                    low3=int(tc.get("low3","0")), pay=payload, neg=int(fin.get("neg","0")))
    CACHE[k] = out
    return out
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
recs = []
for (se,sg,insn), ds in POS.items():
    st = tcstate(se,sg,insn)
    if st and st["act"]==0 and len(ds)==1:
        mech = "CARRY" if ((ds.copy().pop()=="up") == (st["neg"]==0)) else "BORROW"
        if mech=="CARRY": recs.append((True, st))
for k in NEGk:
    st = tcstate(*k)
    if st and st["act"]==0: recs.append((False, st))
# ck14 rows
for fn, cls in (("ck14_fixed.txt",True),("ck14_broken.txt",False)):
    for L in open(fn):
        t = L.split()
        st = tcstate(t[3],t[4],t[0])
        if st and st["act"]==0: recs.append((cls, st))
pickle.dump(CACHE, open("h787_state.pkl","wb"))
tab = collections.defaultdict(lambda: ([],[]))
for cls, st in recs:
    sf = (1<<st["sh"]) - st["disc"]
    tab[(st["neg"], st["low3"])][0 if cls else 1].append(sf)
print("per (neg, low3): CARRY sf values | NEG sf values   [T exists iff max(CARRY) < min(NEG)]")
for k in sorted(tab):
    c, n = tab[k]
    c.sort(); n.sort()
    ok = (not c or not n or max(c) < min(n))
    print("  neg=%d low3=%d : C(%2d) %-28s | N(%2d) %-24s %s" % (k[0], k[1], len(c),
        ",".join(map(str,c[:14])), len(n), ",".join(map(str,n[:12])), "OK" if ok else "OVERLAP"))
