#!/usr/bin/env python3
import subprocess
from fractions import Fraction
SCR="/private/tmp/claude-501/-Users-steve-llm-coduo-binary-analysis/7d0d0788-22c7-4b55-8fbf-66cb5d3d5805/scratchpad"
PREC=360
inputs=[l.split() for l in open(f"{SCR}/sweep_inputs.txt")]
hw=[l.strip() for l in open(f"{SCR}/skylake_fsincos_out.txt")]
ref=[l.strip() for l in open(f"{SCR}/ref_out.txt")]
def path_of(se,sig):
    e=(se&0x7FFF)-16383
    if sig==0: return "zero"
    if e>=63: return "c2"
    if e>=24: return "large"
    if e>=0: return "moderate"
    if e==-1 and sig>=0xC90FDAA22168C234: return "moderate"
    if e>=-3: return "qn"
    return "qs"
def dec(se,sig):
    s=-1 if se>>15 else 1
    return s*Fraction(sig)*Fraction(2)**((se&0x7FFF)-16383-63)
def series_sin(t):
    tot=Fraction(0); term=t; k=1
    while abs(term)>Fraction(1,2**(PREC+16)):
        tot+=term; term=-term*t*t/((2*k)*(2*k+1)); k+=1
    return tot
def series_cos(t):
    tot=Fraction(0); term=Fraction(1); k=1
    while abs(term)>Fraction(1,2**(PREC+16)):
        tot+=term; term=-term*t*t/((2*k-1)*(2*k)); k+=1
    return tot
def enc_rn(x):
    sign=1 if x<0 else 0; a=abs(x)
    e=a.numerator.bit_length()-a.denominator.bit_length()
    if Fraction(2)**e>a: e-=1
    sc=a*Fraction(2)**(63-e); i=sc.numerator//sc.denominator; fr=sc-i
    if fr>Fraction(1,2) or (fr==Fraction(1,2) and (i&1)): i+=1
    if i==1<<64: i>>=1; e+=1
    return (sign<<15)|(e+16383), i
hw_cr=ref_cr=neither=0
rbuckets={}
sin_mm=cos_mm=0
for idx,(inp,h,r) in enumerate(zip(inputs,hw,ref)):
    se,sig=int(inp[0],16),int(inp[1],16)
    if path_of(se,sig)!="qn" or h==r: continue
    x=dec(se,sig)
    hf,rf=h.split(),r.split()
    for pos,truefn,tag in ((1,series_sin,"sin"),(3,series_cos,"cos")):
        hv=(int(hf[pos],16),int(hf[pos+1],16))
        rv=(int(rf[pos],16),int(rf[pos+1],16))
        if hv==rv: continue
        if tag=="sin": sin_mm+=1
        else: cos_mm+=1
        cr=enc_rn(truefn(x))
        if hv==cr and rv!=cr: hw_cr+=1
        elif rv==cr and hv!=cr: ref_cr+=1
        else: neither+=1
        b=round(float(abs(x))*16)/16
        rbuckets.setdefault((tag,b),[0,0])
        rbuckets[(tag,b)][0]+=1
# totals per bucket for rate
tot_b={}
for inp,h,r in zip(inputs,hw,ref):
    se,sig=int(inp[0],16),int(inp[1],16)
    if path_of(se,sig)!="qn": continue
    b=round(float(abs(dec(se,sig)))*16)/16
    for tag in ("sin","cos"):
        tot_b.setdefault((tag,b),0); tot_b[(tag,b)]+=1
print(f"mismatched outputs: sin={sin_mm} cos={cos_mm}")
print(f"hardware correctly rounded (ref not): {hw_cr}")
print(f"reference correctly rounded (hw not): {ref_cr}")
print(f"neither/both: {neither}")
print("\nmismatch rate by |x| bucket (16ths):")
for (tag,b) in sorted(tot_b):
    n=tot_b[(tag,b)]; m=rbuckets.get((tag,b),[0])[0]
    if n>200: print(f"  {tag} |x|~{b:5.3f}: {m}/{n} = {100.0*m/n:5.2f}%")
