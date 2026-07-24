#!/usr/bin/env python3
"""Characterize FSIN-vs-FSINCOS and FCOS-vs-FSINCOS bit differences:
positions in r, directions, and which path is correctly rounded."""
from fractions import Fraction
from collections import defaultdict
SCR="/private/tmp/claude-501/-Users-steve-llm-coduo-binary-analysis/7d0d0788-22c7-4b55-8fbf-66cb5d3d9805/scratchpad".replace("9805","9805")
SCR="/private/tmp/claude-501/-Users-steve-llm-coduo-binary-analysis/7d0d0788-22c7-4b55-8fbf-66cb5d3d5805/scratchpad"
inputs=[l.strip() for l in open(f"{SCR}/dense_qn.txt") if l.strip()]
sc=[l.split() for l in open(f"{SCR}/dense_rn.txt") if l.strip()]
fs=[l.split() for l in open(f"{SCR}/dense_fsin.txt") if l.strip()]
fc=[l.split() for l in open(f"{SCR}/dense_fcos.txt") if l.strip()]
PREC=240
def ssin(t):
    tot=Fraction(t); term=tot; k=1
    while abs(term)>Fraction(1,2**(PREC+16)):
        term=-term*t*t/((2*k)*(2*k+1)); tot+=term; k+=1
    return tot
def scos(t):
    tot=Fraction(1); term=tot; k=1
    while abs(term)>Fraction(1,2**(PREC+16)):
        term=-term*t*t/((2*k-1)*(2*k)); tot+=term; k+=1
    return tot
def dec(se,sig):
    if sig==0: return Fraction(0)
    return ((-1)**(se>>15))*Fraction(sig)*Fraction(2)**((se&0x7FFF)-16383-63)
def enc_rn(x):
    if x==0: return (0,0)
    s=1 if x<0 else 0; a=abs(x)
    e=a.numerator.bit_length()-a.denominator.bit_length()
    if Fraction(2)**e>a: e-=1
    sc_=a*Fraction(2)**(63-e); i=sc_.numerator//sc_.denominator; fr=sc_-i
    if fr>Fraction(1,2) or (fr==Fraction(1,2) and (i&1)): i+=1
    if i==1<<64: i>>=1; e+=1
    return (s<<15)|(e+16383), i
# r-distribution of diffs (bins of 1/128 over [0, 0.25)) + directions + CR
rate=defaultdict(lambda:[0,0,0])   # bin -> [n, sindiff, cosdiff]
dirs=defaultdict(int)
cr=defaultdict(int)
examples=[]
for l,a,b,c in zip(inputs,sc,fs,fc):
    se,sig=int(l[:4],16),int(l[5:21],16)
    e=(se&0x7FFF)-16383
    rf=sig*2.0**(e-63)
    if rf>=0.25: continue
    bn=int(rf*128)
    rate[bn][0]+=1
    ds=(a[1],a[2])!=(b[1],b[2]); dc=(a[3],a[4])!=(c[1],c[2])
    if not ds and not dc: continue
    x=dec(se,sig)
    if ds:
        rate[bn][1]+=1
        v_sc=dec(int(a[1],16),int(a[2],16)); v_f=dec(int(b[1],16),int(b[2],16))
        up = v_f > v_sc
        dirs[("sin","FSIN>" if up else "FSIN<")]+=1
        crv=enc_rn(ssin(x))
        w_sc = (int(a[1],16),int(a[2],16))==crv
        w_f  = (int(b[1],16),int(b[2],16))==crv
        cr[("sin","SINCOS" if w_sc else ("FSIN" if w_f else "neither"))]+=1
        if len(examples)<5: examples.append((rf,"sin",float(v_f-v_sc)*2**64))
    if dc:
        rate[bn][2]+=1
        v_sc=dec(int(a[3],16),int(a[4],16)); v_f=dec(int(c[1],16),int(c[2],16))
        up = v_f > v_sc
        dirs[("cos","FCOS>" if up else "FCOS<")]+=1
        crv=enc_rn(scos(x))
        w_sc = (int(a[3],16),int(a[4],16))==crv
        w_f  = (int(c[1],16),int(c[2],16))==crv
        cr[("cos","SINCOS" if w_sc else ("FCOS" if w_f else "neither"))]+=1
print("diff rate by r (1/128 bins), showing bins with any diffs:")
for bn in sorted(rate):
    n,s_,c_=rate[bn]
    if s_ or c_:
        print(f"  r in [{bn/128:.4f},{(bn+1)/128:.4f}): n={n:6d} sindiff={s_:4d} ({100.0*s_/n:.2f}%) cosdiff={c_:4d} ({100.0*c_/n:.2f}%)")
print("\ndirections:", dict(dirs))
print("correctly-rounded winner:", dict(cr))
for ex in examples: print("example:", ex)
