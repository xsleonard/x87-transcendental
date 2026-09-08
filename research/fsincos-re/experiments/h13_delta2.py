#!/usr/bin/env python3
"""Measure Delta2 = T_hw - T_model2 (current best model, near-exact ops)
via RN+RD interval constraints; print per-cell histograms (2^-70 units)."""
from collections import defaultdict
SCR="/private/tmp/claude-501/-Users-steve-llm-coduo-binary-analysis/7d0d0788-22c7-4b55-8fbf-66cb5d3d5805/scratchpad"
ROM={}
for line in open("/Users/steve/llm/coduo-binary-analysis/fsincos-re/data/pentium-rom/rom-constants.tsv"):
    p=line.rstrip("\n").split("\t")
    if p[0]=="row": continue
    ROM[int(p[0])]=(int(p[1],16),int(p[2]),int(p[4],16))
for row,d in {189:-(1<<13),186:-(1<<44)}.items():
    ef,s,sig=ROM[row]; ROM[row]=(ef,s,sig+d)
from fractions import Fraction
def romfrac(row):
    ef,s,sig=ROM[row]
    return ((-1)**s)*Fraction(sig)*Fraction(2)**((ef-0xFFFD)-68)
GRID=[18,22,26,30,36,44,52,60]
SINROW={18:181,22:182,26:183,30:184,36:177,44:178,52:179,60:180}
COSROW={18:189,22:190,26:191,30:192,36:185,44:186,52:187,60:188}
WIDE={36,44,52,60}
def S_exact(a,six):
    rows=(162,161,160,159,158,157) if six else (172,171,170,169)
    p=romfrac(rows[0])
    for row in rows[1:]: p=p*a*a+romfrac(row)
    return a+p*a*a*a
def Cm1_exact(a,six):
    rows=(168,167,166,165,164,163) if six else (176,175,174,173)
    q=romfrac(rows[0])
    for row in rows[1:]: q=q*a*a+romfrac(row)
    return q*a*a
def dec(se,sig):
    if sig==0: return Fraction(0)
    return ((-1)**(se>>15))*Fraction(sig)*Fraction(2)**((se&0x7FFF)-16383-63)
inputs=[l for l in open(f"{SCR}/dense_qn.txt").read().split("\n") if l.strip()]
hw_rn=[l for l in open(f"{SCR}/dense_rn.txt").read().split("\n") if l.strip()]
hw_rd=[l for l in open(f"{SCR}/dense_rd.txt").read().split("\n") if l.strip()]
H=defaultdict(lambda: defaultdict(int))
NN=defaultdict(int)
import itertools
count=0
for li,l in enumerate(inputs):
    if count>60000: break
    se,sig=int(l[:4],16),int(l[5:21],16)
    e=(se&0x7FFF)-16383
    rf=sig*2.0**(e-63)
    if rf<0.25 or rf>=0.7853981633974483: continue
    count+=1
    neg=(se>>15)&1
    r=Fraction(sig)*Fraction(2)**(e-63)
    b=min(GRID,key=lambda k:abs(rf-k/64))
    six=b in WIDE
    a=r-Fraction(b,64)
    sinT=romfrac(SINROW[b]); cosT=romfrac(COSROW[b])
    S=S_exact(a,six); t=Cm1_exact(a,six)
    Tsin=sinT*(1+t)+cosT*S
    Tcos=cosT*(1+t)-sinT*S
    if neg: Tsin=-Tsin
    rnf=hw_rn[li].split(); rdf=hw_rd[li].split()
    for tag,Tm,idx in (("s",Tsin,1),("c",Tcos,3)):
        hn=dec(int(rnf[idx],16),int(rnf[idx+1],16))
        hd=dec(int(rdf[idx],16),int(rdf[idx+1],16))
        # ulp at hn
        hne=(int(rnf[idx],16)&0x7FFF)-16383
        u=Fraction(2)**(hne-63)
        # T_hw interval: [hd, hd+u) (pos) or (hd-u, hd] (neg); RN halves it
        if hn>=0: lo,hi=hd,hd+u
        else: lo,hi=hd-u,hd
        lo=max(lo,hn-u/2); hi=min(hi,hn+u/2)
        mid=(lo+hi)/2
        d=float((mid-Tm)*Fraction(2)**70)
        Hb=H[(b,tag)]
        Hb[round(d/2)*2]+=1
        NN[(b,tag)]+=1
for key in sorted(H):
    tot=NN[key]
    top=sorted(H[key].items(),key=lambda kv:-kv[1])[:7]
    print(f"cell {key[0]}/64 {key[1]} n={tot}: peak bins(2^-70): "+
          " ".join(f"{k}:{100.0*v/tot:.0f}%" for k,v in top))
