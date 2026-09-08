"""Test whether the table selector reads a rounded quotient (cached only)."""
import collections
import dataclasses
import itertools
import json
from pathlib import Path
from graph_v2 import Graph,prevalue
from model import Policy,encode,value
from protocol import validate_output
from prepare import save

BASE=Path(__file__).resolve().parents[1]/'tmp/fpatan-re'


def main():
    data=collections.defaultdict(list)
    for job in ('d0001','d0002'):
        p=BASE/job
        for actual,line in zip((p/'hardware.txt').read_text().splitlines(),(p/'inputs.txt').read_text().splitlines()):
            t=line.split();key=tuple(int(s,16) for s in t[3:]);ys,ym,xs,xm=key
            y,x=abs(value(ys,ym)),abs(value(xs,xm))
            if min(y,x)/max(y,x)<value(0x3fe1,1<<63):continue
            data[key].append((job,t[1],validate_output(actual,line)))
    results=[]
    for initial in ('exact','chop64','chop65','chop66','chop67','rn64','rn65','rn66','rn67'):
        graph=Graph(arithmetic=dataclasses.replace(Policy(),denominator='chop67',direct_limit=32,initial_div=initial),reduction_mul='exact')
        counts=collections.Counter();misses=[]
        for key,rows in data.items():
            v=prevalue(*key,graph)
            for job,rc,o in rows:
                encoded=encode(v,rc);miss=encoded!=(o['se'],o['sig'])
                counts[job+'_rows']+=1;counts[job+'_misses']+=miss
                if miss:misses.append(dict(job=job,rc=rc,input=[f'{k:x}' for k in key],hardware=[o['se'],o['sig']],prediction=encoded))
        results.append(dict(initial=initial,counts=dict(counts),misses=misses))
        print(initial,dict(counts),flush=True)
    save(BASE/'boundary-index-audit.json',dict(status='DISCOVERY_ONLY',results=results,hardware_executed=False))


if __name__=='__main__':main()
