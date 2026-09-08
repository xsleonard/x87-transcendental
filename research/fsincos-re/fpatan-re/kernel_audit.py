"""Offline direct/table dispatch and polynomial-stage ablation, no captures."""
import collections
import argparse
import dataclasses
import itertools
import json
from pathlib import Path
from model import value,encode,F
from graph_v3 import Program,prevalue
from protocol import validate_output
from prepare import save

BASE=Path(__file__).resolve().parents[1]/'tmp/fpatan-re'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=('original','divider'),default='original');args=parser.parse_args()
    data=collections.defaultdict(list)
    for job in (('d0001','d0002') if args.phase=='original' else ('d0001','d0002','d0003')):
        p=BASE/job
        for actual,line in zip((p/'hardware.txt').read_text().splitlines(),(p/'inputs.txt').read_text().splitlines()):
            t=line.split();key=tuple(int(s,16) for s in t[3:]);ys,ym,xs,xm=key
            y,x=abs(value(ys,ym)),abs(value(xs,xm));r=min(y,x)/max(y,x)
            if r<F(1,256):continue
            # Normalize common exponent, preserving exact input dyadics.
            shift=(xs&32767)-16383;key=(ys-shift,ym,xs-shift,xm)
            data[key].append((job,t[1],validate_output(actual,line)))
    results=[]
    if args.phase=='original':
        programs=[Program(direct_limit=l,direct_test=t,tail_first=f,tail_second=s) for l,t,f,s in
                  itertools.product((16,32),('ratio','ratio-le','exponent'),('chop67','rn64','exact'),('chop67','rn64'))]
    else:
        programs=[Program(direct_limit=l,direct_test=t,direct_divider=d,direct_lead=lead) for l,t,d,lead in
                  itertools.product((16,32),('ratio','exponent'),('rn64','chop64','chop65','chop66','chop67','chop68','chop69','exact'),('rounded','exact'))]
    for p in programs:
        counts=collections.Counter();misses=[]
        for key,rows in data.items():
            v=prevalue(*key,p)
            for job,rc,o in rows:
                result=encode(v,rc);miss=result!=(o['se'],o['sig']);c1=int(abs(value(*result))>abs(v))
                counts[job+'_rows']+=1;counts[job+'_misses']+=miss;counts[job+'_C1_misses']+=c1!=o['C1']
                if miss:misses.append(dict(job=job,rc=rc,raw=[f'{k:x}' for k in key]))
        item=dict(program=dataclasses.asdict(p),counts=dict(counts),misses=misses);results.append(item)
        print(dict(counts),dataclasses.asdict(p),flush=True)
    results.sort(key=lambda x:sum(v for k,v in x['counts'].items() if k.endswith('_misses')))
    filename='kernel-audit.json' if args.phase=='original' else 'kernel-divider-audit.json'
    save(BASE/filename,dict(status='DISCOVERY_ONLY',results=results,best=results[:8],hardware_executed=False))


if __name__=='__main__':main()
