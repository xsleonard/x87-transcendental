#!/usr/bin/env python3
# h784: h768 reduction-frame features RE-TESTED on the visible-only
# contrast (148 votes vs 60 visible razor negs) + quadrant split +
# twin-pair N diffs.  h768 was pre-visibility-control; its null is
# suspect because ~99% of its negs could never have fired.
import pickle, math, collections, statistics
M66 = (3<<64) | 0x243F6A8885A308D3
TOPI = (0xA2F9836E4E441529<<64) | 0xFC2757D1F534DDC0
def compat_N(sig, e):
    dividend = sig << (e+2)
    q, rem = divmod(dividend, M66)
    if (rem<<1) > M66: q += 1
    return q
def tz(x): return (x&-x).bit_length()-1 if x else 99
def feats(se, sig):
    ce = int(se,16); e = (ce & 0x7fff) - 16383
    s = int(sig,16)
    N = compat_N(s, e)
    P = s * TOPI
    sh = 191 - e
    qf = P & ((1<<sh)-1)
    dh = abs(qf - (1<<(sh-1)))
    return dict(e=e, sgn=ce>>15, stz=min(tz(s),13),
        N1=N&1, N2=(N>>1)&1, N4=(N>>2)&1, N8=(N>>3)&1, N16=(N>>4)&1, N32=(N>>5)&1,
        Nmod8=N%8, Ntz=min(tz(N),9), Npop=bin(N).count("1")&1,
        qg=(qf>>(sh-1))&1, dhl2=sh-dh.bit_length())
vrec = pickle.load(open("h761_state.pkl","rb"))
vis = pickle.load(open("h782_vis.pkl","rb"))
V = []
for r in vrec:
    if r["cls"]!="POS": continue
    V.append((r["se"], r["sig"], r["insn"], r["i0"], r["rsn"], int(float(r["mdef"]))))
vset = set((a,b,c) for a,b,c,_,_,_ in V)
N_ = []
for fn, corpus, insn in (("h767_ck1_cos.txt","ck1","cos"),("h767_ck1_sin.txt","ck1","sin"),
                         ("h767_rvl_cos.txt","rvl","cos"),("h767_rvl_sin.txt","rvl","sin")):
    for L in open(fn):
        t = L.split()
        m = int(t[8])
        if not (0 <= m <= 9): continue
        if (t[0],t[1],insn) in vset: continue
        if not vis.get((t[0],t[1],insn)): continue
        N_.append((t[0], t[1], insn, int(t[2]), int(t[3]), m, corpus))
print("votes %d visible negs %d" % (len(V), len(N_)))
VF = [feats(se,sg) for se,sg,_,_,_,_ in V]
NF = [feats(se,sg) for se,sg,_,_,_,_,_ in N_]
print()
print("%-6s %9s %9s %6s" % ("feat","VOTE","VISNEG","z"))
for k in ("e","sgn","stz","N1","N2","N4","N8","N16","N32","Ntz","Npop","qg","dhl2"):
    mv = statistics.mean(x[k] for x in VF); mn = statistics.mean(x[k] for x in NF)
    if k in ("e","stz","Ntz","dhl2"):
        sv = statistics.pstdev(x[k] for x in VF); sn = statistics.pstdev(x[k] for x in NF)
        se_ = math.sqrt(sv*sv/len(VF) + sn*sn/len(NF)) or 1e-9
    else:
        p = (mv*len(VF)+mn*len(NF))/(len(VF)+len(NF))
        se_ = math.sqrt(p*(1-p)*(1/len(VF)+1/len(NF))) or 1e-9
    print("%-6s %9.3f %9.3f %6.1f" % (k, mv, mn, (mv-mn)/se_))
print()
print("quadrant (insn, i0, rsn): votes | visible negs")
vq = collections.Counter((c,i,r) for _,_,c,i,r,_ in V)
nq = collections.Counter((c,i,r) for _,_,c,i,r,_,_ in N_)
for k in sorted(set(vq)|set(nq)):
    print("   %s : %3d | %3d" % (k, vq.get(k,0), nq.get(k,0)))
print()
print("Nmod8: votes | visible negs")
vq = collections.Counter(x["Nmod8"] for x in VF); nq = collections.Counter(x["Nmod8"] for x in NF)
for k in range(8):
    print("   %d : %3d | %3d" % (k, vq.get(k,0), nq.get(k,0)))
print()
print("visible negs by (corpus): fire-region rows only vs all")
print(collections.Counter(c for *_,c in N_))
print("DONE")
