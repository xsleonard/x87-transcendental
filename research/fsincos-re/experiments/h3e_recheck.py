#!/usr/bin/env python3
"""Was the 'large-range artifact' just the neglected cubic?  Score the full
C Skylake model vs hw on exactly the class-F near-multiple probe lines."""
from fractions import Fraction
SCR="/private/tmp/claude-501/-Users-steve-llm-coduo-binary-analysis/7d0d0788-22c7-4b55-8fbf-66cb5d3d5805/scratchpad"
PREC=420
def pi_frac(prec=PREC):
    def atan_inv(n):
        t,k=Fraction(0),0
        while True:
            term=Fraction((-1)**k,(2*k+1)*n**(2*k+1)); t+=term
            if abs(term)<Fraction(1,2**(prec+16)): return t
            k+=1
    return 16*atan_inv(5)-4*atan_inv(239)
PI=pi_frac()
inputs=[l.split() for l in open(f"{SCR}/sweep_inputs.txt")]
hw=[l.strip() for l in open(f"{SCR}/skylake_fsincos_out.txt")]
model=[l.strip() for l in open(f"{SCR}/sky_model_out.txt")]
def dec(se,sig):
    if sig==0: return Fraction(0)
    s=-1 if se>>15 else 1
    return s*Fraction(sig)*Fraction(2)**((se&0x7FFF)-16383-63)
near=far=0; near_ok=far_ok=0
for inp,h,m in zip(inputs,hw,model):
    se,sig=int(inp[0],16),int(inp[1],16)
    e=(se&0x7FFF)-16383
    if not (24<=e<63): continue
    x=dec(se,sig)
    N=round(x*2/PI)
    isnear = N!=0 and abs(x-N*PI/2)<=Fraction(1,2**18)
    if isnear: near+=1; near_ok += (h==m)
    else: far+=1; far_ok += (h==m)
print(f"large near-multiple lines: {near}, model==hw: {near_ok} ({100.0*near_ok/near:.2f}%)")
print(f"large general lines:       {far}, model==hw: {far_ok} ({100.0*far_ok/far:.2f}%)")
