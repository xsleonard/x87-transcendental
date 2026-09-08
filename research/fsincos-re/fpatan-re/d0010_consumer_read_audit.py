"""Separate producer truncation from consumer reads at the final sum.

RN64(CHOP67(product)) is not interchangeable with RN64(product). This
bounded family covers that missing double-rounding distinction explicitly.
Only saved direct-path counterexamples are used; survivors require controls.
"""
import dataclasses
import itertools
import json
from d0010_causal_intervals import BASE,observation_interval,restore
from d0008_operand_format_audit import Ports
from d0009_kernel_audit import kernel
from graph_v5 import prevalue
from model import cut
from prepare import save


def main():
    data=[]
    for p in json.loads((BASE/'d0009-kernel-frontier.json').read_text())['pairs']:
        t={};prevalue(*p['raw'],trace=t)
        if t['kind']=='direct':data.append((p['raw'],p['rows'][0]['input'],t,observation_interval(p['rows'])))
    reads=('exact','rn64','chop64');pairs=tuple(itertools.combinations_with_replacement(reads,2))
    results=[];survivors=[]
    for (a,b),hs,ts,tp,tz,add,consumer in itertools.product(pairs,reads,reads,reads,reads,
             ('rn64','chop64','chop67','rn67'),('rn64','chop64','rn65','chop65','rn66','chop66')):
        ports=Ports(square_left=a,square_right=b,horner_square=hs,tail_square=ts,tail_product=tp,tail_z=tz)
        cache={};failure=None;tested=0
        for raw,line,t,interval in data:
            z=t['z'];tested+=1
            if z not in cache:cache[z]=z+cut(kernel(z,ports,'long',add)-z,consumer)
            v=restore(cache[z],t,raw)
            if not interval.contains(abs(v)):failure=dict(input=line,prevalue=str(v),tested_groups=tested);break
        r=dict(ports=dataclasses.asdict(ports),last_add=add,tail_consumer=consumer,counterexample=failure)
        results.append(r)
        if failure is None:survivors.append(r);print('TARGET SURVIVOR',r,flush=True)
    print('programs',len(results),'direct survivors',len(survivors),flush=True)
    save(BASE/'d0010-consumer-read-audit.json',dict(status='DIRECT_TARGET_SCREEN_ONLY',results=results,
         survivors=survivors,hardware_executed=False))


if __name__=='__main__':main()
