#!/usr/bin/env python3
# h798: bit microscope on the default terminal — CARRY vs BORROW vs NEG
# over every DI_TC field's bits, matched coarse strata (act0 only).
import subprocess, pickle, collections, math, os
def parse_wv(s):
    sg,e2,hx = s.split(":")
    return (int(sg), int(e2), int(hx,16))
CF = "h798_full.pkl"
FC = pickle.load(open(CF,"rb")) if os.path.exists(CF) else {}
def fullstate(se, sig, insn):
    k = (se,sig,insn)
    if k in FC: return FC[k]
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
        try:
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
                        low3=int(tc.get("low3","0")), pay=payload, neg=int(fin.get("neg","0")),
                        L=left[2], R=right[2], mul=parse_wv(tc["mul"])[2] if "mul" in tc else 0,
                        lf=parse_wv(tc["lf"])[2] if "lf" in tc else 0,
                        rf=parse_wv(tc["rf"])[2] if "rf" in tc else 0,
                        f4=parse_wv(tc["f4"])[2] if "f4" in tc else 0,
                        ud=int(tc.get("ud","0")), u5d=int(tc.get("u5d","0")), rud=int(tc.get("rud","0")),
                        dist=int(tc.get("dist","0")), rsh=int(tc.get("rsh","0")))
        except Exception:
            pass
    FC[k] = out
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
for (se,sg,insn), ds in sorted(POS.items()):
    st = fullstate(se,sg,insn)
    if st and st["act"]==0 and len(ds)==1:
        mech = "CARRY" if ((ds.copy().pop()=="up") == (st["neg"]==0)) else "BORROW"
        recs.append((mech, st))
for k in sorted(NEGk):
    st = fullstate(*k)
    if st and st["act"]==0: recs.append(("NEG", st))
for fn, cls in (("ck14_fixed.txt","CARRY"),("ck14_broken.txt","NEG")):
    for L in open(fn):
        t = L.split()
        st = fullstate(t[3],t[4],t[0])
        if st and st["act"]==0: recs.append((cls, st))
pickle.dump(FC, open(CF,"wb"))
print("act0 recs:", collections.Counter(m for m,_ in recs))
# stratify: match on (neg, low3-band, sf8-band); scan bits of fields
def sf8_of(st):
    return 256-(st["disc"]>>(st["sh"]-8)) if st["sh"]>=8 else 256-(st["disc"]<<(8-st["sh"]))
FIELDS = [("L",20),("R",20),("mul",20),("lf",16),("rf",16),("f4",16)]
def strat(st): return (st["neg"], st["low3"]>=4, min(sf8_of(st),8)//3)
groups = collections.defaultdict(lambda: collections.defaultdict(list))
for m, st in recs: groups[strat(st)][m].append(st)
print()
print("=== CARRY vs NEG within strata: max-|z| bits per field (matched) ===")
agg = collections.Counter(); aggn = collections.Counter()
for sk, g in groups.items():
    for f,w in FIELDS:
        for b in range(w):
            for m in ("CARRY","NEG"):
                for st in g[m]:
                    v = (st[f]>>b)&1
                    agg[(sk,f,b,m,v)] += 1
out = []
for f,w in FIELDS:
    for b in range(w):
        num = den = 0.0
        for sk in groups:
            c1 = agg.get((sk,f,b,"CARRY",1),0); c0 = agg.get((sk,f,b,"CARRY",0),0)
            n1 = agg.get((sk,f,b,"NEG",1),0); n0 = agg.get((sk,f,b,"NEG",0),0)
            if c1+c0 < 3 or n1+n0 < 3: continue
            pc = c1/(c1+c0); pn = n1/(n1+n0)
            wgt = 1.0/(1.0/(c1+c0)+1.0/(n1+n0))
            num += wgt*(pc-pn); den += wgt
        if den > 0:
            d = num/den
            se_ = math.sqrt(0.25/den)
            out.append((abs(d/se_), f, b, d))
out.sort(reverse=True)
for z,f,b,d in out[:12]:
    print("  %-4s bit %2d : stratified diff %+.3f  z=%.1f" % (f,b,d,z))
print("DONE")
