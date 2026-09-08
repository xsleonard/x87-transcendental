"""Construct fresh external ratios in exactly the same CHOP67 quotient cell.

Keep each known direct anchor's signs and exponents unchanged, but vary both
64-bit significands. Spread exact discarded remainders across the cell. All
z-only arithmetic graphs predict anchor-equivalent outputs; no fresh hardware
label is needed to establish this relation. Private/history clearance is a
separate mandatory freeze/guard step, not bypassed by this generator.
"""
import hashlib
import json
import random
from d0010_causal_intervals import BASE,observation_interval
from graph_v5 import prevalue
from model import F,cut,exponent,pow2
from prepare import save

SEED='fpatan-d0013-20260905-identical-quotient-hidden-state'


def ceil(v):return -((-v.numerator)//v.denominator)


def main():
    source=BASE/'d0009-kernel-frontier.json';anchors={}
    for pair in json.loads(source.read_text())['pairs']:
        t={};prevalue(*pair['raw'],trace=t)
        if t['kind']!='direct' or t['swap'] or pair['raw'][2]&32768:continue
        z=t['z']
        if z not in anchors or pair['raw'][0]&32768<anchors[z]['raw'][0]&32768:anchors[z]=pair
    rng=random.Random(SEED);groups=[];all_raw=set();attempts=0
    for number,(z,anchor) in enumerate(sorted(anchors.items())):
        line=anchor['rows'][0]['input'];ys,ym,xs,xm=(int(v,16) for v in line.split()[3:])
        d=(ys&32767)-(xs&32767);factor=z/pow2(d);unit=pow2(exponent(z)-66)
        old=F(ym,xm)*pow2(d)
        xmin=max(1<<63,ceil(F(1<<63)/factor));xmax=min((1<<64)-1,int(F((1<<64)-1)/factor))
        assert xmin<xmax
        pool={};trials=0
        while len(pool)<1024 and trials<100000:
            trials+=1;xx=rng.randrange(xmin,xmax+1);yy=ceil(factor*xx)
            if not (1<<63)<=yy<(1<<64):continue
            r=F(yy,xx)*pow2(d)
            if r==old or not z<=r<z+unit:continue
            raw=(ys,yy,xs,xx)
            assert cut(r,'chop67')==z and raw!=(ys,ym,xs,xm)
            pool[raw]=(r-z)/unit
        assert len(pool)==1024
        chosen=[]
        for i in range(16):
            target=F(i,15);raw=min(pool,key=lambda p:abs(pool[p]-target));fraction=pool.pop(raw)
            assert raw not in all_raw;all_raw.add(raw)
            chosen.append(dict(raw=raw,discarded_fraction=str(fraction)))
        assert F(chosen[0]['discarded_fraction'])<F(1,64)
        assert F(chosen[-1]['discarded_fraction'])>F(63,64)
        t0={};v0=prevalue(ys,ym,xs,xm,trace=t0)
        for p in chosen:
            trace={};v=prevalue(*p['raw'],trace=trace)
            assert trace['z']==z and trace['kind']=='direct' and v==v0
        groups.append(dict(index=number,anchor_input=line,anchor_rows=anchor['rows'],
            z=str(z),ulp=str(unit),anchor_discarded_fraction=str((old-z)/unit),pairs=chosen,trials=trials))
        attempts+=trials
        if (number+1)%16==0:print('proved quotient-collision groups',number+1,flush=True)
    save(BASE/'d0012-quotient-discriminators.json',dict(status='GENERATED_NOT_CLEARED_OR_CAPTURED',seed=SEED,
        source_frontier_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),groups=groups,
        counts=dict(anchor_states=len(groups),fresh_raw_pairs=len(all_raw),attempts=attempts),
        relation='Same signs, exponents and exact CHOP67 quotient; different exact input ratio.',
        limits='Requires private/public/tuple clearance and a separate freeze before any hardware execution.',
        hardware_executed=False))
    print('COMPLETE',len(groups),'states',len(all_raw),'fresh operand pairs',flush=True)


if __name__=='__main__':main()
