#!/usr/bin/env python3
"""Truncated (chopped) materialization of S and t (and optionally the whole
poly chain) instead of RN64."""
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
def fmul(a,b,P=64,m='n'):
    if a[1]==0 or b[1]==0: return (0,0,0)
    return rnd(a[0]^b[0],a[1]*b[1],a[2]+b[2],P,m)
def fadd(a,b,P=64,m='n'):
    if a[1]==0: return b
    if b[1]==0: return a
    E=min(a[2],b[2])
    v=((-1)**a[0])*(a[1]<<(a[2]-E))+((-1)**b[0])*(b[1]<<(b[2]-E))
    if v==0: return (0,0,0)
    return rnd(1 if v<0 else 0,abs(v),E,P,m)
def enc64(v):
    if v[1]==0: return (0,0)
    v=rnd(v[0],v[1],v[2],64)
    s,sig,E=v
    b=sig.bit_length()
    if b<64: sig<<=(64-b); E-=(64-b)
    return ((s<<15)|(E+63+16383),sig)
def C68(row):
    ef,s,sig=ROM[row]; return (s,sig,(ef-0xFFFD)-68)
SINROW={18:181,22:182,26:183,30:184,36:177,44:178,52:179,60:180}
COSROW={18:189,22:190,26:191,30:192,36:185,44:186,52:187,60:188}
ONE=(0,1,0)
inputs=[l for l in open(f"{SCR}/dense_qn.txt").read().split("\n") if l.strip()]
hw=[l for l in open(f"{SCR}/dense_rn.txt").read().split("\n") if l.strip()]
random.seed(51)
cand=list(range(len(inputs))); random.shuffle(cand)
SUB=[]
for i in cand:
    se,sig=int(inputs[i][:4],16),int(inputs[i][5:21],16)
    e=(se&0x7FFF)-16383
    rf=sig*2.0**(e-63)
    if 0.25<=rf<0.7853981633974483: SUB.append(i)
    if len(SUB)>=6000: break
def run(mST, mHorner, mAsq):
    mm=0
    for i in SUB:
        se,sig=int(inputs[i][:4],16),int(inputs[i][5:21],16)
        neg=(se>>15)&1
        e=(se&0x7FFF)-16383
        rv=(0,sig,e-63)
        rf=sig*2.0**(e-63)
        if rf<0.5: b=18+4*int((rf-0.25)/(4/64.0))
        else: b=36+8*min(2,int((rf-0.5)/(8/64.0)))
        six=b>=36
        sinT=C68(SINROW[b]); cosT=C68(COSROW[b])
        a=fadd(rv,(1,b,-6),100)
        asq=fmul(a,a,64,mAsq)
        rows=(162,161,160,159,158,157) if six else (172,171,170,169)
        p=C68(rows[0])
        for row in rows[1:]: p=fadd(fmul(p,asq,64,mHorner),C68(row),64,mHorner)
        if SFUSE==0:
            S=fadd(a,fmul(fmul(p,asq,64,'n'),a,64,'n'),64,'n')
        elif SFUSE==1:   # fused: a + w*a single rounding, w=RN64(p*asq)
            w=fmul(p,asq,64,'n')
            S=fadd(a,fmul(w,a,200,'n'),64,'n')
        else:            # fully fused a + p*asq*a
            S=fadd(a,fmul(fmul(p,asq,200,'n'),a,200,'n'),64,'n')
        rows=(168,167,166,165,164,163) if six else (176,175,174,173)
        q=C68(rows[0])
        for row in rows[1:]: q=fadd(fmul(q,asq,64,mHorner),C68(row),64,mHorner)
        t=fmul(q,asq,64,'n')
        m1=fmul(sinT,fadd(ONE,t,100),100); m2=fmul(cosT,S,100)
        sin=fadd(m1,m2,100)
        m3=fmul(cosT,fadd(ONE,t,100),100); m4=fmul(sinT,S,100)
        cos=fadd(m3,(m4[0]^1,m4[1],m4[2]),100)
        if neg and sin[1]: sin=(sin[0]^1,sin[1],sin[2])
        hf=hw[i].split()
        if enc64(sin)!=(int(hf[1],16),int(hf[2],16)): mm+=1
        if enc64(cos)!=(int(hf[3],16),int(hf[4],16)): mm+=1
    return mm
SFUSE=0
for sf in (0,1,2):
    globals()['SFUSE']=sf
    mm=run('n','n','n')
    print(f"table region S-fuse={sf}: {mm}/{2*len(SUB)} = {100.0*mm/2/len(SUB):.3f}%")
