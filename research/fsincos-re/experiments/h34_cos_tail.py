#!/usr/bin/env python3
"""Cos-assembly tail variants vs FSINCOS-cos in the poly region."""
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
C6=[163,164,165,166,167,168]
inputs=[l for l in open(f"{SCR}/dense_qn.txt").read().split("\n") if l.strip()]
sc=[l.split() for l in open(f"{SCR}/dense_rn.txt") if l.strip()]
fc=[l.split() for l in open(f"{SCR}/dense_fcos.txt") if l.strip()]
SUB=[i for i,l in enumerate(inputs)
     if 0.125<= int(l[5:21],16)*2.0**(((int(l[:4],16))&0x7FFF)-16383-63) <0.25]
def variants(i):
    l=inputs[i]
    se,sig=int(l[:4],16),int(l[5:21],16)
    r=(0,sig,((se&0x7FFF)-16383)-63)
    rsq=fmul(r,r)
    q=C68(C6[5])
    for row in (C6[4],C6[3],C6[2],C6[1],C6[0]): q=fadd(fmul(q,rsq),C68(row))
    out={}
    out["A: t=RN64(q*rsq); 1+t"]=fadd(ONE,fmul(q,rsq))
    out["C1: RN64(1+exact(q*rsq))"]=fadd(ONE,fmul(q,rsq,200),200)
    # C4: q chain at 68, t at 68, final 64
    q2=C68(C6[5])
    for row in (C6[4],C6[3],C6[2],C6[1],C6[0]): q2=fadd(fmul(q2,rsq,68),C68(row),68)
    out["C4: horner@68"]=fadd(ONE,fmul(q2,rsq,68),200)
    # C6h: Horner ending at c2 in halves: t=(q*rsq); u=1+t via... same as A
    # C5: split even: q_even = c2 + rsq^2*(c6 + ...) hmm skip
    # C7: coeffs pre-rounded RN64
    def C64(row):
        v=C68(row); return rnP(v[0],v[1],v[2],64)
    q3=C64(C6[5])
    for row in (C6[4],C6[3],C6[2],C6[1],C6[0]): q3=fadd(fmul(q3,rsq),C64(row))
    out["C7: coeffs@RN64"]=fadd(ONE,fmul(q3,rsq))
    # C8: Horner in rsq but with the c2 term REPLACED by split: acc to c4,
    # t_hi = -rsq/2 (exact mul by 0.5), then 1 + t_hi + (c2+0.5)*rsq + rsq^2*q...
    half=(1,1,-1)     # -0.5
    thi=fmul(rsq,half)          # exact
    c2p=fadd(C68(C6[0]),(0,1,-1),200)   # c2 + 0.5 (tiny)
    q4=C68(C6[5])
    for row in (C6[4],C6[3],C6[2],C6[1]): q4=fadd(fmul(q4,rsq),C68(row))
    lo=fadd(fmul(fmul(q4,rsq),rsq),fmul(c2p,rsq))
    u=fadd(ONE,thi)             # 1 - rsq/2 rounded
    out["C8: (1-rsq/2)+(rest)"]=fadd(u,lo)
    return out
score={}
n=0
for i in SUB:
    n+=1
    out=variants(i)
    hc=(int(sc[i][1+2],16),int(sc[i][2+2],16))
    gc=(int(fc[i][1],16),int(fc[i][2],16))
    for k,v in out.items():
        e=enc64(v)
        score[(k,"SINCOS")]=score.get((k,"SINCOS"),0)+(e!=hc)
        score[(k,"FCOS")]=score.get((k,"FCOS"),0)+(e!=gc)
for k in sorted(score):
    print(f"{k[0]:28s} vs {k[1]:6s}: {score[k]:5d}/{n} = {100.0*score[k]/n:.3f}%")
