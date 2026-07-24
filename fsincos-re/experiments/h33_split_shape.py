#!/usr/bin/env python3
"""Poly-region [2^-3,1/4): test Itanium-small_r-SHAPED evaluation with P5
6-term coefficients, vs plain Horner, against FSINCOS / FSIN / FCOS."""
import random
SCR="/private/tmp/claude-501/-Users-steve-llm-coduo-binary-analysis/7d0d0788-22c7-4b55-8fbf-66cb5d3d5805/scratchpad"
ROM={}
for line in open("/Users/steve/llm/coduo-binary-analysis/fsincos-re/data/pentium-rom/rom-constants.tsv"):
    p=line.rstrip("\n").split("\t")
    if p[0]=="row": continue
    ROM[int(p[0])]=(int(p[1],16),int(p[2]),int(p[4],16))
def rnP(s,sig,E,P=64):
    b=sig.bit_length(); sh=b-P
    if sh<=0: return (s,sig,E)
    top=sig>>sh; rem=sig&((1<<sh)-1); half=1<<(sh-1)
    if rem>half or (rem==half and (top&1)):
        top+=1
        if top>>P: top>>=1; sh+=1
    return (s,top,E+sh)
def fmul(a,b,P=64):
    if a[1]==0 or b[1]==0: return (0,0,0)
    return rnP(a[0]^b[0],a[1]*b[1],a[2]+b[2],P)
def fadd(a,b,P=64):
    if a[1]==0: return b
    if b[1]==0: return a
    E=min(a[2],b[2])
    v=((-1)**a[0])*(a[1]<<(a[2]-E))+((-1)**b[0])*(b[1]<<(b[2]-E))
    if v==0: return (0,0,0)
    return rnP(1 if v<0 else 0,abs(v),E,P)
def enc64(v):
    if v[1]==0: return (0,0)
    v=rnP(v[0],v[1],v[2],64)
    s,sig,E=v
    b=sig.bit_length()
    if b<64: sig<<=(64-b); E-=(64-b)
    return ((s<<15)|(E+63+16383),sig)
def C68(row):
    ef,s,sig=ROM[row]; return (s,sig,(ef-0xFFFD)-68)
ONE=(0,1,0)
S6=[157,158,159,160,161,162]   # c3..c13
C6=[163,164,165,166,167,168]   # c2..c12
inputs=[l for l in open(f"{SCR}/dense_qn.txt").read().split("\n") if l.strip()]
sc=[l.split() for l in open(f"{SCR}/dense_rn.txt") if l.strip()]
fs=[l.split() for l in open(f"{SCR}/dense_fsin.txt") if l.strip()]
fc=[l.split() for l in open(f"{SCR}/dense_fcos.txt") if l.strip()]
SUB=[i for i,l in enumerate(inputs)
     if 0.125<= int(l[5:21],16)*2.0**(((int(l[:4],16))&0x7FFF)-16383-63) <0.25]
print(f"poly-region inputs: {len(SUB)}")
def eval_shapes(i):
    l=inputs[i]
    se,sig=int(l[:4],16),int(l[5:21],16)
    neg=(se>>15)&1
    r=(0,sig,((se&0x7FFF)-16383)-63)
    rsq=fmul(r,r)
    out={}
    # SHAPE A: plain Horner (current model)
    p=C68(S6[5])
    for row in (S6[4],S6[3],S6[2],S6[1],S6[0]): p=fadd(fmul(p,rsq),C68(row))
    sinA=fadd(r,fmul(fmul(p,rsq),r))
    q=C68(C6[5])
    for row in (C6[4],C6[3],C6[2],C6[1],C6[0]): q=fadd(fmul(q,rsq),C68(row))
    cosA=fadd(ONE,fmul(q,rsq))
    out["A"]=(sinA,cosA)
    # SHAPE B: Itanium-small_r split with P5 coeffs
    # sin = r + [r*rsq*(c3+rsq*c5)] + [r^7*(c7+rsq*c9+rsq^2*c11+rsq^3*c13)]
    Z=fmul(rsq,rsq)          # r^4
    Zs=fmul(Z,r); Zs=fmul(Zs,rsq)   # r^7
    pl=C68(S6[5])
    for row in (S6[4],S6[3],S6[2]): pl=fadd(fmul(pl,rsq),C68(row))
    ph=fadd(fmul(rsq,C68(S6[1])),C68(S6[0]))
    ph=fmul(ph,rsq); ph=fmul(r,ph)
    poly=fadd(fmul(Zs,pl,64),(0,0,0))
    poly=fadd(poly,ph)
    sinB=fadd(r,poly)
    Zc=fmul(Z,rsq)           # r^6
    ql=C68(C6[5])
    for row in (C6[4],C6[3],C6[2]): ql=fadd(fmul(ql,rsq),C68(row))
    qh=fadd(fmul(rsq,C68(C6[1])),C68(C6[0]))
    qh=fmul(qh,rsq)
    qoly=fmul(Zc,ql)
    qoly=fadd(qoly,qh)
    cosB=fadd(ONE,qoly)
    out["B"]=(sinB,cosB)
    if neg:
        for k in out:
            s_,c_=out[k]
            if s_[1]: s_=(s_[0]^1,s_[1],s_[2])
            out[k]=(s_,c_)
    return out
score={}
for i in SUB:
    out=eval_shapes(i)
    hs=(int(sc[i][1],16),int(sc[i][2],16)); hc=(int(sc[i][3],16),int(sc[i][4],16))
    gs=(int(fs[i][1],16),int(fs[i][2],16)); gc=(int(fc[i][1],16),int(fc[i][2],16))
    for k,(s_,c_) in out.items():
        es=enc64(s_); ec=enc64(c_)
        score[(k,"sin_vs_SINCOS")]=score.get((k,"sin_vs_SINCOS"),0)+(es!=hs)
        score[(k,"cos_vs_SINCOS")]=score.get((k,"cos_vs_SINCOS"),0)+(ec!=hc)
        score[(k,"sin_vs_FSIN")]=score.get((k,"sin_vs_FSIN"),0)+(es!=gs)
        score[(k,"cos_vs_FCOS")]=score.get((k,"cos_vs_FCOS"),0)+(ec!=gc)
n=len(SUB)
for k in sorted(score):
    print(f"shape {k[0]} {k[1]:14s}: {score[k]:5d}/{n} = {100.0*score[k]/n:.3f}%")
