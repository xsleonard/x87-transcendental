#!/usr/bin/env python3
"""Characterize the remaining mismatches of the best model (both regions)."""
import random
from fractions import Fraction
SCR="/private/tmp/claude-501/-Users-steve-llm-coduo-binary-analysis/7d0d0788-22c7-4b55-8fbf-66cb5d3d5805/scratchpad"
ROM={}
for line in open("/Users/steve/llm/coduo-binary-analysis/fsincos-re/data/pentium-rom/rom-constants.tsv"):
    p=line.rstrip("\n").split("\t")
    if p[0]=="row": continue
    ROM[int(p[0])]=(int(p[1],16),int(p[2]),int(p[4],16))
ROM[186]=(ROM[186][0],ROM[186][1],ROM[186][2]-(1<<43))
ROM[189]=(ROM[189][0],ROM[189][1],ROM[189][2]-(1<<12))
def romfrac(row):
    ef,s,sig=ROM[row]
    return ((-1)**s)*Fraction(sig)*Fraction(2)**((ef-0xFFFD)-68)
GRID=[18,22,26,30,36,44,52,60]
SINROW={18:181,22:182,26:183,30:184,36:177,44:178,52:179,60:180}
COSROW={18:189,22:190,26:191,30:192,36:185,44:186,52:187,60:188}
WIDE={36,44,52,60}
def rn64f(x):
    if x==0: return Fraction(0),(0,0)
    s=1 if x<0 else 0; a=abs(x)
    e=a.numerator.bit_length()-a.denominator.bit_length()
    if Fraction(2)**e>a: e-=1
    sc=a*Fraction(2)**(63-e); i=sc.numerator//sc.denominator; fr=sc-i
    if fr>Fraction(1,2) or (fr==Fraction(1,2) and (i&1)): i+=1
    if i==1<<64: i>>=1; e+=1
    v=((-1)**s)*Fraction(i)*Fraction(2)**(e-63)
    return v,((s<<15)|(e+16383),i)
def model(x):
    ax=abs(x); neg = x<0
    rf=float(ax)
    if rf<0.25:
        a=ax
        p=romfrac(162)
        for row in (161,160,159,158,157): p=p*a*a+romfrac(row)
        S=a+p*a*a*a
        q=romfrac(168)
        for row in (167,166,165,164,163): q=q*a*a+romfrac(row)
        sin=S; cos=1+q*a*a
        cell=0
    else:
        b=min(GRID,key=lambda k:abs(rf-k/64))
        six=b in WIDE
        rows=(162,161,160,159,158,157) if six else (172,171,170,169)
        a=ax-Fraction(b,64)
        p=romfrac(rows[0])
        for row in rows[1:]: p=p*a*a+romfrac(row)
        S=a+p*a*a*a
        rows=(168,167,166,165,164,163) if six else (176,175,174,173)
        q=romfrac(rows[0])
        for row in rows[1:]: q=q*a*a+romfrac(row)
        t=q*a*a
        sinT=romfrac(SINROW[b]); cosT=romfrac(COSROW[b])
        sin=sinT*(1+t)+cosT*S
        cos=cosT*(1+t)-sinT*S
        cell=b
    if neg: sin=-sin
    return sin,cos,cell
inputs=[l for l in open(f"{SCR}/dense_qn.txt").read().split("\n") if l.strip()]
hw=[l for l in open(f"{SCR}/dense_rn.txt").read().split("\n") if l.strip()]
random.seed(23)
idxs=random.sample(range(len(inputs)),24000)
from collections import defaultdict
mis=defaultdict(int); tot=defaultdict(int)
ex=[]
for i in idxs:
    l=inputs[i]
    se,sig=int(l[:4],16),int(l[5:21],16)
    e=(se&0x7FFF)-16383
    rf=sig*2.0**(e-63)
    if rf>=0.7853981633974483: continue
    x=((-1)**(se>>15))*Fraction(sig)*Fraction(2)**(e-63)
    sin,cos,cell=model(x)
    _,es=rn64f(sin); _,ec=rn64f(cos)
    hf=hw[i].split()
    hs=(int(hf[1],16),int(hf[2],16)); hc=(int(hf[3],16),int(hf[4],16))
    tot[cell]+=1
    bad_s = es!=hs; bad_c = ec!=hc
    if bad_s: mis[(cell,"s")]+=1
    if bad_c: mis[(cell,"c")]+=1
    if (bad_s or bad_c) and len(ex)<14:
        # distance of exact value to nearest RN boundary, in ulps
        def bdist(v):
            a=abs(v)
            eb=a.numerator.bit_length()-a.denominator.bit_length()
            if Fraction(2)**eb>a: eb-=1
            sc=a*Fraction(2)**(63-eb)
            fr=sc-(sc.numerator//sc.denominator)
            return float(min(abs(fr-Fraction(1,2)), fr, 1-fr))
        ex.append((rf, cell, "s" if bad_s else "c", bdist(sin if bad_s else cos)))
print("cell totals:", dict(tot))
print("mismatches:", dict(mis))
print("\nexamples (rf, cell, side, dist-to-boundary in ulp):")
for t in ex: print(f"  rf={t[0]:.6f} cell={t[1]} {t[2]} bdist={t[3]:.6f}")
