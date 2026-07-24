#!/usr/bin/env python3
"""Wide-internal-datapath variants: intermediates at P bits (P=64..68),
constants at native 68 bits, final result RN64."""
import random
SCR="/private/tmp/claude-501/-Users-steve-llm-coduo-binary-analysis/7d0d0788-22c7-4b55-8fbf-66cb5d3d5805/scratchpad"
def rnP(s, sig, E, P, mode='n'):
    """-> (s, sig2, E2): value rounded to P bits"""
    b = sig.bit_length()
    sh = b - P
    if sh <= 0:
        return (s, sig, E)
    top = sig >> sh
    rem = sig & ((1 << sh) - 1)
    if mode=='n':
        half = 1 << (sh-1)
        if rem > half or (rem == half and (top & 1)):
            top += 1
            if top >> P: top >>= 1; sh += 1
    return (s, top, E + sh)
def norm3(s, sig, E):
    return (s, sig, E)
# rep: (sign, sig_int, E) value = +-sig*2^E, arbitrary sig width (<= P after ops)
def mkP(P):
    def fmul(a, b, mode='n'):
        if a[1]==0 or b[1]==0: return (0,0,0)
        s=a[0]^b[0]; sig=a[1]*b[1]; E=a[2]+b[2]
        return rnP(s,sig,E,P,mode)
    def fadd(a, b, mode='n'):
        if a[1]==0: return b
        if b[1]==0: return a
        E=min(a[2],b[2])
        v=((-1)**a[0])*(a[1]<<(a[2]-E)) + ((-1)**b[0])*(b[1]<<(b[2]-E))
        if v==0: return (0,0,0)
        return rnP(1 if v<0 else 0, abs(v), E, P, mode)
    return fmul, fadd
def fix_rn(t, P):
    # returns (s, sig, E) with rnP applied -- rnP returns (s,E+sh,top): BUG guard
    return t
def to64(v):
    """final: round (s,sig,E) to 64-bit x87 (se,sig64)"""
    if v[1]==0: return (0,0)
    s,sig,E=v
    b=sig.bit_length(); sh=b-64
    if sh>0:
        top=sig>>sh; rem=sig&((1<<sh)-1); half=1<<(sh-1)
        if rem>half or (rem==half and (top&1)):
            top+=1
            if top>>64: top>>=1; sh+=1
        sig=top; E+=sh; b=64+ (0)
    else:
        sig<<= -sh; E+= sh
    e=E+63
    return ((s<<15)|(e+16383), sig)
ROM={}
for line in open("/Users/steve/llm/coduo-binary-analysis/fsincos-re/data/pentium-rom/rom-constants.tsv"):
    p=line.rstrip("\n").split("\t")
    if p[0]=="row": continue
    ROM[int(p[0])]=(int(p[1],16),int(p[2]),int(p[4],16))
def C68(row):
    ef,s,sig=ROM[row]
    return (s, sig, (ef-0xFFFD)-68)
GRID=[18,22,26,30,36,44,52,60]
SINROW={18:181,22:182,26:183,30:184,36:177,44:178,52:179,60:180}
COSROW={18:189,22:190,26:191,30:192,36:185,44:186,52:187,60:188}
inputs=[l for l in open(f"{SCR}/dense_qn.txt").read().split("\n") if l.strip()]
hw=[l for l in open(f"{SCR}/dense_rn.txt").read().split("\n") if l.strip()]
random.seed(9)
idxs=random.sample(range(len(inputs)),4000)
def run(P, mode, combine):
    fmul,fadd=mkP(P)
    ONE=(0,1,0)  # 1 * 2^0
    mm_poly=[0,0]; n_poly=0; mm_tab=[0,0]; n_tab=0
    for i in idxs:
        se,sig=int(inputs[i][:4],16),int(inputs[i][5:21],16)
        neg=(se>>15)&1
        e=(se&0x7FFF)-16383
        rv=(0,sig,e-63)
        rf=sig*2.0**(e-63)
        if rf<0.25:
            rsq=fmul(rv,rv,mode)
            p=C68(162)
            for row in (161,160,159,158,157):
                p=fadd(fmul(p,rsq,mode),C68(row),mode)
            rcube=fmul(rsq,rv,mode)
            sin=fadd(rv,fmul(p,rcube,mode),mode)
            q=C68(168)
            for row in (167,166,165,164,163):
                q=fadd(fmul(q,rsq,mode),C68(row),mode)
            cos=fadd(ONE,fmul(q,rsq,mode),mode)
            reg=mm_poly; n_poly+=1
        else:
            b=min(GRID,key=lambda k:abs(rf-k/64))
            sinT=C68(SINROW[b]); cosT=C68(COSROW[b])
            a=fadd(rv,(1,b,-6),mode)
            asq=fmul(a,a,mode)
            p=C68(172)
            for row in (171,170,169):
                p=fadd(fmul(p,asq,mode),C68(row),mode)
            S4=fadd(a,fmul(fmul(p,asq,mode),a,mode),mode)
            q=C68(176)
            for row in (175,174,173):
                q=fadd(fmul(q,asq,mode),C68(row),mode)
            t=fmul(q,asq,mode)
            if combine==0:
                C4=fadd(ONE,t,mode)
                sin=fadd(fmul(sinT,C4,mode),fmul(cosT,S4,mode),mode)
                m=fmul(sinT,S4,mode); m=(m[0]^1,m[1],m[2])
                cos=fadd(fmul(cosT,C4,mode),m,mode)
            else:
                u=fadd(fmul(sinT,t,mode),fmul(cosT,S4,mode),mode)
                sin=fadd(sinT,u,mode)
                m=fmul(sinT,S4,mode); m=(m[0]^1,m[1],m[2])
                v=fadd(fmul(cosT,t,mode),m,mode)
                cos=fadd(cosT,v,mode)
            reg=mm_tab; n_tab+=1
        if neg and sin[1]: sin=(sin[0]^1,sin[1],sin[2])
        hf=hw[i].split()
        if to64(sin)!=(int(hf[1],16),int(hf[2],16)): reg[0]+=1
        if to64(cos)!=(int(hf[3],16),int(hf[4],16)): reg[1]+=1
    return mm_poly,n_poly,mm_tab,n_tab
for P in (64,65,66,67,68,70):
    for mode in ('n','t'):
        for combine in (0,1):
            mp,npoly,mt,ntab=run(P,mode,combine)
            print(f"P={P} {mode} comb={combine}: poly {mp[0]}+{mp[1]}/{npoly}  tab {mt[0]}+{mt[1]}/{ntab}")
