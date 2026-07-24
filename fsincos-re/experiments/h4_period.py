#!/usr/bin/env python3
"""Kernel-tail structural probe: do flip positions show 1/64 (or other)
periodicity in r?  Uses ALL sweep lines now (reduction solved: model r ==
hw r everywhere), flips = model!=hw lines, r = the model's reduced arg."""
from fractions import Fraction
import math
SCR="/private/tmp/claude-501/-Users-steve-llm-coduo-binary-analysis/7d0d0788-22c7-4b55-8fbf-66cb5d3d5805/scratchpad"
PREC=380
def pi_frac(prec=PREC):
    def atan_inv(n):
        t,k=Fraction(0),0
        while True:
            term=Fraction((-1)**k,(2*k+1)*n**(2*k+1)); t+=term
            if abs(term)<Fraction(1,2**(prec+16)): return t
            k+=1
    return 16*atan_inv(5)-4*atan_inv(239)
PI=pi_frac()
def trunc_bits(x,b):
    s=-1 if x<0 else 1; a=abs(x)
    e=a.numerator.bit_length()-a.denominator.bit_length()
    if Fraction(2)**e>a: e-=1
    sc=a*Fraction(2)**(b-1-e)
    return s*Fraction(sc.numerator//sc.denominator)*Fraction(2)**(e-(b-1))
M66=trunc_bits(PI/2,66)
inputs=[l.split() for l in open(f"{SCR}/sweep_inputs.txt")]
hw=[l.strip() for l in open(f"{SCR}/skylake_fsincos_out.txt")]
model=[l.strip() for l in open(f"{SCR}/sky_model_out.txt")]
def dec(se,sig):
    if sig==0: return Fraction(0)
    s=-1 if se>>15 else 1
    return s*Fraction(sig)*Fraction(2)**((se&0x7FFF)-16383-63)
# bucket flips and totals by |r| in 64ths and in 128ths of 1
from collections import defaultdict
tot=defaultdict(int); flip=defaultdict(int)
sflip=defaultdict(int); cflip=defaultdict(int)
for inp,h,m in zip(inputs,hw,model):
    if h=="C2" or m=="C2" : continue
    se,sig=int(inp[0],16),int(inp[1],16)
    e=(se&0x7FFF)-16383
    x=dec(se,sig)
    ax=abs(x)
    if ax < Fraction(1,8): continue
    if ax < PI/4: r=ax
    else:
        N=round(x*2/PI)
        r=abs(x-N*M66)          # ~hw r (rounding irrelevant for bucketing)
        if r < Fraction(1,8): continue
    b=int(r*128)                # 128ths: r in [0.125, 0.7854] -> b in [16,100]
    tot[b]+=1
    if h!=m:
        flip[b]+=1
        hf,mf=h.split(),m.split()
        if (hf[1],hf[2])!=(mf[1],mf[2]): sflip[b]+=1
        if (hf[3],hf[4])!=(mf[3],mf[4]): cflip[b]+=1
print("bucket(r*128) n  flips  rate%   sin cos   | bucket mod 2 tells 1/64 grid")
for b in sorted(tot):
    if tot[b]<100: continue
    print(f"{b:4d} [{b/128:.4f},{(b+1)/128:.4f}) {tot[b]:6d} {flip[b]:4d} "
          f"{100.0*flip[b]/tot[b]:5.2f}  {sflip[b]:4d} {cflip[b]:4d}")
# aggregate by position within 1/64 cell (low bit of b)
lo=sum(flip[b] for b in flip if b%2==0); hi=sum(flip[b] for b in flip if b%2==1)
lot=sum(tot[b] for b in tot if b%2==0); hit=sum(tot[b] for b in tot if b%2==1)
print(f"\nwithin-1/64-cell halves: lower {lo}/{lot} = {100.0*lo/lot:.2f}%  "
      f"upper {hi}/{hit} = {100.0*hi/hit:.2f}%")
