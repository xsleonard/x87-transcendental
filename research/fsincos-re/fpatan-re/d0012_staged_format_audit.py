"""Fixed producer/read pipelines behind the D0011 arithmetic conflict.

A 67/69-bit producer followed by a 64-bit read is not generally a single
RN64 operation. Enumerate these stage roles explicitly, with no input-based
selectors. Direct frontier agreement is discovery only, never promotion.
"""
import argparse
import functools
import itertools
import json
from d0010_causal_intervals import BASE,observation_interval,restore
from graph_v5 import prevalue
from model import ROM,cut
from prepare import save

READS=('exact','chop64','rn64')
NARROW=('chop64','rn64','chop67>rn64','rn67>rn64','chop69>rn64','rn69>rn64',
        'chop69>rn67>rn64','rn69>rn67>rn64')
PRODUCTS=('chop67','rn67','chop69','rn69','chop69>rn67','rn69>rn67')+NARROW


def pipe(v,spec):
    for stage in spec.split('>'):v=cut(v,stage)
    return v


def direct(z,sr,sq,hr,m,a,first,order):
    u=pipe(z*pipe(z,sr),sq);h=ROM[123]
    for k in range(122,117,-1):h=pipe(ROM[k]+pipe(u*pipe(h,hr),m),a)
    if order==0:tail=cut(pipe(u*h,first)*z,'chop67')
    elif order==1:tail=cut(pipe(z*h,first)*u,'chop67')
    else:tail=cut(pipe(z*u,first)*h,'chop67')
    return z+tail


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--tail-read',action='store_true');args=ap.parse_args()
    data=[]
    for pair in json.loads((BASE/'d0009-kernel-frontier.json').read_text())['pairs']:
        t={};prevalue(*pair['raw'],trace=t)
        if t['kind']=='direct':data.append((pair,t,observation_interval(pair['rows'])))
    data.sort(key=lambda r:r[2].lo!=r[2].hi)
    @functools.lru_cache(maxsize=100000)
    def prefix(z,sr,sq,hr,m,a):
        u=pipe(z*pipe(z,sr),sq);h=ROM[123]
        for k in range(122,117,-1):h=pipe(ROM[k]+pipe(u*pipe(h,hr),m),a)
        return u,h
    firsts=('rn67','chop67>rn64','rn67>rn64','rn64','chop69>rn64','rn69>rn64') if args.tail_read else ('chop67',)
    results=[];survivors=[]
    for number,(sr,sq,hr,m,a,first,order) in enumerate(itertools.product(READS,NARROW,READS,PRODUCTS,NARROW,firsts,range(3))):
        failure=None;tested=0
        for pair,t,band in data:
            z=t['z'];u,h=prefix(z,sr,sq,hr,m,a)
            if order==0:tail=cut(pipe(u*h,first)*z,'chop67')
            elif order==1:tail=cut(pipe(z*h,first)*u,'chop67')
            else:tail=cut(pipe(z*u,first)*h,'chop67')
            v=restore(z+tail,t,pair['raw']);tested+=1
            if not band.contains(abs(v)):
                failure=dict(input=pair['rows'][0]['input'],prevalue=str(v),interval=band.json());break
        recipe=dict(square_read=sr,square=sq,horner_read=hr,multiply=m,add=a,first=first,order=order)
        r=dict(recipe=recipe,tested_groups=tested,counterexample=failure);results.append(r)
        if failure is None:
            survivors.append(r);print('DIRECT DISCOVERY SURVIVOR',recipe,flush=True)
        if (number+1)%10000==0:print('tested',number+1,'direct survivors',len(survivors),flush=True)
    name='d0012-staged-tail-read-audit.json' if args.tail_read else 'd0012-staged-format-audit.json'
    save(BASE/name,dict(status='FIXED_STAGED_DIRECT_DISCOVERY_AUDIT',programs=len(results),
        groups=len(data),survivors=survivors,results=results,hardware_executed=False))
    print('COMPLETE',len(results),'programs;',len(survivors),'direct survivors',flush=True)


if __name__=='__main__':main()
