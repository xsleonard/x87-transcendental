"""Split quotient carriers: lead CHOP67, independent polynomial reads.

The polynomial square may consume differently formatted reads of the exact
ratio, including bits discarded by the leading term. This is a global port
format hypothesis, not a selector derived from endpoint error states.
"""
import itertools
import json
from d0010_causal_intervals import BASE,observation_interval,restore
from graph_v5 import prevalue
from model import ROM,cut
from prepare import save


def main():
    data=[]
    for p in json.loads((BASE/'d0009-kernel-frontier.json').read_text())['pairs']:
        t={};prevalue(*p['raw'],trace=t)
        if t['kind']=='direct':data.append((p['raw'],p['rows'][0]['input'],t,observation_interval(p['rows'])))
    data.sort(key=lambda v:v[3].lo!=v[3].hi)
    reads=tuple(f'{m}{w}' for m in ('chop','rn') for w in range(64,70))+('exact',)
    read_pairs=tuple(itertools.combinations_with_replacement(reads,2));results=[];survivors=[];prefix={}
    # Prefixes are computed lazily, since exact endpoint cases reject most
    # common programs before later operands are needed.
    for (left,right),square,lastadd,outer,first,last in itertools.product(read_pairs,
            ('chop67','rn64','chop64'),('rn64','chop67'),reads,
            ('chop67','rn64'),('chop67','rn64','chop64')):
        cache={};failure=None;tested=0
        for raw,line,t,band in data:
            r=t['ratio'];key=(r,left,right,square,lastadd);tested+=1
            if key not in prefix:
                u=cut(cut(r,left)*cut(r,right),square);h=ROM[123]
                for k in range(122,117,-1):h=cut(ROM[k]+cut(u*h,'chop67'),lastadd if k==118 else 'rn64')
                prefix[key]=(u,h)
            if r not in cache:
                u,h=prefix[key];tail=cut(cut(u*h,first)*cut(r,outer),last);cache[r]=t['z']+tail
            v=restore(cache[r],t,raw)
            if not band.contains(abs(v)):failure=dict(input=line,prevalue=str(v),tested_groups=tested);break
        item=dict(square_left=left,square_right=right,square_result=square,last_add=lastadd,
                  tail_outer=outer,tail_first=first,tail_second=last,counterexample=failure)
        results.append(item)
        if failure is None:survivors.append(item);print('DIRECT TARGET SURVIVOR',item,flush=True)
    print('programs',len(results),'direct survivors',len(survivors),flush=True)
    save(BASE/'d0010-quotient-carrier-audit.json',dict(status='DIRECT_TARGET_SCREEN_ONLY',results=results,
         survivors=survivors,hardware_executed=False))


if __name__=='__main__':main()
