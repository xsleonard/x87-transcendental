"""Fresh V5 challenge: mined schedule separators plus independent controls.

No hardware labels are consulted by the separator miner. Nearby operands
from discovery are explicitly regression-neighborhood coverage, not blind
independent samples. All selected tuples pass local/private and remote guards.
"""
import json
import random
from dataclasses import replace
from pathlib import Path
from architecture import POLICY
from freeze_stream import freeze
from model import F,encode,pow2,value
from compressed_guard import digest

BASE=Path(__file__).resolve().parents[1]/'tmp/fpatan-re'
SEED='fpatan-d0009-20260905-short-rom-tail-read'


def orbits(pair,rng):
    ys,ym,xs,xm=pair
    # Normalized positive pairs stay well inside the finite exponent range.
    for swap in (False,True):
        for sy in (0,32768):
            for sx in (0,32768):
                shift=rng.randrange(-15000,15001)
                y=(ys&32767)+shift; x=(xs&32767)+shift
                a,b,c,d=(x,xm,y,ym) if swap else (y,ym,x,xm)
                yield a|sy,b,c|sx,d


def generate():
    rng=random.Random(SEED)
    receipt=json.loads((BASE/'d0009-miner-complete.json').read_text())
    assert receipt['returncode']==0 and receipt['output_sha256']==digest(BASE/'d0009-separators.txt')
    for line in (BASE/'d0009-separators.txt').read_text().splitlines():
        *raw,mask=line.split();pair=tuple(int(s,16) for s in raw)
        for p in orbits(pair,rng):yield p,'mined-schedule-separator-'+mask
    # Include neighborhoods of every D0008 V4 failure and the additional
    # control operands that rejected the closest V5 alternatives.
    centers=set()
    for number in (0,1,2,4,5):
        path=BASE/f'd0008-schedule{number}-full.json'
        if number==0:
            inputs=[r['input'] for p in json.loads((BASE/'d0008-frontier.json').read_text())['pairs'] for r in p['rows']]
        else:
            inputs=[m['input'] for m in json.loads(path.read_text())['jobs']['d0008']['misses']]
        for line in inputs:
            ys,ym,xs,xm=(int(t,16) for t in line.split()[3:]);shift=(xs&32767)-16383
            centers.add(((ys&32767)-shift,ym,16383,xm))
    offsets=(-8191,-2047,-511,-127,-31,-7,-3,-2,-1,1,2,3,7,31,127,511,2047,8191)
    for ys,ym,xs,xm in sorted(centers):
        for delta in offsets:
            for dy,dx in ((delta,0),(0,delta),(delta,delta)):
                if not (1<<63)<=ym+dy<(1<<64) or not (1<<63)<=xm+dx<(1<<64):continue
                for p in orbits((ys,ym+dy,xs,xm+dx),rng):yield p,'discovery-neighborhood'
    for i in range(32768):
        family=i%4;xs=16383;xm=rng.getrandbits(63)|(1<<63);x=value(xs,xm)
        u=F(rng.getrandbits(64)+1,(1<<64)+1)
        if family==0:
            n=2+(i//4)%31;lo=F(2*n-1,64);hi=min(F(1),F(2*n+1,64))
            ys,ym=encode(x*(lo+(hi-lo)*u));kind='independent-table-cells'
        elif family==1:
            ys,ym=encode(x*u*F(3,64));kind='independent-direct'
        elif family==2:
            n=rng.randrange(2,33);ys,ym=encode(x*(F(n,32)+rng.choice((-1,1))*u*pow2(-rng.randrange(7,70))))
            kind='independent-cancellation'
        else:
            ys=16383-rng.randrange(5,45);ym=rng.getrandbits(63)|(1<<63);kind='independent-small'
        shift=rng.randrange(-15000,15001);ys+=shift;xs+=shift
        if rng.getrandbits(1):ys,ym,xs,xm=xs,xm,ys,ym
        yield (ys|(rng.getrandbits(1)<<15),ym,xs|(rng.getrandbits(1)<<15),xm),kind


if __name__=='__main__':
    freeze('d0009',SEED,generate,('prepare_d0009.py','graph_v5.py','fpatan_candidate_v5.c',
           'd0008_schedule_audit.c','d0009_separator_mine.c','d0009_run_miner.py','d0009_alternatives.py'),
           policy=replace(POLICY,numerical_graph='v5'),
           purpose='Prospective short-ROM and tail-operand-format discrimination plus independent controls')
