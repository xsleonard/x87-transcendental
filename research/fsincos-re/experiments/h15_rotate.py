#!/usr/bin/env python3
"""Rotate per-input (Delta_sin, Delta_cos) into shared-intermediate coords:
dC4 = sinT*Ds + cosT*Dc ; dS4 = cosT*Ds - sinT*Dc.  Grid/cluster analysis."""
from fractions import Fraction
from collections import defaultdict
SCR="/private/tmp/claude-501/-Users-steve-llm-coduo-binary-analysis/7d0d0788-22c7-4b55-8fbf-66cb5d3d5805/scratchpad"
ROM={}
for line in open("/Users/steve/llm/coduo-binary-analysis/fsincos-re/data/pentium-rom/rom-constants.tsv"):
    p=line.rstrip("\n").split("\t")
    if p[0]=="row": continue
    ROM[int(p[0])]=(int(p[1],16),int(p[2]),int(p[4],16))
ROM[186]=(ROM[186][0],ROM[186][1],ROM[186][2]-(1<<44))
def romfrac(row):
    ef,s,sig=ROM[row]
    return ((-1)**s)*Fraction(sig)*Fraction(2)**((ef-0xFFFD)-68)
def dec(se,sig):
    if sig==0: return Fraction(0)
    return ((-1)**(se>>15))*Fraction(sig)*Fraction(2)**((se&0x7FFF)-16383-63)
B=22   # cell 22/64
SINROW={18:181,22:182,26:183,30:184}; COSROW={18:189,22:190,26:191,30:192}
sinT=romfrac(SINROW[B]); cosT=romfrac(COSROW[B])
def S_exact(a):
    p=romfrac(172)
    for row in (171,170,169): p=p*a*a+romfrac(row)
    return a+p*a*a*a
def Cm1_exact(a):
    q=romfrac(176)
    for row in (175,174,173): q=q*a*a+romfrac(row)
    return q*a*a
inputs=[l for l in open(f"{SCR}/dense_qn.txt").read().split("\n") if l.strip()]
hw_rn=[l for l in open(f"{SCR}/dense_rn.txt").read().split("\n") if l.strip()]
hw_rd=[l for l in open(f"{SCR}/dense_rd.txt").read().split("\n") if l.strip()]
pts=[]
for li,l in enumerate(inputs):
    se,sig=int(l[:4],16),int(l[5:21],16)
    e=(se&0x7FFF)-16383
    rf=sig*2.0**(e-63)
    if not (20/64<=rf<24/64): continue
    neg=(se>>15)&1
    r=Fraction(sig)*Fraction(2)**(e-63)
    a=r-Fraction(B,64)
    S=S_exact(a); t=Cm1_exact(a)
    Tsin=sinT*(1+t)+cosT*S
    Tcos=cosT*(1+t)-sinT*S
    if neg: Tsin=-Tsin
    rnf=hw_rn[li].split(); rdf=hw_rd[li].split()
    Ds=Dc=None
    out=[]
    for tag,Tm,idx in (("s",Tsin,1),("c",Tcos,3)):
        hn=dec(int(rnf[idx],16),int(rnf[idx+1],16))
        hd=dec(int(rdf[idx],16),int(rdf[idx+1],16))
        hne=(int(rnf[idx],16)&0x7FFF)-16383
        u=Fraction(2)**(hne-63)
        if hn>=0: lo,hi=hd,hd+u
        else: lo,hi=hd-u,hd
        lo=max(lo,hn-u/2); hi=min(hi,hn+u/2)
        out.append(((lo+hi)/2, hi-lo))
    Dsm,_=out[0]; Dcm,_=out[1]
    Ds=Dsm-Tsin; Dc=Dcm-Tcos
    if neg: Ds=-Ds
    dC4=sinT*Ds+cosT*Dc
    dS4=cosT*Ds-sinT*Dc
    pts.append((float(a),float(dC4*Fraction(2)**70),float(dS4*Fraction(2)**70)))
    if len(pts)>=8000: break
print(f"n={len(pts)}")
# histogram both coordinates
def hist(vals,name):
    h=defaultdict(int)
    for v in vals: h[round(v/2)*2]+=1
    top=sorted(h.items(),key=lambda kv:-kv[1])[:10]
    import statistics
    print(f"{name}: mean={statistics.mean(vals):+.2f} sd={statistics.pstdev(vals):.2f} "
          f"peaks:"+" ".join(f"{k}:{100.0*v/len(vals):.0f}%" for k,v in top))
hist([p[1] for p in pts],"dC4*2^70")
hist([p[2] for p in pts],"dS4*2^70")
# dS4 vs a: is it a staircase in a? sample a-sorted consecutive diffs
pts.sort()
print("\nsorted-by-a sample (a, dC4, dS4):")
for i in range(0,len(pts),len(pts)//24):
    print(f"  a={pts[i][0]:+.6f}  dC4={pts[i][1]:+8.2f}  dS4={pts[i][2]:+8.2f}")
