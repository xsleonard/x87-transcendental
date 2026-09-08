#!/usr/bin/env python3
"""Solve for the hardware's large-range reduction modulus directly.
Assume r_hw = x - N*M_hw (exact), output vs = RN64(r_hw).
Then M_hw in [(x - vs - u/2)/N, (x - vs + u/2)/N], u = ulp(vs).
Intersect across probes."""
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
def ulp_of_enc(se):
    return Fraction(2)**(((se&0x7FFF)-16383)-63)
lo_int, hi_int = None, None
n_used=0
viol=[]
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
    vse=int(hf[1],16); vsg=int(hf[2],16)
    vs=dec(vse,vsg)
    if q==2: vs=-vs
    u=ulp_of_enc(vse)
    lo=(x - vs - u/2)/N; hi=(x - vs + u/2)/N
    if N<0: lo,hi=hi,lo
    n_used+=1
    if lo_int is None: lo_int,hi_int=lo,hi
    else:
        nlo=max(lo_int,lo); nhi=min(hi_int,hi)
        if nlo>nhi:
            viol.append((inp,N,float((lo-hi_int)*2**66),float((lo_int-hi)*2**66)))
            continue
        lo_int,hi_int=nlo,nhi
print(f"probes used: {n_used}, violations of common interval: {len(viol)}")
if lo_int is not None:
    width=hi_int-lo_int
    print(f"interval width * 2^66: {float(width*2**66):.6g}")
    mid=(lo_int+hi_int)/2
    print(f"midpoint - M66, in units of 2^-66: {float((mid-M66)*2**66):.9f}")
    print(f"pi/2 - M66, in units of 2^-66:    {float((PI/2-M66)*2**66):.9f}")
    # express candidate as pi/2 truncated at B bits: find B where trunc matches interval
    for B in range(64,141):
        c=trunc_bits(PI/2,B)
        if lo_int<=c<=hi_int: print(f"  trunc{B}(pi/2) IN interval")
    # exact 66-bit + specific tail patterns?
    lo_t=float((lo_int-M66)*2**66); hi_t=float((hi_int-M66)*2**66)
    print(f"interval rel M66 in 2^-66 units: [{lo_t:.9f}, {hi_t:.9f}]")
