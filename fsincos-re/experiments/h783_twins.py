#!/usr/bin/env python3
# h783: (a) fire-region membership split BY CORPUS (F-anomaly link?)
# (b) exact deficits d for votes + visible negs; k-scan of extra=k*(sq&w)
# (c) twin microscope: (m,sq&7)-matched vote/neg pairs, full features
import pickle, math, collections
from fractions import Fraction
exec(open("h774_bitscan.py").read().split("vrec = pickle.load")[0])
HALF = Fraction(1,2)
def chain_s(m):
    def trunc(v,b):
        a = abs(v); g = TWO**(texp(a)-b+1)
        f = (a/g).__floor__()*g
        return f if v>0 else -f
    def rnb(v,b):
        a = abs(v); g = TWO**(texp(a)-b+1)
        q = a/g; fl = q.__floor__(); r = q-fl
        if r>HALF or (r==HALF and fl%2==1): fl += 1
        return fl*g if v>0 else -fl*g
    sq = trunc(m*m,67); f4 = trunc(sq*sq,67)
    o = trunc(f4*CV[5],67); o = rnb(CV[3]+o,64)
    o = trunc(f4*o,67); o = rnb(CV[1]+o,64); o = trunc(sq*o,67)
    e = trunc(f4*CV[6],67); e = rnb(CV[4]+e,64)
    e = trunc(f4*e,67); e = rnb(CV[2]+e,64); e = trunc(f4*e,67)
    return o, e
def exact_d(oval, eval_):
    s = oval + eval_
    es = texp(abs(s)); ee = texp(abs(eval_))
    g = TWO**(es-63)
    r = abs(s)/g - (abs(s)/g).__floor__()
    return float((HALF - r) * TWO**(es-63-ee+66))
vrec = pickle.load(open("h761_state.pkl","rb"))
vis = pickle.load(open("h782_vis.pkl","rb"))
# corpus tags for votes
tag = {}
for fn in ("h753_allvotes.txt","h759_miner2_votes.txt"):
    for L in open(fn):
        t = L.split()
        tag.setdefault((t[3],t[4],t[1]), t[0])
V = []
for rr in vrec:
    if rr["cls"]!="POS": continue
    o,e = chain_s(rr["mval"])
    s = sigs(rr["mval"])
    V.append(dict(cls="POS", corpus=tag.get((rr["se"],rr["sig"],rr["insn"]),"??"),
        insn=rr["insn"], se=rr["se"], sig=rr["sig"], m=int(float(rr["mdef"])), de2=rr["de2"],
        d=exact_d(o,e), sq=s["sq"], f4=s["f4"], emag=texp(rr["mval"]), mval=rr["mval"]))
N = []
for fn, corpus, insn in (("h767_ck1_cos.txt","ck1","cos"),("h767_ck1_sin.txt","ck1","sin"),
                         ("h767_rvl_cos.txt","rvl","cos"),("h767_rvl_sin.txt","rvl","sin")):
    for L in open(fn):
        t = L.split()
        mrow = int(t[8])
        if not (0 <= mrow <= 9): continue
        k = (t[0],t[1],insn)
        vv = vis.get(k)
        if not vv: continue
        mag = wv_val(pw(t[4])); ov = wv_val(pw(t[5])); ev = wv_val(pw(t[6]))
        s = sigs(mag)
        N.append(dict(cls="NEG", corpus=corpus, insn=insn, se=t[0], sig=t[1], m=mrow,
            de2=int(t[9]), d=exact_d(ov,ev), sq=s["sq"], f4=s["f4"], emag=texp(mag), vism=",".join(vv)))
print("votes %d visible-negs %d (ck1 %d rvl %d)" % (len(V), len(N),
    sum(1 for x in N if x["corpus"]=="ck1"), sum(1 for x in N if x["corpus"]=="rvl")))
# (a) fire-region: does the neg sit at (m,v) coords where votes exist?
vcells = collections.Counter((x["m"], x["sq"]&7) for x in V)
inreg = [x for x in N if vcells.get((x["m"], x["sq"]&7),0) > 0]
print("in-fire-region negs: %d  by corpus: %s  by insn: %s" % (len(inreg),
    dict(collections.Counter(x["corpus"] for x in inreg)),
    dict(collections.Counter(x["insn"] for x in inreg))))
print("out-of-region negs by corpus:", dict(collections.Counter(x["corpus"] for x in N if vcells.get((x["m"],x["sq"]&7),0)==0)))
# (b) k-scan: extra = k*(sq&mask) in even-lsbs; POS need extra>=d, NEG need extra<d
print()
for mask,label in ((7,"sq&7"),(15,"sq&15"),(63,"sq&63")):
    best = None
    for ki in range(1,129):
        k = ki/16.0
        posmiss = sum(1 for x in V if k*(x["sq"]&mask) < x["d"])
        negfire = sum(1 for x in N if k*(x["sq"]&mask) >= x["d"])
        if best is None or posmiss+negfire < best[0]:
            best = (posmiss+negfire, k, posmiss, negfire)
    print("%s best k=%.3f : POS unmet %d/148, NEG false-fire %d/%d" % (label, best[1], best[2], best[3], len(N)))
# (c) twins
print()
print("TWIN CELLS (m, sq&7) with both classes:  [cls corpus insn se emag de2 sq&63 f4&7 d]")
byc = collections.defaultdict(list)
for x in V + N: byc[(x["m"], x["sq"]&7)].append(x)
for cell in sorted(byc):
    rows = byc[cell]
    if len(set(r["cls"] for r in rows)) < 2: continue
    print(" cell m=%d v=%d:" % cell)
    for r in sorted(rows, key=lambda r: r["cls"]):
        print("   %s %-4s %s %s emag=%-3d de2=%-2d sq63=%-2d f4_7=%d d=%.3f %s" % (
            r["cls"], r["corpus"], r["insn"], r["se"], r["emag"], r["de2"],
            r["sq"]&63, r["f4"]&7, r["d"], r.get("vism","")))
print("DONE")
