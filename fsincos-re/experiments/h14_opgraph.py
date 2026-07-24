#!/usr/bin/env python3
"""Op-graph search for the table-region combine, guided by Delta2 stats."""
import random
SCR="/private/tmp/claude-501/-Users-steve-llm-coduo-binary-analysis/7d0d0788-22c7-4b55-8fbf-66cb5d3d5805/scratchpad"
ROM={}
for line in open("/Users/steve/llm/coduo-binary-analysis/fsincos-re/data/pentium-rom/rom-constants.tsv"):
    p=line.rstrip("\n").split("\t")
    if p[0]=="row": continue
    ROM[int(p[0])]=(int(p[1],16),int(p[2]),int(p[4],16))
ROM[186]=(ROM[186][0],ROM[186][1],ROM[186][2]-(1<<44))   # cos(44/64) transcription typo ONLY
def rnd(s,sig,E,P,mode):
    b=sig.bit_length(); sh=b-P
    if sh<=0: return (s,sig,E)
    top=sig>>sh; rem=sig&((1<<sh)-1)
    if mode=='n':
        half=1<<(sh-1)
        if rem>half or (rem==half and (top&1)):
            top+=1
            if top>>P: top>>=1; sh+=1
    return (s,top,E+sh)
def mk(P,mode):
    def fmul(a,b):
        if a[1]==0 or b[1]==0: return (0,0,0)
        return rnd(a[0]^b[0],a[1]*b[1],a[2]+b[2],P,mode)
    def fadd(a,b):
        if a[1]==0: return b
        if b[1]==0: return a
        E=min(a[2],b[2])
        v=((-1)**a[0])*(a[1]<<(a[2]-E))+((-1)**b[0])*(b[1]<<(b[2]-E))
        if v==0: return (0,0,0)
        return rnd(1 if v<0 else 0,abs(v),E,P,mode)
    return fmul,fadd
def toN(v,N,mode='n'):
    if v[1]==0: return (0,0,0)
    return rnd(v[0],v[1],v[2],N,mode)
def enc64(v):
    if v[1]==0: return (0,0)
    s,sig,E=v
    b=sig.bit_length()
    assert b<=64 or True
    if b<64: sig<<=(64-b); E-=(64-b)
    elif b>64:
        vv=rnd(s,sig,E,64,'n'); s,sig,E=vv
        if sig.bit_length()<64: sig<<=64-sig.bit_length()
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
random.seed(13)
cand=[i for i in range(len(inputs))]
random.shuffle(cand)
SUB=[]
for i in cand:
    se,sig=int(inputs[i][:4],16),int(inputs[i][5:21],16)
    e=(se&0x7FFF)-16383
    rf=sig*2.0**(e-63)
    if 0.25<=rf<0.7853981633974483: SUB.append(i)
    if len(SUB)>=4000: break
def run(P,mode,c4mat,final2,polymode):
    fmul,fadd=mk(P,mode)
    mm=0
    for i in SUB:
        se,sig=int(inputs[i][:4],16),int(inputs[i][5:21],16)
        neg=(se>>15)&1
        e=(se&0x7FFF)-16383
        rv=(0,sig,e-63)
        rf=sig*2.0**(e-63)
        b=min(GRID,key=lambda k:abs(rf-k/64))
        six=b in WIDE
        sinT=C68(SINROW[b]); cosT=C68(COSROW[b])
        a=fadd(rv,(1,b,-6))
        asq=fmul(a,a)
        rows=(162,161,160,159,158,157) if six else (172,171,170,169)
        p=C68(rows[0])
        for row in rows[1:]: p=fadd(fmul(p,asq),C68(row))
        S=fadd(a,fmul(fmul(p,asq),a)) if polymode==0 else fadd(a,fmul(fmul(p,a),asq))
        rows=(168,167,166,165,164,163) if six else (176,175,174,173)
        q=C68(rows[0])
        for row in rows[1:]: q=fadd(fmul(q,asq),C68(row))
        t=fmul(q,asq)
        if c4mat:
            C4=fadd(ONE,t)
            m1=fmul(sinT,C4); m2=fmul(cosT,S)
            sin=fadd(m1,m2)
            m3=fmul(cosT,C4); m4=fmul(sinT,S)
            cos=fadd(m3,(m4[0]^1,m4[1],m4[2]))
        else:
            u=fadd(fmul(sinT,t),fmul(cosT,S))
            sin=fadd(sinT,u)
            m4=fmul(sinT,S)
            v=fadd(fmul(cosT,t),(m4[0]^1,m4[1],m4[2]))
            cos=fadd(cosT,v)
        if final2:
            sin=toN(sin,P,mode); cos=toN(cos,P,mode)
        if neg and sin[1]: sin=(sin[0]^1,sin[1],sin[2])
        hf=hw[i].split()
        if enc64(toN(sin,64)) != (int(hf[1],16),int(hf[2],16)): mm+=1
        if enc64(toN(cos,64)) != (int(hf[3],16),int(hf[4],16)): mm+=1
    return mm
best=[]
for P in (66,67,68,69):
    for mode in ('n','t'):
        for c4mat in (0,1):
            for polymode in (0,1):
                mm=run(P,mode,c4mat,0,polymode)
                best.append((mm,P,mode,c4mat,polymode))
best.sort()
for mm,P,mode,c4,pm in best[:10]:
    print(f"P={P} {mode} c4mat={c4} poly={pm}: {mm}/{2*len(SUB)} = {100.0*mm/2/len(SUB):.2f}%")
