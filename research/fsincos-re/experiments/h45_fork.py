#!/usr/bin/env python3
"""Settle the fork: fit sin-path and cos-path S mechanisms INDEPENDENTLY
on the enlarged tiebreaker set; also test compensating-term shapes."""
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
SINROW={18:181,22:182,26:183,30:184,36:177,44:178,52:179,60:180}
COSROW={18:189,22:190,26:191,30:192,36:185,44:186,52:187,60:188}
ONE=(0,1,0)
S6=(162,161,160,159,158,157); C6=(168,167,166,165,164,163)
S4=(172,171,170,169); C4=(176,175,174,173)
def parts(sig64,e):
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
    rows=C6 if six else C4
    q=C68(rows[0])
    for row in rows[1:]: q=fadd(fmul(q,asq,64),C68(row),64)
    t=fmul(q,asq,64)
    return b,sinT,cosT,a,asq,p,t
def mkS(name,a,asq,p):
    if name=="base":  return fadd(a,fmul(fmul(p,asq,64),a,64),64)
    if name=="baseC": return fadd(a,fmul(fmul(p,asq,64),a,64),64,'t')
    u_rn=fadd(ONE,fmul(p,asq,64),64)
    u_ch=fadd(ONE,fmul(p,asq,64),64,'t')
    if name=="fRRn": return fmul(a,u_rn,64)
    if name=="fRCh": return fmul(a,u_rn,64,'t')
    if name=="fCRn": return fmul(a,u_ch,64)
    if name=="fCCh": return fmul(a,u_ch,64,'t')
    raise KeyError
SNAMES=("base","baseC","fRRn","fRCh","fCRn","fCCh")
inputs=[l.strip() for l in open(f"{SCR}/tb2_inputs.txt") if l.strip()]
meta=[l.split() for l in open(f"{SCR}/tb2_meta.txt") if l.strip()]
hw=[l.split() for l in open(f"{SCR}/tb2_out.txt") if l.strip()]
from collections import defaultdict
score=defaultdict(lambda:[0,0])
for l,mrow,h in zip(inputs,meta,hw):
    side,bstr,dstr,usstr,estr=mrow
    e=int(estr); sig64=int(l[5:21],16)
    b,sinT,cosT,a,asq,p,t=parts(sig64,e)
    # boundary from stored d/us relative to the base model value
    Sb=mkS("base",a,asq,p)
    if side=="s":
        m1=fmul(sinT,fadd(ONE,t,300),300); m2=fmul(cosT,Sb,300)
        Tb=fadd(m1,m2,300)
    else:
        m3=fmul(cosT,fadd(ONE,t,300),300); m4=fmul(sinT,Sb,300)
        Tb=fadd(m3,(m4[0]^1,m4[1],m4[2]),300)
    sT,gT,ET=Tb
    d=int(dstr)
    # hw side
    r64=rnP(sT,gT,ET,64)
    s_,sg_,E_=r64
    bl2=sg_.bit_length()
    if bl2<64: sg_<<=(64-bl2); E_-=(64-bl2)
    mse=(s_<<15)|(E_+63+16383)
    idx=1 if side=="s" else 3
    agree=(mse,sg_)==(int(h[idx],16),int(h[idx+1],16))
    hw_up=(d>0) if agree else (not (d>0))
    bndv=(gT-d)          # boundary significand at scale 2^ET
    for name in SNAMES:
        Sv=mkS(name,a,asq,p)
        if side=="s":
            m1=fmul(sinT,fadd(ONE,t,300),300); m2=fmul(cosT,Sv,300)
            Tv=fadd(m1,m2,300)
        else:
            m3=fmul(cosT,fadd(ONE,t,300),300); m4=fmul(sinT,Sv,300)
            Tv=fadd(m3,(m4[0]^1,m4[1],m4[2]),300)
        sV,gV,EV=Tv
        Ecom=min(ET,EV)
        pred_up=(((-1)**sV)*(gV<<(EV-Ecom))) > (((-1)**sT)*(bndv<<(ET-Ecom)))
        wide = b>=36
        k=(side,"wide" if wide else "narrow",name)
        score[k][0]+= (pred_up==hw_up); score[k][1]+=1
print(f"{'region':7s} {'side':4s} " + " ".join(f"{n:>6s}" for n in SNAMES))
for region in ("narrow","wide"):
    for side in ("s","c"):
        row=[]
        for name in SNAMES:
            c,n=score[(side,region,name)]
            row.append(f"{100.0*c/n:5.1f}%" if n else "   - ")
        n0=score[(side,region,SNAMES[0])][1]
        print(f"{region:7s} {side:4s} " + " ".join(f"{x:>6s}" for x in row) + f"   (n={n0})")
