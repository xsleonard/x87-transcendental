#!/usr/bin/env python3
"""Exact-bit test: hw sin output on near-multiple inputs vs RN64(x - N*M66),
for moderate AND large ranges; also test N = nearest-int(x*2/pi) convention."""
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
    e=x.numerator.bit_length()-x.denominator.bit_length()
    if Fraction(2)**e>x: e-=1
    sc=x*Fraction(2)**(b-1-e)
    return Fraction(sc.numerator//sc.denominator)*Fraction(2)**(e-(b-1))
M66=trunc_bits(PI/2,66)
inputs=[l.split() for l in open(f"{SCR}/sweep_inputs.txt")]
hw=[l.strip() for l in open(f"{SCR}/skylake_fsincos_out.txt")]
def dec(se,sig):
    if sig==0: return Fraction(0)
    s=-1 if se>>15 else 1
    return s*Fraction(sig)*Fraction(2)**((se&0x7FFF)-16383-63)
def enc_rn64(x):
    if x==0: return (0,0)
    sign=1 if x<0 else 0; a=abs(x)
    e=a.numerator.bit_length()-a.denominator.bit_length()
    if Fraction(2)**e>a: e-=1
    sc=a*Fraction(2)**(63-e); i=sc.numerator//sc.denominator; fr=sc-i
    if fr>Fraction(1,2) or (fr==Fraction(1,2) and (i&1)): i+=1
    if i==1<<64: i>>=1; e+=1
    return (sign<<15)|(e+16383), i
stats={}
ex_shown=0
for inp,h in zip(inputs,hw):
    se,sig=int(inp[0],16),int(inp[1],16)
    e=(se&0x7FFF)-16383
    if e<0 or e>=63: continue
    rng="mod" if e<24 else "lrg"
    x=dec(se,sig)
    N=round(x*2/PI)
    if N==0: continue
    r_true=x-N*PI/2
    if abs(r_true)>Fraction(1,2**20): continue
    q=N&3
    if q not in (0,2): continue
    if h=="C2": continue
    hf=h.split()
    hv=(int(hf[1],16),int(hf[2],16))
    r_cand=x-N*M66
    if q==2: r_cand=-r_cand
    want=enc_rn64(r_cand)
    key=(rng,)
    stats.setdefault(key,[0,0,0])
    stats[key][1]+=1
    if hv==want: stats[key][0]+=1
    else:
        # distance in ulps
        d = abs(hv[1]-want[1]) if hv[0]==want[0] else 999
        stats[key][2]=max(stats[key][2],d if d!=999 else stats[key][2])
        if ex_shown<6:
            ex_shown+=1
            print(f"nonexact[{rng}]: x={inp[0]} {inp[1]} N&3={q} hw={hf[1]},{hf[2]} want={want[0]:04x},{want[1]:016x} ulpdiff={d}")
for k,(a,b,mx) in sorted(stats.items()):
    print(f"{k[0]}: bit-exact {a}/{b}  (max seen ulp diff {mx})")
