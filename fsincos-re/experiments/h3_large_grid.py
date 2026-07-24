#!/usr/bin/env python3
"""Large-range reduction hypothesis grid.

For 2^24 <= |x| < 2^63 near k*pi/2, hw sin output ~= internal r.
S3 family: r = RN64(x - f_P(N*M66)) where f_P rounds/truncates the product
N*M66 to P significand bits, P in 64..130.
S2 family: split N = Nhi*2^m + Nlo; x' = g_W(x - Nhi*2^m*M66);
           r = RN64(x' - Nlo*M66); g_W = RN/trunc to W bits.
"""
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
def trunc_bits(x,b):
    s=-1 if x<0 else 1; a=abs(x)
    if a==0: return Fraction(0)
    e=a.numerator.bit_length()-a.denominator.bit_length()
    if Fraction(2)**e>a: e-=1
    sc=a*Fraction(2)**(b-1-e)
    return s*Fraction(sc.numerator//sc.denominator)*Fraction(2)**(e-(b-1))
def rn_bits(x,b):
    s=-1 if x<0 else 1; a=abs(x)
    if a==0: return Fraction(0)
    e=a.numerator.bit_length()-a.denominator.bit_length()
    if Fraction(2)**e>a: e-=1
    sc=a*Fraction(2)**(b-1-e); i=sc.numerator//sc.denominator; fr=sc-i
    if fr>Fraction(1,2) or (fr==Fraction(1,2) and (i&1)): i+=1
    return s*Fraction(i)*Fraction(2)**(e-(b-1))
M66=trunc_bits(PI/2,66)
inputs=[l.split() for l in open(f"{SCR}/sweep_inputs.txt")]
hw=[l.strip() for l in open(f"{SCR}/skylake_fsincos_out.txt")]
def dec(se,sig):
    if sig==0: return Fraction(0)
    s=-1 if se>>15 else 1
    return s*Fraction(sig)*Fraction(2)**((se&0x7FFF)-16383-63)
# collect probes: large range, near-multiple, quadrant exposing sin=r
probes=[]
for inp,h in zip(inputs,hw):
    se,sig=int(inp[0],16),int(inp[1],16)
    e=(se&0x7FFF)-16383
    if not (24<=e<63): continue
    x=dec(se,sig)
    N=round(x*2/PI)
    if N==0: continue
    if abs(x-N*PI/2)>Fraction(1,2**18): continue
    q=N&3
    if q not in (0,2): continue
    if h=="C2": continue
    hf=h.split()
    vs=dec(int(hf[1],16),int(hf[2],16))
    if q==2: vs=-vs
    probes.append((x,N,vs))
print(f"probes: {len(probes)}")
def score(fn):
    ok=0
    for x,N,vs in probes:
        r=rn_bits(fn(x,N),64)
        if r==vs: ok+=1
    return ok
# S1 baseline
print("S1 exact-product:", score(lambda x,N: x-N*M66), "/", len(probes))
# S3: product width grid
best=[]
for P in list(range(64,131,2))+[65,67,69,71,127,129]:
    for mode,f in (("tr",trunc_bits),("rn",rn_bits)):
        s=score(lambda x,N,P=P,f=f: x-f(N*M66,P))
        if s>len(probes)*0.5: best.append((s,f"S3 {mode}{P}"))
        if s==len(probes): print(f"S3 {mode}{P}: FULL MATCH")
best.sort(reverse=True)
print("top S3:", best[:6])
