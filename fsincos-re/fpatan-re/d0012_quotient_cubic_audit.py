"""Wider divided carrier in a cubic-first FPATAN polynomial graph.

The final lead remains CHOP67(r), while square/cubic operands may read a
different fixed width of the same exact external ratio. D0010's quotient
audit used square-Horner-z tail order, so it did not cover this composition.
No new hardware or input-conditioned arithmetic is used.
"""
import functools
import itertools
import json
from d0010_causal_intervals import BASE,observation_interval,restore
from d0012_staged_format_audit import pipe
from graph_v5 import prevalue
from model import ROM,cut
from prepare import save

READS=tuple(f'{m}{w}' for w in range(64,71) for m in ('chop','rn'))+('exact',)
SQUARES=('rn64','chop67','chop67>rn64','rn67>rn64','chop69>rn64','rn69>rn64')
ADDS=('rn64','chop67>rn64','rn67>rn64','chop69>rn64','rn69>rn64')


def main():
    data=[]
    for pair in json.loads((BASE/'d0009-kernel-frontier.json').read_text())['pairs']:
        t={};prevalue(*pair['raw'],trace=t)
        if t['kind']=='direct':data.append((pair,t,observation_interval(pair['rows'])))
    data.sort(key=lambda row:row[2].lo!=row[2].hi)
    @functools.lru_cache(maxsize=100000)
    def prefix(r,left,right,square,add):
        u=pipe(pipe(r,left)*pipe(r,right),square);h=ROM[123]
        for k in range(122,117,-1):h=pipe(ROM[k]+cut(u*h,'chop67'),add)
        return u,h
    results=[];survivors=[]
    for number,((left,right),square,outer,add) in enumerate(itertools.product(
            itertools.combinations_with_replacement(READS,2),SQUARES,READS,ADDS)):
        failure=None;tested=0
        for pair,t,band in data:
            u,h=prefix(t['ratio'],left,right,square,add)
            cube=cut(u*pipe(t['ratio'],outer),'chop67');k=t['z']+cut(cube*h,'chop67')
            v=restore(k,t,pair['raw']);tested+=1
            if not band.contains(abs(v)):
                failure=dict(input=pair['rows'][0]['input'],prevalue=str(v),interval=band.json());break
        recipe=dict(square_left=left,square_right=right,square=square,cubic_outer=outer,add=add)
        r=dict(recipe=recipe,tested_groups=tested,counterexample=failure);results.append(r)
        if failure is None:survivors.append(r);print('DIRECT DISCOVERY SURVIVOR',recipe,flush=True)
        if (number+1)%10000==0:print('tested',number+1,'survivors',len(survivors),flush=True)
    save(BASE/'d0012-quotient-cubic-audit.json',dict(status='SPLIT_QUOTIENT_CUBIC_DIRECT_DISCOVERY_AUDIT',
        lead='CHOP67(exact ratio)',groups=len(data),programs=len(results),results=results,
        survivors=survivors,hardware_executed=False))
    print('COMPLETE',len(results),'programs;',len(survivors),'direct survivors',flush=True)


if __name__=='__main__':main()
