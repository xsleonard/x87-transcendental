#!/usr/bin/env python3
"""Tiebreaker set v2: brute-scan both outputs, window 2^-6 ulp, exact
thresholds recorded, full table region (narrow + wide cells)."""
import random, sys
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
S6=(162,161,160,159,158,157); C6=(168,167,166,165,164,163)
S4=(172,171,170,169); C4=(176,175,174,173)
def model_both(sig64, e):
    rv=(0,sig64,e-63)
    rf=sig64*2.0**(e-63)
    if rf<0.5: b=18+4*int((rf-0.25)/(4/64.0))
    else: b=36+8*min(2,int((rf-0.5)/(8/64.0)))
    six=b>=36
    sinT=C68(SINROW[b]); cosT=C68(COSROW[b])
    a=fadd(rv,(1,b,-6),200)
    asq=fmul(a,a,64)
    rows=S6 if six else S4
    p=C68(rows[0])
    for row in rows[1:]: p=fadd(fmul(p,asq,64),C68(row),64)
    w=fmul(fmul(p,asq,64),a,64)
    S=fadd(a,w,64)
    rows=C6 if six else C4
    q=C68(rows[0])
    for row in rows[1:]: q=fadd(fmul(q,asq,64),C68(row),64)
    t=fmul(q,asq,64)
    m1=fmul(sinT,fadd(ONE,t,300),300); m2=fmul(cosT,S,300)
    Ts=fadd(m1,m2,300)
    m3=fmul(cosT,fadd(ONE,t,300),300); m4=fmul(sinT,S,300)
    Tc=fadd(m3,(m4[0]^1,m4[1],m4[2]),300)
    return b,a,Ts,Tc
def bdist(T):
    s,sig,E=T
    bl=sig.bit_length(); us=bl-64
    if us<=0: return None,None
    frac=sig&((1<<us)-1); half=1<<(us-1)
    return frac-half, us     # signed distance to midpoint, ulp shift
random.seed(int(sys.argv[1]) if len(sys.argv)>1 else 101)
N=int(sys.argv[2]) if len(sys.argv)>2 else 260000
out=[]
for _ in range(N):
    e=random.choice((-2,-1))
    sig64=random.getrandbits(64)|(1<<63)
    rf=sig64*2.0**(e-63)
    if not (0.25<=rf<0.7853): continue
    b,a,Ts,Tc=model_both(sig64,e)
    for side,T in (("s",Ts),("c",Tc)):
        d,us=bdist(T)
        if d is None: continue
        if abs(d) <= (1<<(us-6)):
            out.append((sig64,e,side,b,d,us))
with open(f"{SCR}/tb2_inputs.txt","w") as f:
    for sig64,e,side,b,d,us in out:
        f.write(f"{e+16383:04x} {sig64:016x}\n")
with open(f"{SCR}/tb2_meta.txt","w") as f:
    for sig64,e,side,b,d,us in out:
        f.write(f"{side} {b} {d} {us} {e}\n")
print(f"kept {len(out)} tiebreakers from {N} scans")
