#!/usr/bin/env python3
"""Survivor-Delta forensics: definite hw-minus-model deviations vs a."""
from collections import defaultdict
SCR="/private/tmp/claude-501/-Users-steve-llm-coduo-binary-analysis/7d0d0788-22c7-4b55-8fbf-66cb5d3d5805/scratchpad"
ROM={}
for line in open("/Users/steve/llm/coduo-binary-analysis/fsincos-re/data/pentium-rom/rom-constants.tsv"):
    p=line.rstrip("\n").split("\t")
    if p[0]=="row": continue
    ROM[int(p[0])]=(int(p[1],16),int(p[2]),int(p[4],16))
ROM[186]=(ROM[186][0],ROM[186][1],ROM[186][2]-(1<<43))
ROM[189]=(ROM[189][0],ROM[189][1],ROM[189][2]-(1<<12))
def rnP(s,sig,E,P):
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
def C68(row):
    ef,s,sig=ROM[row]; return (s,sig,(ef-0xFFFD)-68)
SINROW={18:181,22:182,26:183,30:184,36:177,44:178,52:179,60:180}
COSROW={18:189,22:190,26:191,30:192,36:185,44:186,52:187,60:188}
ONE=(0,1,0)
def sval(v):  # tuple -> signed int at exp scale: return (int, E)
    return (((-1)**v[0])*v[1], v[2])
inputs=[l for l in open(f"{SCR}/dense_qn.txt").read().split("\n") if l.strip()]
hw_rn=[l for l in open(f"{SCR}/dense_rn.txt").read().split("\n") if l.strip()]
hw_rd=[l for l in open(f"{SCR}/dense_rd.txt").read().split("\n") if l.strip()]
# per (cell, side): a-bin -> [n_defplus, n_defminus, sum_boundmag(2^-72), n]
BINS=4
stats=defaultdict(lambda: [[0,0,0.0,0] for _ in range(BINS)])
CL={18:(16,20),22:(20,24),26:(24,28),30:(28,32),36:(32,40),44:(40,48),52:(48,56)}
nproc=0
for li,l in enumerate(inputs):
    se,sig=int(l[:4],16),int(l[5:21],16)
    e=(se&0x7FFF)-16383
    rf=sig*2.0**(e-63)
    if not (0.25<=rf<0.7853981633974483): continue
    nproc+=1
    neg=(se>>15)&1
    rv=(0,sig,e-63)
    if rf<0.5: b=18+4*int((rf-0.25)/(4/64.0))
    else: b=36+8*min(2,int((rf-0.5)/(8/64.0)))
    six=b>=36
    sinT=C68(SINROW[b]); cosT=C68(COSROW[b])
    a=fadd(rv,(1,b,-6),100)
    af=((-1)**a[0])*a[1]*2.0**a[2] if a[1] else 0.0
    asq=fmul(a,a,64)
    rows=(162,161,160,159,158,157) if six else (172,171,170,169)
    p=C68(rows[0])
    for row in rows[1:]: p=fadd(fmul(p,asq,64),C68(row),64)
    S=fadd(a,fmul(fmul(p,asq,64),a,64),64)
    rows=(168,167,166,165,164,163) if six else (176,175,174,173)
    q=C68(rows[0])
    for row in rows[1:]: q=fadd(fmul(q,asq,64),C68(row),64)
    t=fmul(q,asq,64)
    m1=fmul(sinT,fadd(ONE,t,300),300); m2=fmul(cosT,S,300)
    Tsin=fadd(m1,m2,300)
    m3=fmul(cosT,fadd(ONE,t,300),300); m4=fmul(sinT,S,300)
    Tcos=fadd(m3,(m4[0]^1,m4[1],m4[2]),300)
    if neg and Tsin[1]: Tsin=(Tsin[0]^1,Tsin[1],Tsin[2])
    rnf=hw_rn[li].split(); rdf=hw_rd[li].split()
    lo_c,hi_c=CL[b]
    frac=(rf-lo_c/64.0)/((hi_c-lo_c)/64.0)
    ab=min(BINS-1,int(frac*BINS))
    for tag,Tm,idx in (("s",Tsin,1),("c",Tcos,3)):
        hse,hsg=int(rnf[idx],16),int(rnf[idx+1],16)
        dse,dsg=int(rdf[idx],16),int(rdf[idx+1],16)
        # values as scaled ints at common scale
        def dec2(se_,sg_):
            s_=-1 if se_>>15 else 1
            return (s_*sg_, ((se_&0x7FFF)-16383)-63)
        hn,hne=dec2(hse,hsg); hd,hde=dec2(dse,dsg)
        ulpe=(hse&0x7FFF)-16383-63
        # common scale for interval arithmetic: use E=min of everything
        Tm_v,Tm_e=sval(Tm)
        E=min(hne,hde,ulpe,Tm_e)
        hnv=hn<<(hne-E); hdv=hd<<(hde-E); u=1<<(ulpe-E)
        Tv=Tm_v<<(Tm_e-E)
        if hnv>=0: lo1,hi1=hdv,hdv+u
        else: lo1,hi1=hdv-u,hdv
        lo2,hi2=2*hnv-u,2*hnv+u    # 2x scale for RN halves
        lo=max(2*lo1,lo2); hi=min(2*hi1,hi2)
        # Delta interval (2x scale): [lo-2Tv, hi-2Tv]
        dlo=lo-2*Tv; dhi=hi-2*Tv
        st=stats[(b,tag,neg)][ab]
        st[3]+=1
        if dlo>0:   # definitely hw > model
            st[0]+=1; st[2]+=float(dlo)*2.0**(E-1)*2**72
        elif dhi<0:
            st[1]+=1; st[2]+=float(-dhi)*2.0**(E-1)*2**72
print(f"processed {nproc} inputs")
for key in sorted(stats):
    b,tag,neg=key
    print(f"--- cell {b}/64 side {tag} xsign={'-' if neg else '+'} ---")
    for ab in range(BINS):
        pl,mi,mag,n=stats[key][ab]
        if n==0: continue
        net=pl-mi
        avg=mag/max(1,pl+mi)
        print(f"  bin{ab:2d} n={n:5d} def+={pl:4d} def-={mi:4d} net={net:+5d} avg|bound|~{avg:.1f}*2^-72")
