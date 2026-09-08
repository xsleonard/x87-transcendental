"""Fixed schedules behind the terminal-supergraph square discriminator.

Use the globally fixed u=RN64(z*CHOP64(z)) and cube-first CHOP67 tail.
Enumerate fixed Horner operation roles, not input-dependent choices. This
is discovery-only and must not change the main candidate or the paper.
"""
import argparse
import collections
import functools
import itertools
import json
from d0010_causal_intervals import BASE,observation_interval,restore
from d0011_relaxed_horner import READS,FORMATS
from graph_v5 import prevalue
from model import ROM,cut
from prepare import save

POLICIES=tuple(itertools.product(READS,READS,FORMATS,FORMATS))


def step(u,h,k,policy):
    ur,hr,m,a=policy
    return cut(ROM[k]+cut(cut(u,ur)*cut(h,hr),m),a)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--split-last',action='store_true');args=ap.parse_args()
    data=[]
    for pair in json.loads((BASE/'d0009-kernel-frontier.json').read_text())['pairs']:
        t={};prevalue(*pair['raw'],trace=t)
        if t['kind']!='direct':continue
        data.append((pair,t,observation_interval(pair['rows'])))
    data.sort(key=lambda row:row[2].lo!=row[2].hi)
    @functools.lru_cache(maxsize=None)
    def prefix(z,policy):
        u=cut(z*cut(z,'chop64'),'rn64');h=ROM[123]
        for k in range(122,118,-1):h=step(u,h,k,policy)
        return u,h,cut(u*z,'chop67')
    choices=itertools.product(POLICIES,POLICIES) if args.split_last else ((p,p) for p in POLICIES)
    results=[];survivors=[]
    for number,(early,last) in enumerate(choices):
        failure=None;tested=0
        for pair,t,band in data:
            u,h,cube=prefix(t['z'],early);h=step(u,h,118,last)
            v=restore(t['z']+cut(cube*h,'chop67'),t,pair['raw']);tested+=1
            if not band.contains(abs(v)):
                failure=dict(input=pair['rows'][0]['input'],prevalue=str(v),interval=band.json());break
        r=dict(early=early,last=last,counterexample=failure,tested_groups=tested)
        results.append(r)
        if failure is None:survivors.append(r);print('DIRECT FRONTIER SURVIVOR',early,last,flush=True)
        if (number+1)%10000==0:print('tested',number+1,'survivors',len(survivors),flush=True)
    suffix='split-last' if args.split_last else 'uniform'
    save(BASE/f'd0011-asymmetric-square-{suffix}.json',dict(status='FIXED_DIRECT_FRONTIER_DISCOVERY_AUDIT',
        square='RN64(z*CHOP64(z))',tail='CHOP67(CHOP67(u*z)*h)',programs=len(results),
        policy_fields=('square_read','horner_read','multiply','add'),groups=len(data),
        survivors=survivors,results=results,hardware_executed=False))
    print('COMPLETE',len(results),'programs;',len(survivors),'direct frontier survivors',flush=True)


if __name__=='__main__':main()
