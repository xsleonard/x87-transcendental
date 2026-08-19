#!/usr/bin/env python3
# h782: visibility control AT SCALE + per-corpus composition.
# (a) visible-mode-set for EVERY razor row (ck1 + rvl, m 0..9)
# (b) per corpus x insn: P(visible), by mode-class
# (c) votes vs ALL visible negs: sq bit2 / sq&7 at full power
# (d) joint (m, sq&7) frontier votes vs visible negs
import pickle, math, collections, os
from fractions import Fraction
exec(open("h774_bitscan.py").read().split("vrec = pickle.load")[0])
HALF = Fraction(1,2)
def vismodes(mag):
    def trunc(v,b):
        a = abs(v); g = TWO**(texp(a)-b+1)
        f = (a/g).__floor__()*g
        return f if v>0 else -f
    def rnb(v,b):
        a = abs(v); g = TWO**(texp(a)-b+1)
        q = a/g; fl = q.__floor__(); r = q-fl
        if r>HALF or (r==HALF and fl%2==1): fl += 1
        return fl*g if v>0 else -fl*g
    def chain_poly(m):
        sq = trunc(m*m,67)
        f4 = trunc(sq*sq,67)
        o = trunc(f4*CV[5],67); o = rnb(CV[3]+o,64)
        o = trunc(f4*o,67); o = rnb(CV[1]+o,64); o = trunc(sq*o,67)
        e = trunc(f4*CV[6],67); e = rnb(CV[4]+e,64)
        e = trunc(f4*e,67); e = rnb(CV[2]+e,64); e = trunc(f4*e,67)
        return o + e
    s = chain_poly(mag)
    p0 = rnb(s,64)
    g64 = TWO**(texp(abs(p0))-63)
    p1 = (abs(p0)+g64)*(1 if p0>0 else -1)
    out = []
    for p in (p0,p1):
        corr = trunc(mag*p,67)
        v = mag + corr
        a = abs(v); g = TWO**(texp(a)-63)
        q = a/g; fl = q.__floor__(); r = q-fl
        rnq = fl + (1 if (r>HALF or (r==HALF and fl%2==1)) else 0)
        rdq = fl
        ruq = fl + (1 if r>0 else 0)
        out.append((rnq,rdq,ruq,texp(a)))
    a,b = out
    ms = set()
    if (a[0],a[3])!=(b[0],b[3]): ms.add("rn")
    if (a[1],a[3])!=(b[1],b[3]): ms.add("mfl")
    if (a[2],a[3])!=(b[2],b[3]): ms.add("mce")
    return ms
vrec = pickle.load(open("h761_state.pkl","rb"))
vm = {}
for r in vrec:
    if r["cls"]=="POS":
        vm[(r["se"],r["sig"],r["insn"])] = (r["mval"], int(float(r["mdef"])), r["de2"])
NEG = []
for fn, corpus, insn in (("h767_ck1_cos.txt","ck1","cos"),("h767_ck1_sin.txt","ck1","sin"),
                         ("h767_rvl_cos.txt","rvl","cos"),("h767_rvl_sin.txt","rvl","sin")):
    for L in open(fn):
        t = L.split()
        mrow = int(t[8])
        if 0 <= mrow <= 9 and (t[0],t[1],insn) not in vm:
            NEG.append((corpus, insn, mrow, int(t[9]), wv_val(pw(t[4])), t[0], t[1]))
print("negs total:", len(NEG))
CACHE = "h782_vis.pkl"
vis = pickle.load(open(CACHE,"rb")) if os.path.exists(CACHE) else {}
todo = [(c,i,m,d,mag,se,sg) for (c,i,m,d,mag,se,sg) in NEG if (se,sg,i) not in vis]
print("to compute:", len(todo))
for n,(c,i,m,d,mag,se,sg) in enumerate(todo):
    vis[(se,sg,i)] = sorted(vismodes(mag))
    if n % 2000 == 1999:
        pickle.dump(vis, open(CACHE,"wb")); print("  ...", n+1, flush=True)
pickle.dump(vis, open(CACHE,"wb"))
# (b) per corpus x insn
st = collections.defaultdict(lambda: [0,0,collections.Counter()])
for (c,i,m,d,mag,se,sg) in NEG:
    v = vis[(se,sg,i)]
    st[(c,i)][0] += 1
    if v: st[(c,i)][1] += 1
    st[(c,i)][2][tuple(v)] += 1
print()
print("P(visible) per corpus x insn:")
for k in sorted(st):
    n, nv, byms = st[k]
    print("  %s %s : %d rows, visible %d (%.2f%%)  modes: %s" % (k[0],k[1],n,nv,100.0*nv/n,
        " ".join("%s:%d"%("/".join(ms),c) for ms,c in sorted(byms.items()) if ms)))
# visibility by m
bym = collections.defaultdict(lambda: [0,0])
for (c,i,m,d,mag,se,sg) in NEG:
    bym[(c,m)][0] += 1
    if vis[(se,sg,i)]: bym[(c,m)][1] += 1
print()
print("P(visible) by m:  m: ck1 rvl")
for m in range(10):
    a = bym[("ck1",m)]; b = bym[("rvl",m)]
    print("  %d : %5d/%-5d=%.2f%%   %5d/%-5d=%.2f%%" % (m, a[1],a[0],100.0*a[1]/max(a[0],1), b[1],b[0],100.0*b[1]/max(b[0],1)))
# (c) sq contrast: votes vs ALL visible negs
V = [sigs(mv[0]) for mv in vm.values()]
NV = [sigs(mag) for (c,i,m,d,mag,se,sg) in NEG if vis[(se,sg,i)]]
print()
print("votes %d vs visible negs %d" % (len(V), len(NV)))
pv = sum((x["sq"]>>2)&1 for x in V)/len(V); pn = sum((x["sq"]>>2)&1 for x in NV)/len(NV)
se_ = math.sqrt(pn*(1-pn)/len(V)); print("sq bit2: vote %.3f visneg %.3f z=%.1f" % (pv,pn,(pv-pn)/se_))
vh = collections.Counter(x["sq"]&7 for x in V); nh = collections.Counter(x["sq"]&7 for x in NV)
print("sq&7: vote-frac visneg-frac")
for v in range(8):
    print("  %d : %.3f  %.3f" % (v, vh.get(v,0)/len(V), nh.get(v,0)/len(NV)))
# (d) joint (m, sq&7) counts
print()
print("joint m x sq&7 (votes | visible negs):")
vj = collections.Counter(); nj = collections.Counter()
for k,mv in vm.items():
    s = sigs(mv[0]); vj[(mv[1], s["sq"]&7)] += 1
negm = {}
for (c,i,m,d,mag,se,sg) in NEG:
    if vis[(se,sg,i)]: negm[(se,sg,i)] = m
for (c,i,m,d,mag,se,sg) in NEG:
    if vis[(se,sg,i)]:
        s = sigs(mag); nj[(m, s["sq"]&7)] += 1
for m in range(10):
    row = "  m=%d  " % m + " ".join("%3d/%-4d" % (vj.get((m,v),0), nj.get((m,v),0)) for v in range(8))
    print(row)
print("DONE")
