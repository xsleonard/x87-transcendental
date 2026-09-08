"""Explore control-flow-derived final/intermediate add graphs, cached labels."""
import collections
import argparse
import dataclasses
import itertools
import json
from pathlib import Path
from explore import groups,BASE
from graph_v2 import Graph,prevalue
from model import Policy,encode,value
from prepare import save


def score(g,data):
    c=collections.Counter()
    for key,rows in data.items():
        v=prevalue(*key,g)
        for rc,se,sig,c1,ident in rows:
            encoded=encode(v,rc);ec1=int(abs(value(*encoded))>abs(v))
            c['rows']+=1;c['misses']+=encoded!=(se,sig);c['C1_misses']+=ec1!=c1
    return dict(c)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=('controlflow','coupled','reduction-products'),default='controlflow')
    args=parser.parse_args();data=groups();out=[]
    if args.phase=='controlflow':
        graphs=[Graph(placement=p,intermediate=i) for p,i in itertools.product(
            ('none','rotate','swap','always','base-first'),('exact','chop67','rn67','rn64'))]
    elif args.phase=='coupled':
        graphs=[Graph(arithmetic=dataclasses.replace(Policy(),direct_limit=l,denominator=n,div=d),kernel=k)
                for l,n,d,k in itertools.product((16,32,64),('rn64','chop67','rn67','exact'),('chop67','rn67','exact'),('exact','chop67'))]
    else:
        graphs=[Graph(arithmetic=dataclasses.replace(Policy(),direct_limit=32,denominator=n,div=d),reduction_mul=m)
                for m,n,d in itertools.product(('chop67','rn67','rn64','exact'),('chop67','rn64','exact'),('chop67','rn67'))]
    for g in graphs:
        result=dict(graph=dataclasses.asdict(g),**score(g,data));out.append(result)
        print(result['misses'],result['C1_misses'],json.dumps(result['graph'],sort_keys=True),flush=True)
    save(BASE/(args.phase+'-schedules.json'),dict(status='DISCOVERY_ONLY',results=out,best=sorted(out,key=lambda r:r['misses'])[:8]))


if __name__=='__main__':main()
