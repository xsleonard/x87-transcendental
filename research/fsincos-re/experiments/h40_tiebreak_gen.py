#!/usr/bin/env python3
"""Generate 'tiebreaker' inputs: model sin/cos value within ~2^-71.5 of an
RN64 boundary.  Newton-hop across significands for efficiency."""
import sys
SCR="/private/tmp/claude-501/-Users-steve-llm-coduo-binary-analysis/7d0d0788-22c7-4b55-8fbf-66cb5d3d5805/scratchpad"
ROM={}
for line in open("/Users/steve/llm/coduo-binary-analysis/fsincos-re/data/pentium-rom/rom-constants.tsv"):
    p=line.rstrip("\n").split("\t")
    if p[0]=="row": continue
    ROM[int(p[0])]=(int(p[1],16),int(p[2]),int(p[4],16))
ROM[186]=(ROM[186][0],ROM[186][1],ROM[186][2]-(1<<43))
ROM[189]=(ROM[189][0],ROM[189][1],ROM[189][2]-(1<<12))
def rnP(s,sig,E,P):
    b=sig.bit_length(); sh=b-P
    if sh<=0: return (s,sig,E)
    top=sig>>sh; rem=sig&((1<<sh)-1); half=1<<(sh-1)
    if rem>half or (rem==half and (top&1)):
        top+=1
        if top>>P: top>>=1; sh+=1
    return (s,top,E+sh)
def fmul(a,b,P=64):
    if a[1]==0 or b[1]==0: return (0,0,0)
    return rnP(a[0]^b[0],a[1]*b[1],a[2]+b[2],P)
def fadd(a,b,P=64):
    if a[1]==0: return b
    if b[1]==0: return a
    E=min(a[2],b[2])
    v=((-1)**a[0])*(a[1]<<(a[2]-E))+((-1)**b[0])*(b[1]<<(b[2]-E))
    if v==0: return (0,0,0)
    return rnP(1 if v<0 else 0,abs(v),E,P)
def C68(row):
    ef,s,sig=ROM[row]; return (s,sig,(ef-0xFFFD)-68)
SINROW={18:181,22:182,26:183,30:184,36:177,44:178,52:179,60:180}
COSROW={18:189,22:190,26:191,30:192,36:185,44:186,52:187,60:188}
ONE=(0,1,0)
def model_T(sig64, side):
    """exact pre-round value (int, E) of model sin/cos for +x with sig64,exp -1/-2"""
    # inputs restricted to binade [-2]: r in [0.25,0.5): cells 18-30
    e=-2
    rv=(0,sig64,e-63)
    rf=sig64*2.0**(e-63)
    b=18+4*int((rf-0.25)/(4/64.0))
    six=False
    sinT=C68(SINROW[b]); cosT=C68(COSROW[b])
    a=fadd(rv,(1,b,-6),200)
    asq=fmul(a,a,64)
    rows=(172,171,170,169)
    p=C68(rows[0])
    for row in rows[1:]: p=fadd(fmul(p,asq,64),C68(row),64)
    w=fmul(fmul(p,asq,64),a,64)
    S=fadd(a,w,64)
    rows=(176,175,174,173)
    q=C68(rows[0])
    for row in rows[1:]: q=fadd(fmul(q,asq,64),C68(row),64)
    t=fmul(q,asq,64)
    if side=="s":
        m1=fmul(sinT,fadd(ONE,t,300),300); m2=fmul(cosT,S,300)
        T=fadd(m1,m2,300)
    else:
        m3=fmul(cosT,fadd(ONE,t,300),300); m4=fmul(sinT,S,300)
        T=fadd(m3,(m4[0]^1,m4[1],m4[2]),300)
    return T, b
def bdist_frac(T):
    """distance (value units) from T to the nearest RN64 boundary (midpoint),
       plus local ulp"""
    s,sig,E=T
    b=sig.bit_length()
    ulp_shift=b-64
    # midpoints at (k+1/2)*2^(E+ulp_shift): fractional part of sig/2^ulp_shift
    if ulp_shift<=0: return None,None
    frac=sig&((1<<ulp_shift)-1)
    half=1<<(ulp_shift-1)
    d=frac-half
    return d, ulp_shift, E   # distance to midpoint in units of 2^E
import random
random.seed(71)
out=[]
TARGET=60000
side_cycle=["s","c"]
attempts=0
sig=None
si=0
while len(out)<TARGET and attempts<400000:
    attempts+=1
    side=side_cycle[si%2]
    if sig is None or attempts%50==0:
        sig=(random.getrandbits(64)|1<<63)
    T,b=model_T(sig,side)
    d,us,E=bdist_frac(T)
    if d is None: continue
    # Newton hop: T moves ~ slope*dsig; slope = dT/dsig ~ cos-ish*2^(e-63)
    # target: d -> 0: dsig = -d/slope_units; slope in T-units per sig-step:
    # measure empirically with one extra eval
    T2,_=model_T(sig+1024,side)
    dT=( ((-1)**T2[0])*(T2[1]<<max(0,T2[2]-T[2])) - ((-1)**T[0])*(T[1]<<max(0,T[2]-T2[2])) )
    Ecom=min(T[2],T2[2])
    dT=(((-1)**T2[0])*(T2[1]<<(T2[2]-Ecom))) - (((-1)**T[0])*(T[1]<<(T[2]-Ecom)))
    slope=dT/1024.0
    if slope==0: sig=None; continue
    dv=d*(2.0**(E-Ecom))
    step=int(-dv/slope)
    cand=sig+step
    if not (1<<63)<=cand<(1<<64): sig=None; continue
    T3,b3=model_T(cand,side)
    d3,us3,E3=bdist_frac(T3)
    if d3 is not None and abs(d3)<= (1<<(us3-8)):   # within 2^-8 ulp of boundary
        out.append((cand,side,b3))
        si+=1
        sig=cand+random.randint(2000,50000)
    else:
        sig=None
with open(f"{SCR}/tiebreak_inputs.txt","w") as f:
    for sig64,side,b in out:
        f.write(f"3ffd {sig64:016x}\n")
with open(f"{SCR}/tiebreak_meta.txt","w") as f:
    for sig64,side,b in out:
        f.write(f"{side} {b}\n")
print(f"generated {len(out)} tiebreakers in {attempts} attempts")
