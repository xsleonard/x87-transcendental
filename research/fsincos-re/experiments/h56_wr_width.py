#!/usr/bin/env python3
"""Poly region: materialization width of the correction product before the
final add; score sign-prediction on tb3 AND flips on dense."""
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
ONE=(0,1,0)
S6=(162,161,160,159,158,157); C6=(168,167,166,165,164,163)
def model(sig64,e,W,mode='n'):
    rv=(0,sig64,e-63)
    rsq=fmul(rv,rv,64)
    p=C68(S6[0])
    for row in S6[1:]: p=fadd(fmul(p,rsq,64),C68(row),64)
    w=fmul(p,rsq,64)
    wr=fmul(w,rv,W,mode)             # materialized correction @W
    Ts=fadd(rv,wr,300)
    q=C68(C6[0])
    for row in C6[1:]: q=fadd(fmul(q,rsq,64),C68(row),64)
    qr=fmul(q,rsq,W,mode)
    Tc=fadd(ONE,qr,300)
    return Ts,Tc
# sign prediction on tb3 sharp
inputs=[l.strip() for l in open(f"{SCR}/tb3_inputs.txt") if l.strip()]
meta=[l.split() for l in open(f"{SCR}/tb3_meta.txt") if l.strip()]
hw=[l.split() for l in open(f"{SCR}/tb3_out.txt") if l.strip()]
def signpred(W,mode):
    ok=n=0
    for l,mrow,h in zip(inputs,meta,hw):
        side,bstr,dstr,usstr,estr=mrow
        if abs(int(dstr))>(1<<(int(usstr)-8)): continue
        e=int(estr); sig64=int(l[5:21],16)
        Tb_s,Tb_c=model(sig64,e,300)    # wide baseline for boundary
        Tb=Tb_s if side=="s" else Tb_c
        sT,gT,ET=Tb
        blT=gT.bit_length(); usT=blT-64
        fracT=gT&((1<<usT)-1); half=1<<(usT-1)
        d=fracT-half
        r64=rnP(sT,gT,ET,64)
        s2,sg2,E2=r64
        bl2=sg2.bit_length()
        if bl2<64: sg2<<=(64-bl2); E2-=(64-bl2)
        mse=(s2<<15)|(E2+63+16383)
        idx=1 if side=="s" else 3
        agree=(mse,sg2)==(int(h[idx],16),int(h[idx+1],16))
        hw_up=(d>0) if agree else (not (d>0))
        Tv_s,Tv_c=model(sig64,e,W,mode)
        Tv=Tv_s if side=="s" else Tv_c
        sV,gV,EV=Tv
        Ecom=min(ET,EV)
        pred_up=(((-1)**sV)*(gV<<(EV-Ecom))) > (((-1)**sT)*((gT-d)<<(ET-Ecom)))
        ok+=pred_up==hw_up; n+=1
    return ok,n
# flips on dense poly subset
dense=[l for l in open(f"{SCR}/dense_qn.txt").read().split("\n") if l.strip()]
dhw=[l.split() for l in open(f"{SCR}/dense_rn.txt") if l.strip()]
import random
random.seed(91)
cand=list(range(len(dense))); random.shuffle(cand)
DS=[]
for i in cand:
    se,sig=int(dense[i][:4],16),int(dense[i][5:21],16)
    e=(se&0x7FFF)-16383
    rf=sig*2.0**(e-63)
    if 0.125<=rf<0.25: DS.append(i)
    if len(DS)>=6000: break
def flips(W,mode):
    ms=mc=0
    for i in DS:
        se,sig=int(dense[i][:4],16),int(dense[i][5:21],16)
        neg=(se>>15)&1
        e=(se&0x7FFF)-16383
        Ts,Tc=model(sig,e,W,mode)
        if neg and Ts[1]: Ts=(Ts[0]^1,Ts[1],Ts[2])
        hf=dhw[i]
        ms+=enc64(Ts)!=(int(hf[1],16),int(hf[2],16))
        mc+=enc64(Tc)!=(int(hf[3],16),int(hf[4],16))
    return ms,mc
for W,mode in ((300,'n'),(64,'n'),(65,'n'),(66,'n'),(67,'n'),(68,'n'),(66,'t'),(67,'t')):
    ok,n=signpred(W,mode)
    ms,mc=flips(W,mode)
    print(f"W={W}{mode}: signpred {ok}/{n}={100.0*ok/n:.1f}%  flips sin {ms} cos {mc} ({100.0*(ms+mc)/2/len(DS):.3f}%)")
