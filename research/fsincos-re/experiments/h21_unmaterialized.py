#!/usr/bin/env python3
"""Test selective non-materialization: S and/or t consumed WIDE by the fused
combine (no 64-bit writeback); also fused Horner steps and wide asq."""
import random
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
def enc64(v):
    if v[1]==0: return (0,0)
    v=rnP(v[0],v[1],v[2],64)
    s,sig,E=v
    b=sig.bit_length()
    if b<64: sig<<=(64-b); E-=(64-b)
    return ((s<<15)|(E+63+16383),sig)
def C68(row):
    ef,s,sig=ROM[row]; return (s,sig,(ef-0xFFFD)-68)
SINROW={18:181,22:182,26:183,30:184,36:177,44:178,52:179,60:180}
COSROW={18:189,22:190,26:191,30:192,36:185,44:186,52:187,60:188}
ONE=(0,1,0)
inputs=[l for l in open(f"{SCR}/dense_qn.txt").read().split("\n") if l.strip()]
hw=[l for l in open(f"{SCR}/dense_rn.txt").read().split("\n") if l.strip()]
random.seed(31)
cand=list(range(len(inputs))); random.shuffle(cand)
SUB=[]
for i in cand:
    se,sig=int(inputs[i][:4],16),int(inputs[i][5:21],16)
    e=(se&0x7FFF)-16383
    rf=sig*2.0**(e-63)
    if 0.25<=rf<0.7853981633974483: SUB.append(i)
    if len(SUB)>=5000: break
def run(matS, matT, hornP, fusedH, asqP):
    """matS/matT: materialize S/t at 64 before combine (1) or keep wide (0);
       hornP: precision of Horner ops; fusedH: fused mul-add per step;
       asqP: precision of a^2."""
    mm=0
    for i in SUB:
        se,sig=int(inputs[i][:4],16),int(inputs[i][5:21],16)
        neg=(se>>15)&1
        e=(se&0x7FFF)-16383
        rv=(0,sig,e-63)
        rf=sig*2.0**(e-63)
        if rf<0.5: b=18+4*int((rf-0.25)/(4/64.0))
        else: b=36+8*min(2,int((rf-0.5)/(8/64.0)))
        six=b>=36
        sinT=C68(SINROW[b]); cosT=C68(COSROW[b])
        a=fadd(rv,(1,b,-6),100)     # exact
        asq=fmul(a,a,asqP)
        rows=(162,161,160,159,158,157) if six else (172,171,170,169)
        p=C68(rows[0])
        for row in rows[1:]:
            if fusedH:
                # single rounding per step: p*asq + c
                E=min(p[2]+asq[2], C68(row)[2])
                prod=((-1)**(p[0]^asq[0]))*(p[1]*asq[1])
                cc=C68(row); cv=((-1)**cc[0])*cc[1]
                v=prod*(1<<max(0,(p[2]+asq[2])-E))+cv*(1<<max(0,cc[2]-E)) if False else None
                # simpler: exact then round
                Ee=min(p[2]+asq[2], cc[2])
                v=((-1)**(p[0]^asq[0]))*((p[1]*asq[1])<<((p[2]+asq[2])-Ee)) + ((-1)**cc[0])*(cc[1]<<(cc[2]-Ee))
                if v==0: p=(0,0,0)
                else: p=rnP(1 if v<0 else 0,abs(v),Ee,hornP)
            else:
                p=fadd(fmul(p,asq,hornP),C68(row),hornP)
        w=fmul(fmul(p,asq,hornP),a,hornP)
        S=fadd(a,w,100)                # wide sum a + w (exact)
        if matS: S=rnP(S[0],S[1],S[2],64)
        rows=(168,167,166,165,164,163) if six else (176,175,174,173)
        q=C68(rows[0])
        for row in rows[1:]:
            if fusedH:
                cc=C68(row)
                Ee=min(q[2]+asq[2], cc[2])
                v=((-1)**(q[0]^asq[0]))*((q[1]*asq[1])<<((q[2]+asq[2])-Ee)) + ((-1)**cc[0])*(cc[1]<<(cc[2]-Ee))
                if v==0: q=(0,0,0)
                else: q=rnP(1 if v<0 else 0,abs(v),Ee,hornP)
            else:
                q=fadd(fmul(q,asq,hornP),C68(row),hornP)
        t=fmul(q,asq,100)              # wide product (exact)
        if matT: t=rnP(t[0],t[1],t[2],64)
        # fused combine (exact): sin=sinT*(1+t)+cosT*S ; cos=cosT*(1+t)-sinT*S
        m1=fmul(sinT,fadd(ONE,t,100),100)
        m2=fmul(cosT,S,100)
        sin=fadd(m1,m2,100)
        m3=fmul(cosT,fadd(ONE,t,100),100)
        m4=fmul(sinT,S,100)
        cos=fadd(m3,(m4[0]^1,m4[1],m4[2]),100)
        if neg and sin[1]: sin=(sin[0]^1,sin[1],sin[2])
        hf=hw[i].split()
        if enc64(sin)!=(int(hf[1],16),int(hf[2],16)): mm+=1
        if enc64(cos)!=(int(hf[3],16),int(hf[4],16)): mm+=1
    return mm
res=[]
for matS in (1,0):
    for matT in (1,0):
        for hornP in (64,68):
            for fusedH in (0,1):
                for asqP in (64,68,100):
                    mm=run(matS,matT,hornP,fusedH,asqP)
                    res.append((mm,matS,matT,hornP,fusedH,asqP))
res.sort()
for mm,ms,mt,hp,fh,ap in res[:14]:
    print(f"matS={ms} matT={mt} hornP={hp} fused={fh} asqP={ap}: {mm}/{2*len(SUB)} = {100.0*mm/2/len(SUB):.3f}%")
