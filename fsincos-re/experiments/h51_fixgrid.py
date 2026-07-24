#!/usr/bin/env python3
"""S truncated toward zero on a FIXED absolute grid 2^-G: sign-prediction
and flip scoring."""
import random
SCR="/private/tmp/claude-501/-Users-steve-llm-coduo-binary-analysis/7d0d0788-22c7-4b55-8fbf-66cb5d3d5805/scratchpad"
ROM={}
for line in open("/Users/steve/llm/coduo-binary-analysis/fsincos-re/data/pentium-rom/rom-constants.tsv"):
    p=line.rstrip("\n").split("\t")
    if p[0]=="row": continue
    ROM[int(p[0])]=(int(p[1],16),int(p[2]),int(p[4],16))
ROM[186]=(ROM[186][0],ROM[186][1],ROM[186][2]-(1<<43))
ROM[189]=(ROM[189][0],ROM[189][1],ROM[189][2]-(1<<12))
def rnP(s,sig,E,P,mode='n'):
    b=sig.bit_length(); sh=b-P
    if sh<=0: return (s,sig,E)
    top=sig>>sh; rem=sig&((1<<sh)-1)
    if mode=='n':
        half=1<<(sh-1)
        if rem>half or (rem==half and (top&1)):
            top+=1
            if top>>P: top>>=1; sh+=1
    return (s,top,E+sh)
def fmul(a,b,P=64,m='n'):
    if a[1]==0 or b[1]==0: return (0,0,0)
    return rnP(a[0]^b[0],a[1]*b[1],a[2]+b[2],P,m)
def fadd(a,b,P=64,m='n'):
    if a[1]==0: return b
    if b[1]==0: return a
    E=min(a[2],b[2])
    v=((-1)**a[0])*(a[1]<<(a[2]-E))+((-1)**b[0])*(b[1]<<(b[2]-E))
    if v==0: return (0,0,0)
    return rnP(1 if v<0 else 0,abs(v),E,P,m)
def enc64(v):
    if v[1]==0: return (0,0)
    v=rnP(v[0],v[1],v[2],64)
    s,sig,E=v
    b=sig.bit_length()
    if b<64: sig<<=(64-b); E-=(64-b)
    return ((s<<15)|(E+63+16383),sig)
def C68(row):
    ef,s,sig=ROM[row]; return (s,sig,(ef-0xFFFD)-68)
SINROW={18:181,22:182,26:183,30:184,36:177,44:178,52:179,60:180}
COSROW={18:189,22:190,26:191,30:192,36:185,44:186,52:187,60:188}
ONE=(0,1,0)
S6=(162,161,160,159,158,157); C6=(168,167,166,165,164,163)
S4=(172,171,170,169); C4=(176,175,174,173)
def fixtrunc(v,G):
    """truncate value toward zero on grid 2^-G"""
    if v[1]==0: return v
    s,sig,E=v
    sh=E+G
    if sh>=0: return v            # already coarser than grid (exact)
    kept=sig>>(-sh)
    if kept==0: return (0,0,0)
    return (s,kept,-G)
def model(sig64,e,SG,TG):
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
    S=fadd(a,fmul(fmul(p,asq,64),a,64),64)
    if SG: S=fixtrunc(S,SG)
    rows=C6 if six else C4
    q=C68(rows[0])
    for row in rows[1:]: q=fadd(fmul(q,asq,64),C68(row),64)
    t=fmul(q,asq,64)
    if TG: t=fixtrunc(t,TG)
    m1=fmul(sinT,fadd(ONE,t,300),300); m2=fmul(cosT,S,300)
    Ts=fadd(m1,m2,300)
    m3=fmul(cosT,fadd(ONE,t,300),300); m4=fmul(sinT,S,300)
    Tc=fadd(m3,(m4[0]^1,m4[1],m4[2]),300)
    return Ts,Tc
# flip scoring on dense subset
inputs=[l for l in open(f"{SCR}/dense_qn.txt").read().split("\n") if l.strip()]
hw=[l.split() for l in open(f"{SCR}/dense_rn.txt") if l.strip()]
random.seed(81)
cand=list(range(len(inputs))); random.shuffle(cand)
SUB=[]
for i in cand:
    se,sig=int(inputs[i][:4],16),int(inputs[i][5:21],16)
    e=(se&0x7FFF)-16383
    rf=sig*2.0**(e-63)
    if 0.25<=rf<0.7853: SUB.append(i)
    if len(SUB)>=6000: break
for SG in (0,64,65,66,67):
    for TG in (0,):
        ms=mc=0
        for i in SUB:
            se,sig=int(inputs[i][:4],16),int(inputs[i][5:21],16)
            neg=(se>>15)&1
            e=(se&0x7FFF)-16383
            Ts,Tc=model(sig,e,SG,TG)
            if neg and Ts[1]: Ts=(Ts[0]^1,Ts[1],Ts[2])
            hf=hw[i]
            ms+=enc64(Ts)!=(int(hf[1],16),int(hf[2],16))
            mc+=enc64(Tc)!=(int(hf[3],16),int(hf[4],16))
        print(f"S-fixgrid 2^-{SG if SG else '  (none)'}: sin {ms} cos {mc} tot {ms+mc}/{2*len(SUB)} = {100.0*(ms+mc)/2/len(SUB):.3f}%")
