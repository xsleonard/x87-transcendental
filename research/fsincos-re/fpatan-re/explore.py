"""Discovery-only global schedule comparisons on immutable D0001 labels.

No selected policy is promoted by this script. Future acceptance requires
structural justification, faithful C, and independently frozen fresh tests.
All enumerated operation policies and full scores are retained.
"""
import argparse
import collections
import dataclasses
import itertools
import json
from pathlib import Path
import time
from model import Policy,prevalue,encode
from protocol import validate_output
from prepare import save

BASE=Path(__file__).resolve().parents[1]/'tmp/fpatan-re/d0001'


def groups():
    result=collections.defaultdict(list)
    for row,line in zip((BASE/'hardware.txt').read_text().splitlines(),(BASE/'inputs.txt').read_text().splitlines()):
        t=line.split();ys,ym,xs,xm=(int(x,16) for x in t[3:])
        # Exact common power-of-two normalization is a proved symmetry of
        # these finite candidate operators. Hardware labels remain original.
        shift=(xs&0x7fff)-16383
        key=(ys-shift,ym,xs-shift,xm)
        observed=validate_output(row,line)
        result[key].append((t[1],observed['se'],observed['sig'],observed['C1'],t[0]))
    return result


def score(policy,data):
    c=collections.Counter()
    for key,rows in data.items():
        before=prevalue(*key,policy)
        for rc,se,sig,c1,ident in rows:
            result=encode(before,rc)
            c['rows']+=1;c['misses']+=result!=(se,sig)
    return dict(c)


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    p.add_argument('--phase',choices=('terminal','arithmetic','reduction'),default='terminal');a=p.parse_args()
    data=groups();results=[];started=time.time()
    if a.phase=='terminal':
        policies=[dataclasses.replace(Policy(),combine=c,rotate=r,table=t) for c,r,t in
            itertools.product(('exact','chop67','rn67','rn64'),('exact','chop67','rn67'),('exact','rn64'))]
    elif a.phase=='arithmetic':
        policies=[dataclasses.replace(Policy(),div=d,denominator=n,sub=s) for d,n,s in
            itertools.product(('chop67','rn67','rn64','exact'),('rn64','chop67','rn67','exact'),('chop67','rn64','exact'))]
    else:
        policies=[dataclasses.replace(Policy(),direct_limit=l,polynomial=c,reduction=r,initial_div=d) for l,c,r,d in
            itertools.product((8,16,32,64),('short','long'),('pair','ratio'),('exact','rn64','chop67'))]
    for i,policy in enumerate(policies):
        result=dict(policy=dataclasses.asdict(policy),**score(policy,data));results.append(result)
        print(i,result['misses'],json.dumps(result['policy'],sort_keys=True),flush=True)
    save(a.out,dict(status='DISCOVERY_ONLY',elapsed=time.time()-started,results=results,
        best=sorted(results,key=lambda r:r['misses'])[:10],hardware_executed=False))


if __name__=='__main__':main()
