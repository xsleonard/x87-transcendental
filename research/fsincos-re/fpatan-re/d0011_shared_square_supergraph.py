"""Require one square recipe across inputs, while freeing Horner policies.

The wider inputwise audit leaves only three terminal product orders. Here
each of 54 square producers must be shared across all saved direct groups,
but the Horner operation choices remain independently free per input. A
rejection therefore rules out every fixed Horner policy behind that square.
"""
import collections
import itertools
import json
from d0010_causal_intervals import BASE,observation_interval
from d0011_relaxed_horner import READS,FORMATS,reachable
from graph_v5 import prevalue
from model import cut
from prepare import save


def main():
    data=[];seen=set()
    for pair in json.loads((BASE/'d0009-kernel-frontier.json').read_text())['pairs']:
        raw=pair['raw'];t={};prevalue(*raw,trace=t)
        if t['kind']!='direct' or t['swap'] or raw[2]&32768:continue
        band=observation_interval(pair['rows']);key=(t['z'],band)
        if key in seen:continue
        seen.add(key);data.append((pair,t,band))
    squares=list(itertools.product(READS,READS,FORMATS))
    failures=collections.Counter();counterexamples={};provenance={}
    for index,(pair,t,band) in enumerate(data):
        z=t['z'];us=[cut(cut(z,left)*cut(z,right),fmt) for left,right,fmt in squares]
        states={u:reachable(z,u) for u in set(us)};valid={}
        for u,(hs,counts) in states.items():
            for order in range(3):
                valid[u,order]=[]
                for h in hs:
                    if order==0:tail=cut(cut(u*h,'chop67')*z,'chop67')
                    elif order==1:tail=cut(cut(z*h,'chop67')*u,'chop67')
                    else:tail=cut(cut(u*z,'chop67')*h,'chop67')
                    if band.contains(z+tail):valid[u,order].append(h)
        for square,u in enumerate(us):
            for order in range(3):
                key=f'{square}:{order}'
                if not valid[u,order]:
                    failures[key]+=1
                    if key not in counterexamples:
                        counterexamples[key]=dict(input=pair['rows'][0]['input'],z=str(z),u=str(u),
                            interval=band.json(),reachable_h_values=[str(h) for h in states[u][0]],
                            state_counts=states[u][1])
        if (index+1)%16==0:print('shared-square groups',index+1,flush=True)
    results=[]
    for square,(left,right,fmt) in enumerate(squares):
        for order in range(3):
            key=f'{square}:{order}'
            results.append(dict(square=dict(left_read=left,right_read=right,format=fmt),order=order,
                failed_groups=failures[key],counterexample=counterexamples.get(key)))
    good=[r for r in results if not r['failed_groups']]
    save(BASE/'d0011-shared-square-supergraph.json',dict(status='SHARED_SQUARE_RELAXED_HORNER_NOT_A_SOLUTION',
        programs=len(results),groups=len(data),surviving_programs=good,results=results,
        horner='Per-input and per-node free READS and FORMATS, with all reachable states retained',
        reads=READS,formats=FORMATS,hardware_executed=False))
    print('COMPLETE',len(results),'programs; shared-square survivors',len(good),flush=True)


if __name__=='__main__':main()
