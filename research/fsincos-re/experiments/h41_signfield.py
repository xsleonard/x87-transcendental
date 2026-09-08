#!/usr/bin/env python3
"""Read the sign(Delta) field from the tiebreaker captures."""
import importlib.util, sys
SCR="/private/tmp/claude-501/-Users-steve-llm-coduo-binary-analysis/7d0d0788-22c7-4b55-8fbf-66cb5d3d5805/scratchpad"
spec=importlib.util.spec_from_file_location("g","h40_tiebreak_gen.py")
# reimplement minimal pieces instead of importing (h40 runs generation on import)
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
SINROW={18:181,22:182,26:183,30:184}; COSROW={18:189,22:190,26:191,30:192}
ONE=(0,1,0)
def model_full(sig64, side):
    e=-2
    rv=(0,sig64,e-63)
    rf=sig64*2.0**(e-63)
    b=18+4*int((rf-0.25)/(4/64.0))
    sinT=C68(SINROW[b]); cosT=C68(COSROW[b])
    a=fadd(rv,(1,b,-6),200)
    af=((-1)**a[0])*a[1]*2.0**a[2] if a[1] else 0.0
    asq=fmul(a,a,64)
    p=C68(172)
    for row in (171,170,169): p=fadd(fmul(p,asq,64),C68(row),64)
    w=fmul(fmul(p,asq,64),a,64)
    S=fadd(a,w,64)
    q=C68(176)
    for row in (175,174,173): q=fadd(fmul(q,asq,64),C68(row),64)
    t=fmul(q,asq,64)
    if side=="s":
        m1=fmul(sinT,fadd(ONE,t,300),300); m2=fmul(cosT,S,300)
        T=fadd(m1,m2,300)
    else:
        m3=fmul(cosT,fadd(ONE,t,300),300); m4=fmul(sinT,S,300)
        T=fadd(m3,(m4[0]^1,m4[1],m4[2]),300)
    # RN64 of T and boundary side info
    sT,sigT,ET=T
    bl=sigT.bit_length(); us=bl-64
    frac=sigT&((1<<us)-1); half=1<<(us-1)
    d=frac-half     # >0: model rounds up; hw rounds up iff Delta > -d*2^ET... 
    r64=rnP(sT,sigT,ET,64)
    return b, af, d, us, ET, r64
inputs=[l.strip() for l in open(f"{SCR}/tiebreak_inputs.txt") if l.strip()]
meta=[l.split() for l in open(f"{SCR}/tiebreak_meta.txt") if l.strip()]
hw=[l.split() for l in open(f"{SCR}/tiebreak_out.txt") if l.strip()]
from collections import defaultdict
field=defaultdict(lambda:[0,0])
for l,(side,bstr),h in zip(inputs,meta,hw):
    sig64=int(l[5:21],16)
    b,af,d,us,ET,r64=model_full(sig64,side)
    idx=1 if side=="s" else 3
    hse,hsg=int(h[idx],16),int(h[idx+1],16)
    # model rounded value:
    s_,sg_,E_=r64
    bl=sg_.bit_length()
    if bl<64: sg_<<=(64-bl); E_-=(64-bl)
    mse=(s_<<15)|(E_+63+16383)
    hw_up = None
    if (mse,sg_)==(hse,hsg):
        hw_up = d>0        # hw agreed with model's side
    else:
        hw_up = not (d>0)  # hw went the other way
    # Delta > -d  if hw_up else Delta < -d ; with |d| tiny: sign(Delta)=+1 if hw_up
    ab=min(15,int((af+1/32)/(1/16)*16)) if b else 0
    key=(b,side,ab)
    field[key][0]+= 1 if hw_up else 0
    field[key][1]+=1
print("sign(Delta) field: fraction positive by cell/side/a-bin (16 bins over cell)")
for b in (18,22,26,30):
    for side in ("s","c"):
        row=[]
        for ab in range(16):
            n=field[(b,side,ab)][1]
            row.append(f"{100.0*field[(b,side,ab)][0]/n:3.0f}({n:3d})" if n else "  - (  0)")
        print(f"cell {b} {side}: "+" ".join(row))
