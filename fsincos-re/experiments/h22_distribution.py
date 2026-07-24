#!/usr/bin/env python3
"""Full distribution analysis of the C model's residual mismatches."""
from collections import defaultdict
SCR="/private/tmp/claude-501/-Users-steve-llm-coduo-binary-analysis/7d0d0788-22c7-4b55-8fbf-66cb5d3d5805/scratchpad"
inputs=[l.strip() for l in open(f"{SCR}/dense_qn.txt") if l.strip()]
hw=[l.strip() for l in open(f"{SCR}/dense_rn.txt") if l.strip()]
mo=[l.strip() for l in open(f"{SCR}/c_v2_dense.txt") if l.strip()]
GRIDB={}
def cell_of(rf):
    if rf<0.25: return 0
    if rf<0.5: return 18+4*int((rf-0.25)/(4/64.0))
    return 36+8*min(2,int((rf-0.5)/(8/64.0)))
def cell_lo(b):
    return {18:16,22:20,26:24,30:28,36:32,44:40,52:48}[b]/64.0
def cell_hi(b):
    return {18:20,22:24,26:28,30:32,36:40,44:48,52:56}[b]/64.0
# stats
rate_r=defaultdict(lambda:[0,0])     # 64 bins over [0.125, 0.785]
apos=defaultdict(lambda:[0,0])       # position within cell, 10 bins
sgn=defaultdict(int)
both=defaultdict(int)
updown=defaultdict(int)
lowbits=defaultdict(lambda:[0,0])
for l,h,m in zip(inputs,hw,mo):
    se,sig=int(l[:4],16),int(l[5:21],16)
    e=(se&0x7FFF)-16383
    rf=sig*2.0**(e-63)
    if rf>=0.7853981633974483: continue
    if rf<0.125: continue
    rb=int((rf-0.125)/(0.785-0.125)*64)
    rate_r[rb][1]+=1
    hf=h.split(); mf=m.split()
    bs=(hf[1],hf[2])!=(mf[1],mf[2]); bc=(hf[3],hf[4])!=(mf[3],mf[4])
    miss=bs or bc
    if miss: rate_r[rb][0]+=1
    both[("both" if (bs and bc) else ("sin" if bs else ("cos" if bc else "none")))]+=1
    b=cell_of(rf)
    if b:
        frac=(rf-cell_lo(b))/(cell_hi(b)-cell_lo(b))
        ab=int(frac*10)
        apos[ab][1]+=1
        if miss: apos[ab][0]+=1
    if miss:
        # direction: hw above or below model (per side)
        for tag,idx,bad in (("s",1,bs),("c",3,bc)):
            if not bad: continue
            hse,hsg=int(hf[idx],16),int(hf[idx+1],16)
            mse,msg=int(mf[idx],16),int(mf[idx+1],16)
            up = (hsg>msg) if hse==mse else ((hse&0x7FFF)>(mse&0x7FFF))
            if hse>>15: up = not up
            asign = 1 if (b and (rf > (cell_lo(b)+cell_hi(b))/2)) else 0
            sgn[(tag,"up" if up else "dn","a+" if asign else "a-")]+=1
    lb=sig&0xFF
    lowbits[lb&0x7][1]+=1
    if miss: lowbits[lb&0x7][0]+=1
print("=== mismatch rate vs r (64 bins), % ===")
row=[]
for rb in range(64):
    c,t=rate_r[rb]
    row.append(f"{100.0*c/t:.2f}" if t>300 else "  -  ")
for i in range(0,64,8):
    rr=0.125+(i+0.5)*(0.66)/64
    print(f"r~{0.125+i*0.66/64:.3f}: "+" ".join(row[i:i+8]))
print("\n=== sin/cos coincidence ===")
print(dict(both))
print("\n=== rate vs position within table cell (10 bins lo->hi) ===")
for ab in range(10):
    c,t=apos[ab]
    if t: print(f"  pos {ab/10:.1f}-{(ab+1)/10:.1f}: {100.0*c/t:.2f}%  ({c}/{t})")
print("\n=== direction vs a-sign ===")
for k in sorted(sgn): print(f"  {k}: {sgn[k]}")
print("\n=== rate vs low-3-bits of input significand ===")
for k in sorted(lowbits):
    c,t=lowbits[k]
    print(f"  {k}: {100.0*c/t:.2f}%")
