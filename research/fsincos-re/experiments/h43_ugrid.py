#!/usr/bin/env python3
"""Score candidate mechanisms by PER-INPUT sign prediction on tiebreakers."""
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
def C68(row):
    ef,s,sig=ROM[row]; return (s,sig,(ef-0xFFFD)-68)
SINROW={18:181,22:182,26:183,30:184}; COSROW={18:189,22:190,26:191,30:192}
ONE=(0,1,0)
def parts(sig64):
    e=-2
    rv=(0,sig64,e-63)
    rf=sig64*2.0**(e-63)
    b=18+4*int((rf-0.25)/(4/64.0))
    sinT=C68(SINROW[b]); cosT=C68(COSROW[b])
    a=fadd(rv,(1,b,-6),200)
    asq=fmul(a,a,64)
    p=C68(172)
    for row in (171,170,169): p=fadd(fmul(p,asq,64),C68(row),64)
    q=C68(176)
    for row in (175,174,173): q=fadd(fmul(q,asq,64),C68(row),64)
    t=fmul(q,asq,64)
    return b,sinT,cosT,a,asq,p,q,t
def T_of(S,t,sinT,cosT,side):
    if side=="s":
        m1=fmul(sinT,fadd(ONE,t,300),300); m2=fmul(cosT,S,300)
        return fadd(m1,m2,300)
    m3=fmul(cosT,fadd(ONE,t,300),300); m4=fmul(sinT,S,300)
    return fadd(m3,(m4[0]^1,m4[1],m4[2]),300)
def S_variants(a,asq,p):
    out={}
    w=fmul(fmul(p,asq,64),a,64)
    out["base RN"]=fadd(a,w,64)
    for Pm,mm in ((64,'n'),(64,'t'),(65,'n'),(65,'t')):
        m=fmul(p,asq,Pm,mm)
        for Pu,mu in ((64,'n'),(64,'t'),(65,'t'),(66,'t')):
            u=fadd(ONE,m,Pu,mu)
            for ms in ('n','t'):
                out[f"m{Pm}{mm} u{Pu}{mu} S{ms}"]=fmul(a,u,64,ms)
    return out
inputs=[l.strip() for l in open(f"{SCR}/tiebreak_inputs.txt") if l.strip()]
meta=[l.split() for l in open(f"{SCR}/tiebreak_meta.txt") if l.strip()]
hw=[l.split() for l in open(f"{SCR}/tiebreak_out.txt") if l.strip()]
from collections import defaultdict
score=defaultdict(lambda:[0,0])
for l,(side,bstr),h in zip(inputs,meta,hw):
    sig64=int(l[5:21],16)
    b,sinT,cosT,a,asq,p,q,t=parts(sig64)
    # hw side: compare hw output to the BASE model's rounded value & boundary
    Sbase=fadd(a,fmul(fmul(p,asq,64),a,64),64)
    Tb=T_of(Sbase,t,sinT,cosT,side)
    sT,gT,ET=Tb
    bl=gT.bit_length(); us=bl-64
    frac=gT&((1<<us)-1); half=1<<(us-1)
    d=frac-half
    r64=rnP(sT,gT,ET,64)
    s_,sg_,E_=r64
    bl2=sg_.bit_length()
    if bl2<64: sg_<<=(64-bl2); E_-=(64-bl2)
    mse=(s_<<15)|(E_+63+16383)
    idx=1 if side=="s" else 3
    agree=(mse,sg_)==(int(h[idx],16),int(h[idx+1],16))
    hw_up = (d>0) if agree else (not (d>0))
    for name,Sv in S_variants(a,asq,p).items():
        Tv=T_of(Sv,t,sinT,cosT,side)
        # predicted side: Tv vs boundary of the BASE ulp cell
        sV,gV,EV=Tv
        Ecom=min(ET,EV)
        v_pred=(((-1)**sV)*(gV<<(EV-Ecom)))
        # boundary value = (gT - d)*2^ET scaled
        bnd=((gT - d))<<(ET-Ecom) if ET>=Ecom else None
        pred_up = v_pred > (((-1)**sT)*((gT-d)<<(ET-Ecom)))
        k=(name,side)
        score[k][0]+= (pred_up==hw_up); score[k][1]+=1
for k in sorted(score):
    c,n=score[k]
    print(f"{k[0]:14s} {k[1]}: predicted {c}/{n} = {100.0*c/n:.1f}%")
