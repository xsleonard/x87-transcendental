"""Role-specific final Horner multiply/add and two tail-product formats.

Earlier Horner stages retain the existing CHOP67/RN64 schedule. This differs
from the uniform-width sweep: the final coefficient-add may expose a wider
carrier to the tail. Every policy is global and checked against all saved
direct frontier intervals, not just the exact-value subset.
"""
import collections
import itertools
import json
from d0010_causal_intervals import BASE,observation_interval,restore
from d0010_split_power_audit import format_value
from graph_v5 import prevalue
from model import ROM,cut
from prepare import save

FORMATS=tuple(f'{m}{w}' for m in ('chop','rn') for w in range(64,71))+('exact','chop67+rn64','chop69+rn64')


def main():
    data=[];prefix={}
    for p in json.loads((BASE/'d0009-kernel-frontier.json').read_text())['pairs']:
        t={};prevalue(*p['raw'],trace=t)
        if t['kind']!='direct':continue
        band=observation_interval(p['rows']);data.append((p['raw'],p['rows'][0]['input'],t,band))
        z=t['z']
        if z not in prefix:
            u=cut(z*z,'chop67');h=ROM[123]
            for k in range(122,118,-1):h=cut(ROM[k]+cut(u*h,'chop67'),'rn64')
            prefix[z]=(u,h)
    data.sort(key=lambda v:v[3].lo!=v[3].hi)
    rejected=collections.Counter();survivors=[];count=0;hcache={}
    for mul,add,first,last,order in itertools.product(FORMATS,FORMATS,FORMATS,FORMATS,range(3)):
        count+=1;cache={}
        for raw,line,t,band in data:
            z=t['z'];key=(z,mul,add)
            if key not in hcache:
                u,old=prefix[z];hcache[key]=format_value(ROM[118]+format_value(u*old,mul),add)
            if z not in cache:
                u,_=prefix[z];h=hcache[key]
                if order==0:tail=format_value(format_value(u*h,first)*z,last)
                elif order==1:tail=format_value(format_value(u*z,first)*h,last)
                else:tail=format_value(format_value(z*h,first)*u,last)
                cache[z]=z+tail
            v=restore(cache[z],t,raw)
            if not band.contains(abs(v)):rejected[line]+=1;break
        else:
            policy=dict(last_multiply=mul,last_add=add,tail_first=first,tail_second=last,order=order)
            survivors.append(policy);print('DIRECT FRONTIER SURVIVOR',policy,flush=True)
    print('programs',count,'direct survivors',len(survivors),flush=True)
    save(BASE/'d0010-terminal-graph-synthesis.json',dict(status='DIRECT_FRONTIER_DISCOVERY_ONLY',programs=count,
        formats=FORMATS,rejected=dict(rejected),survivors=survivors,hardware_executed=False))


if __name__=='__main__':main()
