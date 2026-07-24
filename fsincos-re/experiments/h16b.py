#!/usr/bin/env python3
"""Mixed-precision graphs: wide poly, selective 64-bit writebacks, fused or
per-op combine."""
import random
SCR="/private/tmp/claude-501/-Users-steve-llm-coduo-binary-analysis/7d0d0788-22c7-4b55-8fbf-66cb5d3d5805/scratchpad"
ROM={}
for line in open("/Users/steve/llm/coduo-binary-analysis/fsincos-re/data/pentium-rom/rom-constants.tsv"):
    p=line.rstrip("\n").split("\t")
    if p[0]=="row": continue
    ROM[int(p[0])]=(int(p[1],16),int(p[2]),int(p[4],16))
ROM[186]=(ROM[186][0],ROM[186][1],ROM[186][2]-(1<<43))
ROM[189]=(ROM[189][0],ROM[189][1],ROM[189][2]-(1<<12))
def rnd(s,sig,E,P,mode='n'):
    b=sig.bit_length(); sh=b-P
    if sh<=0: return (s,sig,E)
    top=sig>>sh; rem=sig&((1<<sh)-1)
    if mode=='n':
        half=1<<(sh-1)
        if rem>half or (rem==half and (top&1)):
            top+=1
            if top>>P: top>>=1; sh+=1
    return (s,top,E+sh)
def fmulP(a,b,P,mode='n'):
    if a[1]==0 or b[1]==0: return (0,0,0)
    return rnd(a[0]^b[0],a[1]*b[1],a[2]+b[2],P,mode)
def faddP(a,b,P,mode='n'):
    if a[1]==0: return b
    if b[1]==0: return a
    E=min(a[2],b[2])
    v=((-1)**a[0])*(a[1]<<(a[2]-E))+((-1)**b[0])*(b[1]<<(b[2]-E))
    if v==0: return (0,0,0)
    return rnd(1 if v<0 else 0,abs(v),E,P,mode)
def enc64(v):
    if v[1]==0: return (0,0)
    v=rnd(v[0],v[1],v[2],64)
    s,sig,E=v
    b=sig.bit_length()
    if b<64: sig<<=(64-b); E-=(64-b)
    return ((s<<15)|(E+63+16383),sig)
def C68(row):
    ef,s,sig=ROM[row]; return (s,sig,(ef-0xFFFD)-68)
GRID=[18,22,26,30,36,44,52,60]
SINROW={18:181,22:182,26:183,30:184,36:177,44:178,52:179,60:180}
COSROW={18:189,22:190,26:191,30:192,36:185,44:186,52:187,60:188}
WIDE={36,44,52,60}
ONE=(0,1,0)
inputs=[l for l in open(f"{SCR}/dense_qn.txt").read().split("\n") if l.strip()]
hw=[l for l in open(f"{SCR}/dense_rn.txt").read().split("\n") if l.strip()]
random.seed(17)
cand=list(range(len(inputs))); random.shuffle(cand)
SUB=[]
for i in cand:
    se,sig=int(inputs[i][:4],16),int(inputs[i][5:21],16)
    e=(se&0x7FFF)-16383
    rf=sig*2.0**(e-63)
    if 0.25<=rf<0.7853981633974483: SUB.append(i)
    if len(SUB)>=3000: break
WIDEP=100
def graph(i, polyP, wbST, combP, finaldirect):
    se,sig=int(inputs[i][:4],16),int(inputs[i][5:21],16)
    neg=(se>>15)&1
    e=(se&0x7FFF)-16383
    rv=(0,sig,e-63)
    rf=sig*2.0**(e-63)
    if rf<0.5: b=18+4*int((rf-0.25)/(4/64.0))
    else: b=36+8*min(2,int((rf-0.5)/(8/64.0)))
    six=b in WIDE
    sinT=C68(SINROW[b]); cosT=C68(COSROW[b])
    a=faddP(rv,(1,b,-6),polyP)
    asq=fmulP(a,a,polyP)
    rows=(162,161,160,159,158,157) if six else (172,171,170,169)
    p=C68(rows[0])
    for row in rows[1:]: p=faddP(fmulP(p,asq,polyP),C68(row),polyP)
    S=faddP(a,fmulP(fmulP(p,asq,polyP),a,polyP),polyP)
    rows=(168,167,166,165,164,163) if six else (176,175,174,173)
    q=C68(rows[0])
    for row in rows[1:]: q=faddP(fmulP(q,asq,polyP),C68(row),polyP)
    t=fmulP(q,asq,polyP)
    if wbST:
        S=rnd(S[0],S[1],S[2],64); t=rnd(t[0],t[1],t[2],64)
    m1=fmulP(sinT,faddP(ONE,t,combP),combP); m2=fmulP(cosT,S,combP)
    sin=faddP(m1,m2,combP)
    m3=fmulP(cosT,faddP(ONE,t,combP),combP); m4=fmulP(sinT,S,combP)
    cos=faddP(m3,(m4[0]^1,m4[1],m4[2]),combP)
    if neg and sin[1]: sin=(sin[0]^1,sin[1],sin[2])
    hf=hw[i].split()
    ok=(enc64(sin)==(int(hf[1],16),int(hf[2],16))) + (enc64(cos)==(int(hf[3],16),int(hf[4],16)))
    return 2-ok
res=[]
for polyP in (64,67,WIDEP):
    for wbST in (0,1):
        for combP in (64,67,WIDEP):
            mm=sum(graph(i,polyP,wbST,combP,0) for i in SUB)
            res.append((mm,polyP,wbST,combP))
res.sort()
for mm,pp,wb,cp in res:
    print(f"polyP={pp} wbST={wb} combP={cp}: {mm}/{2*len(SUB)} = {100.0*mm/2/len(SUB):.2f}%")
