#!/usr/bin/env python3
"""Solve Skylake's actual table entries per cell: regress hw-vs-model
difference against the (C4(a), S4(a)) basis, cell by cell."""
import math
from collections import defaultdict
SCR="/private/tmp/claude-501/-Users-steve-llm-coduo-binary-analysis/7d0d0788-22c7-4b55-8fbf-66cb5d3d5805/scratchpad"
ROM={}
for line in open("/Users/steve/llm/coduo-binary-analysis/fsincos-re/data/pentium-rom/rom-constants.tsv"):
    p=line.rstrip("\n").split("\t")
    if p[0]=="row": continue
    ROM[int(p[0])]=(int(p[1],16),int(p[2]),int(p[4],16))
GRID=[18,22,26,30,36,44,52,60]
SINROW={18:181,22:182,26:183,30:184,36:177,44:178,52:179,60:180}
COSROW={18:189,22:190,26:191,30:192,36:185,44:186,52:187,60:188}
def romf(row):
    ef,s,sig=ROM[row]
    return ((-1)**s)*sig*2.0**((ef-0xFFFD)-68)
inputs=[l for l in open(f"{SCR}/dense_qn.txt").read().split("\n") if l.strip()]
hw=[l for l in open(f"{SCR}/dense_rn.txt").read().split("\n") if l.strip()]
# model outputs: quick approximate model in floats is NOT enough; instead use
# the h9 exact model P=68 comb=1 to produce model outputs, and take
# diff_hw_model = hw - model in ulps (small ints).  Reuse code by exec.
import importlib.util, sys
# inline minimal exact model (copy of h9 winner)
def rnP(s,sig,E,P):
    b=sig.bit_length(); sh=b-P
    if sh<=0: return (s,sig,E)
    top=sig>>sh; rem=sig&((1<<sh)-1); half=1<<(sh-1)
    if rem>half or (rem==half and (top&1)):
        top+=1
        if top>>P: top>>=1; sh+=1
    return (s,top,E+sh)
def fmul(a,b,P=68):
    if a[1]==0 or b[1]==0: return (0,0,0)
    return rnP(a[0]^b[0],a[1]*b[1],a[2]+b[2],P)
def fadd(a,b,P=68):
    if a[1]==0: return b
    if b[1]==0: return a
    E=min(a[2],b[2])
    v=((-1)**a[0])*(a[1]<<(a[2]-E))+((-1)**b[0])*(b[1]<<(b[2]-E))
    if v==0: return (0,0,0)
    return rnP(1 if v<0 else 0,abs(v),E,P)
def C68(row):
    ef,s,sig=ROM[row]; return (s,sig,(ef-0xFFFD)-68)
ONE=(0,1,0)
def to64(v):
    if v[1]==0: return (0,0)
    s,sig,E=v
    b=sig.bit_length(); sh=b-64
    if sh>0:
        top=sig>>sh; rem=sig&((1<<sh)-1); half=1<<(sh-1)
        if rem>half or (rem==half and (top&1)):
            top+=1
            if top>>64: top>>=1; sh+=1
        sig=top; E+=sh
    else:
        sig<<=-sh; E+=sh
    return ((s<<15)|(E+63+16383),sig)
data=defaultdict(list)
for i,l in enumerate(inputs):
    se,sig=int(l[:4],16),int(l[5:21],16)
    e=(se&0x7FFF)-16383
    rf=sig*2.0**(e-63)
    if rf<0.25: continue
    neg=(se>>15)&1
    rv=(0,sig,e-63)
    b=min(GRID,key=lambda k:abs(rf-k/64))
    sinT=C68(SINROW[b]); cosT=C68(COSROW[b])
    a=fadd(rv,(1,b,-6))
    asq=fmul(a,a)
    p=C68(172)
    for row in (171,170,169): p=fadd(fmul(p,asq),C68(row))
    S4=fadd(a,fmul(fmul(p,asq),a))
    q=C68(176)
    for row in (175,174,173): q=fadd(fmul(q,asq),C68(row))
    t=fmul(q,asq)
    u=fadd(fmul(sinT,t),fmul(cosT,S4))
    sinm=fadd(sinT,u)
    m=fmul(sinT,S4); m=(m[0]^1,m[1],m[2])
    v=fadd(fmul(cosT,t),m)
    cosm=fadd(cosT,v)
    if neg and sinm[1]: sinm=(sinm[0]^1,sinm[1],sinm[2])
    hf=hw[i].split()
    for tag,mv,hse,hsg in (("s",sinm,int(hf[1],16),int(hf[2],16)),
                            ("c",cosm,int(hf[3],16),int(hf[4],16))):
        mse,msg=to64(mv)
        if (mse,msg)==(hse,hsg): d=0
        else:
            if (mse&0x7FFF)==(hse&0x7FFF) and (mse>>15)==(hse>>15):
                d=hsg-msg
                if mse>>15: d=-d
            else:
                d=None  # exponent differs: 1-ulp across binade or worse
        af=a[1]*2.0**a[2]*((-1)**a[0])
        data[(b,tag)].append((af,d))
# regress per cell: d(ulps of result) ~ (ds*C4 + dc*S4)/ulp: for sin output:
# d_sin*2^-64*scale... just fit d = A + B*a (A ~ dsinT_effect, B ~ dcosT_effect)
print("cell side  n  none%  meanD  fitA  fitB   (d in output ulps)")
for key in sorted(data):
    rows=data[key]
    n=len(rows)
    good=[(a,d) for a,d in rows if d is not None]
    if len(good)<50: continue
    sa=sum(a for a,_ in good); sd=sum(d for _,d in good)
    saa=sum(a*a for a,_ in good); sad=sum(a*d for a,d in good)
    m=len(good)
    B=(m*sad-sa*sd)/(m*saa-sa*sa) if m*saa-sa*sa else 0.0
    A=(sd-B*sa)/m
    print(f"{key[0]:2d}/64 {key[1]}  {n:5d} {100.0*(n-len(good))/n:5.1f} {sd/m:+7.3f} {A:+8.3f} {B:+9.3f}")
