#!/usr/bin/env python3
"""Read the hardware's internal pi approximation straight off its sin output
on inputs near k*pi/2 (reduced argument tiny => sin(x) ~= r_hw)."""
from fractions import Fraction
SCR="/private/tmp/claude-501/-Users-steve-llm-coduo-binary-analysis/7d0d0788-22c7-4b55-8fbf-66cb5d3d5805/scratchpad"
PREC=400
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
def dec(se,sig):
    if sig==0: return Fraction(0)
    s=-1 if se>>15 else 1
    return s*Fraction(sig)*Fraction(2)**((se&0x7FFF)-16383-63)
def rn64(x):
    if x==0: return Fraction(0)
    sign=-1 if x<0 else 1; a=abs(x)
    e=a.numerator.bit_length()-a.denominator.bit_length()
    if Fraction(2)**e>a: e-=1
    sc=a*Fraction(2)**(63-e); i=sc.numerator//sc.denominator; fr=sc-i
    if fr>Fraction(1,2) or (fr==Fraction(1,2) and (i&1)): i+=1
    return sign*Fraction(i)*Fraction(2)**(e-63)
def trunc_bits(x,b):
    # truncate positive x to b significand bits
    e=x.numerator.bit_length()-x.denominator.bit_length()
    if Fraction(2)**e>x: e-=1
    sc=x*Fraction(2)**(b-1-e)
    return Fraction(sc.numerator//sc.denominator)*Fraction(2)**(e-(b-1))
def rn_bits(x,b):
    e=x.numerator.bit_length()-x.denominator.bit_length()
    if Fraction(2)**e>x: e-=1
    sc=x*Fraction(2)**(b-1-e); i=sc.numerator//sc.denominator
    if sc-i>=Fraction(1,2): i+=1
    return Fraction(i)*Fraction(2)**(e-(b-1))
# candidate internal pi/2 values
cands={}
for b in (64,65,66,67,68,72,80,128):
    cands[f"trunc{b}"]=trunc_bits(PI/2,b)
    cands[f"rn{b}"]=rn_bits(PI/2,b)
scores={k:[0,0] for k in cands}   # [explained, total]
UNEXPL=[]
n_probe=0
for inp,h in zip(inputs,hw):
    se,sig=int(inp[0],16),int(inp[1],16)
    e=(se&0x7FFF)-16383
    if not (0<=e<24): continue        # moderate class only
    x=dec(se,sig)
    N=round(x*2/PI)
    if N==0: continue
    r_true=x-N*PI/2
    if abs(r_true)>Fraction(1,2**20): continue   # near-multiple probes only
    n_probe+=1
    if h=="C2": continue
    hf=h.split()
    vs=dec(int(hf[1],16),int(hf[2],16))
    # quadrant: sin(x) = +-sin(r) or +-cos(r); for tiny r cos->1; select sin-like
    q=N&3
    if q==0: pred=lambda r: r
    elif q==2: pred=lambda r: -r
    else: continue                     # sin output is +-cos(tiny)= +-1, no r info
    ok_any=False
    for name,M in cands.items():
        r_cand=x-N*M
        # hw sin ~ rn64(r + c - r^3/6): for |r|<2^-20, cubic <=2^-60*r; compare loosely
        target=pred(r_cand)
        if vs==0 and target==0: match=True
        else:
            diff=abs(vs-target)
            match = diff <= abs(target)*Fraction(1,2**50) if target!=0 else vs==0
        if match: scores[name][0]+=1; ok_any=True
        scores[name][1]+=1
    if not ok_any and len(UNEXPL)<5:
        UNEXPL.append((inp,h,float(r_true)))
print(f"probes with sin-exposing quadrant: sum below / candidate")
for name in sorted(cands, key=lambda n:(len(n),n)):
    ex,tot=scores[name]
    if tot: print(f"  {name:9s}: {ex}/{tot} explained")
print(f"total near-multiple moderate probes: {n_probe}")
for u in UNEXPL:
    print("unexplained:",u)
