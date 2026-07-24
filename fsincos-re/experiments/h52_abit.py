#!/usr/bin/env python3
"""Split the sharp-point sign field by the sub-2^-65 bit of |a|."""
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
inputs=[l.strip() for l in open(f"{SCR}/tb2_inputs.txt") if l.strip()]
meta=[l.split() for l in open(f"{SCR}/tb2_meta.txt") if l.strip()]
hw=[l.split() for l in open(f"{SCR}/tb2_out.txt") if l.strip()]
from collections import defaultdict
tab=defaultdict(lambda:[0,0])
for l,mrow,h in zip(inputs,meta,hw):
    side,bstr,dstr,usstr,estr=mrow
    if abs(int(dstr))>(1<<(int(usstr)-8)): continue
    e=int(estr); sig64=int(l[5:21],16)
    rv=(0,sig64,e-63)
    rf=sig64*2.0**(e-63)
    if rf<0.5: b=18+4*int((rf-0.25)/(4/64.0))
    else: b=36+8*min(2,int((rf-0.5)/(8/64.0)))
    six=b>=36
    sinT=C68(SINROW[b]); cosT=C68(COSROW[b])
    a=fadd(rv,(1,b,-6),200)
    # bits of |a| below the 2^-65 grid: value = a.sig * 2^(a.exp2); grid 2^-65
    s_,ga,Ea=a
    sh=Ea+65
    if sh>=0: subbits=0
    else: subbits=ga&((1<<(-sh))-1)
    frac_a=(subbits/float(1<<(-sh))) if sh<0 else 0.0
    asq=fmul(a,a,64)
    rows=S6 if six else S4
    p=C68(rows[0])
    for row in rows[1:]: p=fadd(fmul(p,asq,64),C68(row),64)
    rows=C6 if six else C4
    q=C68(rows[0])
    for row in rows[1:]: q=fadd(fmul(q,asq,64),C68(row),64)
    t=fmul(q,asq,64)
    Sb=fadd(a,fmul(fmul(p,asq,64),a,64),64)
    if side=="s":
        m1=fmul(sinT,fadd(ONE,t,300),300); m2=fmul(cosT,Sb,300)
        Tb=fadd(m1,m2,300)
        idx=1
    else:
        m3=fmul(cosT,fadd(ONE,t,300),300); m4=fmul(sinT,Sb,300)
        Tb=fadd(m3,(m4[0]^1,m4[1],m4[2]),300)
        idx=3
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
    apos = a[0]==0
    fb = 0 if frac_a==0 else (1 if frac_a<0.5 else (2 if frac_a==0.5 else 3))
    key=(side,"n" if not six else "w","a+" if apos else "a-",fb)
    tab[key][0]+= 1 if hw_up else 0
    tab[key][1]+=1
print("P(hw_up)% (n) by frac(|a|) below 2^-65 grid: bins {0, (0,.5), .5, (.5,1)}")
for side in ("s","c"):
    for reg in ("n","w"):
        for asgn in ("a-","a+"):
            row=[]
            for fb in range(4):
                c,n=tab[(side,reg,asgn,fb)]
                row.append(f"{100.0*c/n:3.0f}({n:4d})" if n else "  -(   0)")
            print(f"{side} {reg} {asgn}: "+" ".join(row))
