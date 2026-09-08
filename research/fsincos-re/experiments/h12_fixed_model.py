#!/usr/bin/env python3
"""Model v2: ROM bit-error corrections + 6-term polys for wide cells."""
import random
SCR="/private/tmp/claude-501/-Users-steve-llm-coduo-binary-analysis/7d0d0788-22c7-4b55-8fbf-66cb5d3d5805/scratchpad"
def rnP(s,sig,E,P):
    b=sig.bit_length(); sh=b-P
    if sh<=0: return (s,sig,E)
    top=sig>>sh; rem=sig&((1<<sh)-1); half=1<<(sh-1)
    if rem>half or (rem==half and (top&1)):
        top+=1
        if top>>P: top>>=1; sh+=1
    return (s,top,E+sh)
def mk(P):
    def fmul(a,b):
        if a[1]==0 or b[1]==0: return (0,0,0)
        return rnP(a[0]^b[0],a[1]*b[1],a[2]+b[2],P)
    def fadd(a,b):
        if a[1]==0: return b
        if b[1]==0: return a
        E=min(a[2],b[2])
        v=((-1)**a[0])*(a[1]<<(a[2]-E))+((-1)**b[0])*(b[1]<<(b[2]-E))
        if v==0: return (0,0,0)
        return rnP(1 if v<0 else 0,abs(v),E,P)
    return fmul,fadd
def to64(v):
    if v[1]==0: return (0,0)
    s,sig,E=v
    b=sig.bit_length(); sh=b-64
    if sh>0:
        top=sig>>sh; rem=sig&((1<<sh)-1); half=1<<(sh-1)
        if rem>half or (rem==half and (top&1)):
            top+=1
            if top>>64: top>>=1; sh+=1
        sig=top; E+=sh
    else:
        sig<<=-sh; E+=sh
    return ((s<<15)|(E+63+16383),sig)
ROM={}
for line in open("/Users/steve/llm/coduo-binary-analysis/fsincos-re/data/pentium-rom/rom-constants.tsv"):
    p=line.rstrip("\n").split("\t")
    if p[0]=="row": continue
    ROM[int(p[0])]=(int(p[1],16),int(p[2]),int(p[4],16))
# corrections: single-bit transcription errors identified from silicon + article's own decimals
FIX={189: -(1<<13), 186: -(1<<44)}
for row,d in FIX.items():
    ef,s,sig=ROM[row]; ROM[row]=(ef,s,sig+d)
def C68(row):
    ef,s,sig=ROM[row]; return (s,sig,(ef-0xFFFD)-68)
GRID=[18,22,26,30,36,44,52,60]
SINROW={18:181,22:182,26:183,30:184,36:177,44:178,52:179,60:180}
COSROW={18:189,22:190,26:191,30:192,36:185,44:186,52:187,60:188}
WIDE={36,44,52,60}
ONE=(0,1,0)
inputs=[l for l in open(f"{SCR}/dense_qn.txt").read().split("\n") if l.strip()]
hw=[l for l in open(f"{SCR}/dense_rn.txt").read().split("\n") if l.strip()]
random.seed(11)
idxs=random.sample(range(len(inputs)),6000)
def run(P, wide6, narrow6, combine):
    fmul,fadd=mk(P)
    def S_poly(a, six):
        asq=fmul(a,a)
        if six:
            p=C68(162)
            for row in (161,160,159,158,157): p=fadd(fmul(p,asq),C68(row))
        else:
            p=C68(172)
            for row in (171,170,169): p=fadd(fmul(p,asq),C68(row))
        return fadd(a,fmul(fmul(p,asq),a)), asq
    def C_delta(asq, six):
        if six:
            q=C68(168)
            for row in (167,166,165,164,163): q=fadd(fmul(q,asq),C68(row))
        else:
            q=C68(176)
            for row in (175,174,173): q=fadd(fmul(q,asq),C68(row))
        return fmul(q,asq)     # C-1
    mm_p=[0,0]; n_p=0; mm_t=[0,0]; n_t=0
    for i in idxs:
        se,sig=int(inputs[i][:4],16),int(inputs[i][5:21],16)
        neg=(se>>15)&1
        e=(se&0x7FFF)-16383
        rv=(0,sig,e-63)
        rf=sig*2.0**(e-63)
        if rf>=0.7853981633974483: continue    # generator leak: skip >pi/4
        if rf<0.25:
            S,asq=S_poly(rv,True)
            t=C_delta(asq,True)
            sin=S
            cos=fadd(ONE,t)
            reg,cnt=mm_p,1; n_p+=1
        else:
            b=min(GRID,key=lambda k:abs(rf-k/64))
            six = (b in WIDE) if wide6 else False
            if not (b in WIDE): six = narrow6
            sinT=C68(SINROW[b]); cosT=C68(COSROW[b])
            a=fadd(rv,(1,b,-6))
            S,asq=S_poly(a,six)
            t=C_delta(asq,six)
            m=fmul(sinT,S); m=(m[0]^1,m[1],m[2])
            if combine==1:
                u=fadd(fmul(sinT,t),fmul(cosT,S))
                sin=fadd(sinT,u)
                v=fadd(fmul(cosT,t),m)
                cos=fadd(cosT,v)
            else:
                C4=fadd(ONE,t)
                sin=fadd(fmul(sinT,C4),fmul(cosT,S))
                cos=fadd(fmul(cosT,C4),m)
            reg=mm_t; n_t+=1
        if neg and sin[1]: sin=(sin[0]^1,sin[1],sin[2])
        hf=hw[i].split()
        if to64(sin)!=(int(hf[1],16),int(hf[2],16)): reg[0]+=1
        if to64(cos)!=(int(hf[3],16),int(hf[4],16)): reg[1]+=1
    return mm_p,n_p,mm_t,n_t
for P in (66,68,70,80):
    for wide6 in (True,False):
        for combine in (1,0):
            mp,np_,mt,nt=run(P,wide6,False,combine)
            print(f"P={P} wide6={int(wide6)} comb={combine}: poly {mp[0]}+{mp[1]}/{np_}  tab {mt[0]}+{mt[1]}/{nt}")
