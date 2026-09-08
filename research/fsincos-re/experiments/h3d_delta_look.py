#!/usr/bin/env python3
"""Characterize delta = r_model - r_hw for large-range near-multiple probes."""
from fractions import Fraction
import math
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
def trunc_bits(x,b):
    s=-1 if x<0 else 1; a=abs(x)
    e=a.numerator.bit_length()-a.denominator.bit_length()
    if Fraction(2)**e>a: e-=1
    sc=a*Fraction(2)**(b-1-e)
    return s*Fraction(sc.numerator//sc.denominator)*Fraction(2)**(e-(b-1))
M66=trunc_bits(PI/2,66)
inputs=[l.split() for l in open(f"{SCR}/sweep_inputs.txt")]
hw=[l.strip() for l in open(f"{SCR}/skylake_fsincos_out.txt")]
def dec(se,sig):
    if sig==0: return Fraction(0)
    s=-1 if se>>15 else 1
    return s*Fraction(sig)*Fraction(2)**((se&0x7FFF)-16383-63)
rows=[]
for inp,h in zip(inputs,hw):
    se,sig=int(inp[0],16),int(inp[1],16)
    e=(se&0x7FFF)-16383
    if not (24<=e<63): continue
    x=dec(se,sig)
    N=round(x*2/PI)
    if N==0 or h=="C2": continue
    if abs(x-N*PI/2)>Fraction(1,2**18): continue
    q=N&3
    if q not in (0,2): continue
    hf=h.split()
    vs=dec(int(hf[1],16),int(hf[2],16))
    if q==2: vs=-vs
    model=x-N*M66
    d=model-vs
    rows.append((e,N,x,vs,d))
rows.sort()
print(f"{len(rows)} probes.  columns: e | log2|N| | log2|d| | d*2^66/N | d*2^(66)| sign")
import random
random.seed(1)
for e,N,x,vs,d in random.sample(rows,25):
    l2d = math.log2(abs(d)) if d else -999
    print(f"e={e:2d} log2N={math.log2(abs(N)):6.2f} log2|d|={l2d:8.2f} "
          f"d*2^66/N={float(d*Fraction(2)**66/N):+.6e} dsign={'-' if d<0 else '+'}")
# aggregate: is log2|d| ~ log2 N - 130?  (would mean d ~ N * 2^-130ish)
import statistics
vals=[(math.log2(abs(N)), math.log2(abs(d))) for e,N,x,vs,d in rows if d]
diffs=[b-a for a,b in vals]
print("\nlog2|d| - log2|N|: mean %.2f  sd %.2f  min %.2f max %.2f  (n=%d, d==0: %d)"
      % (statistics.mean(diffs), statistics.pstdev(diffs), min(diffs), max(diffs),
         len(diffs), sum(1 for *_,d in rows if d==0)))
# distribution of d in units of 2^-66*N-scaled? try d / (N*2^-66) histogram buckets
