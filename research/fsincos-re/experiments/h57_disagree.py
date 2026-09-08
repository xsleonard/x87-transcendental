#!/usr/bin/env python3
"""Poly-region sign field + carrier features (w-frac, q-frac, r-position)."""
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
ONE=(0,1,0)
S6=(162,161,160,159,158,157); C6=(168,167,166,165,164,163)
inputs=[l.strip() for l in open(f"{SCR}/tb3_inputs.txt") if l.strip()]
meta=[l.split() for l in open(f"{SCR}/tb3_meta.txt") if l.strip()]
hw=[l.split() for l in open(f"{SCR}/tb3_out.txt") if l.strip()]
from collections import defaultdict
byr=defaultdict(lambda:[0,0])
byw=defaultdict(lambda:[0,0])
byq=defaultdict(lambda:[0,0])
for l,mrow,h in zip(inputs,meta,hw):
    side,bstr,dstr,usstr,estr=mrow
    if abs(int(dstr))>(1<<(int(usstr)-8)): continue
    e=int(estr); sig64=int(l[5:21],16)
    rv=(0,sig64,e-63)
    rf=sig64*2.0**(e-63)
    rsq=fmul(rv,rv,64)
    p=C68(S6[0])
    for row in S6[1:]: p=fadd(fmul(p,rsq,64),C68(row),64)
    q=C68(C6[0])
    for row in C6[1:]: q=fadd(fmul(q,rsq,64),C68(row),64)
    if side=="s":
        w=fmul(p,rsq,64)
        Tb=fadd(rv,fmul(w,rv,300),300)
        # feature: frac of w*r product (the value fused into the final)
        wr=fmul(w,rv,300)
        sX,gX,EX=wr
        idx=1
    else:
        Tb=fadd(ONE,fmul(q,rsq,300),300)
        qr=fmul(q,rsq,300)
        sX,gX,EX=qr
        idx=3
    blX=gX.bit_length(); usX=blX-64
    frX=(gX&((1<<usX)-1))/float(1<<usX) if usX>0 else 0.0
    sT,gT,ET=Tb
    blT=gT.bit_length(); usT=blT-64
    fracT=gT&((1<<usT)-1); half=1<<(usT-1)
    d=fracT-half
    r64=rnP(sT,gT,ET,64)
    s2,sg2,E2=r64
    bl2=sg2.bit_length()
    if bl2<64: sg2<<=(64-bl2); E2-=(64-bl2)
    mse=(s2<<15)|(E2+63+16383)
    agree=(mse,sg2)==(int(h[idx],16),int(h[idx+1],16))
    hw_up=(d>0) if agree else (not (d>0))
    rb=min(7,int((rf-0.125)/(0.125/8)))
    byr[(side,rb)][0]+=hw_up; byr[(side,rb)][1]+=1
    fb=min(7,int(frX*8))
    disagree = (hw_up != (d>0))
    byw[(side,fb)][0]+=disagree; byw[(side,fb)][1]+=1
print("P(hw_up)% (n) vs r-bin [0.125..0.25, 8 bins]:")
for side in ("s","c"):
    row=[]
    for rb in range(8):
        c,n=byr[(side,rb)]
        row.append(f"{100.0*c/n:3.0f}({n:3d})" if n else "  -")
    print(f"  {side}: "+" ".join(row))
print("P(hw DISAGREES with wide model)% (n) vs frac(correction-term) [8 bins]:")
for side in ("s","c"):
    row=[]
    for fb in range(8):
        c,n=byw[(side,fb)]
        row.append(f"{100.0*c/n:3.0f}({n:3d})" if n else "  -")
    print(f"  {side}: "+" ".join(row))
