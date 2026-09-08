#!/usr/bin/env python3
"""Reduced-argument handling: first-order c-injection vs TRUE wide-a,
tested on the leaked >pi/4 dense inputs (N=1 reduction, c != 0)."""
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
def fmul(a,b,P=64):
    if a[1]==0 or b[1]==0: return (0,0,0)
    return rnd(a[0]^b[0],a[1]*b[1],a[2]+b[2],P)
def fadd(a,b,P=64):
    if a[1]==0: return b
    if b[1]==0: return a
    E=min(a[2],b[2])
    v=((-1)**a[0])*(a[1]<<(a[2]-E))+((-1)**b[0])*(b[1]<<(b[2]-E))
    if v==0: return (0,0,0)
    return rnd(1 if v<0 else 0,abs(v),E,P)
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
M66=(0x3<<64)|0x243F6A8885A308D3    # pi/2 trunc 66, scale 2^-65
inputs=[l for l in open(f"{SCR}/dense_qn.txt").read().split("\n") if l.strip()]
hw=[l.split() for l in open(f"{SCR}/dense_rn.txt") if l.strip()]
S6=[157,158,159,160,161,162]; C6=[163,164,165,166,167,168]
S4=[169,170,171,172]; C4=[173,174,175,176]
def kernel(sin_out, a, i0flip, mode):
    """a = (sign, sig, E) possibly wide (up to 66-bit sig). mode: kernel path."""
    pass
def run(WIDE):
    ms=mc=0; n=0
    for li,l in enumerate(inputs):
        se,sig=int(l[:4],16),int(l[5:21],16)
        e=(se&0x7FFF)-16383
        rf=sig*2.0**(e-63)
        if rf<0.7853981633974483: continue
        n+=1
        neg=(se>>15)&1
        # reduce: N=1 (x in [0.785,1)): d = x*2^65 - M66  (exact, scale 2^-65)
        xi=sig<<(e+2)     # x*2^65 as int (e=-1 -> sig<<1)
        d=xi-M66
        dneg=1 if d<0 else 0
        da=abs(d)
        # quadrant: sin(x)=cos(r), cos(x)=-sin(r) with r=x-pi/2, N=1
        if WIDE:
            a_r=(dneg,da,-65)         # wide r (up to ~62 bits here)
            c=(0,0,0)
        else:
            rr=rnd(dneg,da,-65,64)
            # c = residual
            rv=((-1)**rr[0])*(rr[1]<<max(0,(rr[2]+65)))
            ci=d-rv if rr[2]==-65 else d-(((-1)**rr[0])*rr[1]*(2**(rr[2]+65)))
            ci=int(ci)
            c=(1 if ci<0 else 0,abs(ci),-65) if ci else (0,0,0)
            a_r=rr
        # |r| here ~ [0.215, 0.785-pi/2+...]: r = x-pi/2 in [-0.785, -0.57]: |r| in [0.57,0.785]?? 
        # x in [0.89,1.0): r=x-1.5708 in [-0.68,-0.57]: |r| in [0.57,0.68] -> table region
        rf2=abs(((-1)**a_r[0])*a_r[1]*2.0**a_r[2])
        b=36+8*min(2,int((rf2-0.5)/(8/64.0))) if rf2>=0.5 else 18+4*int((rf2-0.25)/(4/64.0))
        six=b>=36
        sinT=C68(SINROW[b]); cosT=C68(COSROW[b])
        aa=(a_r[0]^0, a_r[1], a_r[2])
        # a = |r| - b exactly (both scale-compatible ints)
        E=min(a_r[2],-6)
        av=(a_r[1]<<(a_r[2]-E))-(b<<(-6-E))
        a=(1 if av<0 else 0,abs(av),E) if av else (0,0,0)
        asq=fmul(a,a,64)
        rows=tuple(reversed(S6)) if six else tuple(reversed(S4))
        p=C68(rows[0])
        for row in rows[1:]: p=fadd(fmul(p,asq,64),C68(row),64)
        w=fmul(fmul(p,asq,64),a,64)
        S=fadd(a,w,64)
        rows=tuple(reversed(C6)) if six else tuple(reversed(C4))
        q=C68(rows[0])
        for row in rows[1:]: q=fadd(fmul(q,asq,64),C68(row),64)
        t=fmul(q,asq,64)
        # c-injection for non-wide (first-order)
        if not WIDE and c[1]:
            ce=(c[0]^dneg^dneg, c[1], c[2])  # c in |r| frame: |r+c| = |r|+sign(r)c
            ce=(c[0]^a_r[0], c[1], c[2])
        else:
            ce=(0,0,0)
        # kernel sin(|r|) and cos(|r|)
        m1=fmul(sinT,fadd(ONE,t,200),200); m2=fmul(cosT,S,200)
        ksin=fadd(m1,m2,200)
        if ce[1]: ksin=fadd(ksin,fmul(cosT,ce,200),200)
        m3=fmul(cosT,fadd(ONE,t,200),200); m4=fmul(sinT,S,200)
        kcos=fadd(m3,(m4[0]^1,m4[1],m4[2]),200)
        if ce[1]: kcos=fadd(kcos,(lambda z:(z[0]^1,z[1],z[2]))(fmul(sinT,ce,200)),200)
        # map quadrant: r<0 (dneg=1): sin(x)=cos(r)=cos(|r|)=kcos; cos(x)=-sin(r)=sin(|r|)=ksin
        # for x>0 leak inputs: N=1: sin(x)=cos(r), cos(x)=-sin(r); r<0 so cos(r)=cos|r|, -sin(r)=sin|r|
        sinx=kcos
        cosx=ksin
        if neg and sinx[1]: sinx=(sinx[0]^1,sinx[1],sinx[2])   # sin odd; cos even
        hf=hw[li]
        ms+=enc64(sinx)!=(int(hf[1],16),int(hf[2],16))
        mc+=enc64(cosx)!=(int(hf[3],16),int(hf[4],16))
    return ms,mc,n
for WIDE in (0,1):
    ms,mc,n=run(WIDE)
    print(f"WIDE={WIDE}: sin {ms}/{n}={100.0*ms/n:.3f}%  cos {mc}/{n}={100.0*mc/n:.3f}%")
