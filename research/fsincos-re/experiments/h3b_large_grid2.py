#!/usr/bin/env python3
from fractions import Fraction
import sys
sys.path.insert(0,'.')
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
print(f"probes: {len(probes)}", flush=True)
def score(fn, cap=None):
    ok=0
    P=probes if cap is None else probes[:cap]
    for x,N,vs in P:
        if rn_bits(fn(x,N),64)==vs: ok+=1
    return ok,len(P)
results=[]
# ---- S2: split N at m bits; intermediate rounded to W ----
for m in (2,4,8,12,16,20,24,28,32):
    for W in (64,65,66,67,68,70,80,96):
        for mode,f in (("tr",trunc_bits),("rn",rn_bits)):
            def fn(x,N,m=m,W=W,f=f):
                Nlo = N - (N>>m<<m) if N>=0 else -((-N) - ((-N)>>m<<m))
                Nhi = N - Nlo
                xp = f(x - Nhi*M66, W)
                return xp - Nlo*M66
            ok,n=score(fn,cap=200)
            if ok>150:
                ok,n=score(fn)
                results.append((ok,f"S2 m={m} W={W} {mode}"))
                if ok==n: print(f"S2 m={m} W={W} {mode}: FULL {ok}/{n}", flush=True)
results.sort(reverse=True)
print("top S2:", results[:8], flush=True)
# ---- S4: FPREM-style bit-by-bit with partial remainders rounded to W ----
res4=[]
for W in (64,65,66,67,68,69,70,72,80):
    for mode,f in (("tr",trunc_bits),("rn",rn_bits)):
        def fn(x,N,W=W,f=f):
            a=abs(x); s=-1 if x<0 else 1
            # subtract M66*2^j top-down
            while a >= M66:
                e=a.numerator.bit_length()-a.denominator.bit_length()
                if Fraction(2)**e>a: e-=1
                j=e  # M66 ~ 2^0.65: shift so M66*2^j <= a
                while M66*Fraction(2)**j > a: j-=1
                a = f(a - M66*Fraction(2)**j, W)
            if a > M66/2: a = f(a - M66, W)  # to nearest
            return s*a
        ok,n=score(fn,cap=150)
        if ok>100:
            ok,n=score(fn)
            res4.append((ok,f"S4 W={W} {mode}"))
            if ok==n: print(f"S4 W={W} {mode}: FULL {ok}/{n}", flush=True)
res4.sort(reverse=True)
print("top S4:", res4[:8], flush=True)
