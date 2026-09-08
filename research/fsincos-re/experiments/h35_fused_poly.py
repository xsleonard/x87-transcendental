#!/usr/bin/env python3
"""Poly region: fused finals for sin and cos x Horner precision grid."""
SCR="/private/tmp/claude-501/-Users-steve-llm-coduo-binary-analysis/7d0d0788-22c7-4b55-8fbf-66cb5d3d5805/scratchpad"
ROM={}
for line in open("/Users/steve/llm/coduo-binary-analysis/fsincos-re/data/pentium-rom/rom-constants.tsv"):
    p=line.rstrip("\n").split("\t")
    if p[0]=="row": continue
    ROM[int(p[0])]=(int(p[1],16),int(p[2]),int(p[4],16))
def rnP(s,sig,E,P=64):
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
S6=[157,158,159,160,161,162]; C6=[163,164,165,166,167,168]
inputs=[l for l in open(f"{SCR}/dense_qn.txt").read().split("\n") if l.strip()]
sc=[l.split() for l in open(f"{SCR}/dense_rn.txt") if l.strip()]
SUB=[i for i,l in enumerate(inputs)
     if 0.125<= int(l[5:21],16)*2.0**(((int(l[:4],16))&0x7FFF)-16383-63) <0.25]
def run(HP, fuse_sin, fuse_cos, mulstage):
    ms=mc=0
    for i in SUB:
        l=inputs[i]
        se,sig=int(l[:4],16),int(l[5:21],16)
        neg=(se>>15)&1
        r=(0,sig,((se&0x7FFF)-16383)-63)
        rsq=fmul(r,r)
        p=C68(S6[5])
        for row in (S6[4],S6[3],S6[2],S6[1],S6[0]): p=fadd(fmul(p,rsq,HP),C68(row),HP)
        if fuse_sin==0:
            sin=fadd(r,fmul(fmul(p,rsq),r))
        elif fuse_sin==1:              # r + exact(p*rsq*r) single rounding
            w=fmul(fmul(p,rsq,mulstage),r,200)
            sin=fadd(r,w,200)
        else:                          # r + (RN64(p*rsq))*r fused final
            w=fmul(p,rsq)
            sin=fadd(r,fmul(w,r,200),200)
        q=C68(C6[5])
        for row in (C6[4],C6[3],C6[2],C6[1],C6[0]): q=fadd(fmul(q,rsq,HP),C68(row),HP)
        if fuse_cos==0:
            cos=fadd(ONE,fmul(q,rsq))
        else:
            cos=fadd(ONE,fmul(q,rsq,200),200)
        if neg and sin[1]: sin=(sin[0]^1,sin[1],sin[2])
        hs=(int(sc[i][1],16),int(sc[i][2],16)); hc=(int(sc[i][3],16),int(sc[i][4],16))
        ms+=enc64(sin)!=hs; mc+=enc64(cos)!=hc
    return ms,mc
n=len(SUB)
for HP in (64,66,68):
    for fs in (0,1,2):
        for fc_ in (0,1):
            for mst in ((200,) if fs==1 else (64,)):
                ms,mc=run(HP,fs,fc_,mst)
                print(f"HP={HP} fuse_sin={fs} fuse_cos={fc_}: sin {ms}/{n}={100.0*ms/n:.3f}%  cos {mc}/{n}={100.0*mc/n:.3f}%")
