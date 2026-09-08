"""Separate Horner/tail square producers and producer/consumer rounding.

All choices are global operation roles, never operand-dependent selectors.
Direct-path exact endpoint constraints prune first; a survivor must then
pass every saved direct frontier interval and the full retained corpus.
"""
import itertools
import json
from d0010_causal_intervals import BASE,observation_interval,restore
from graph_v5 import prevalue
from model import ROM,cut
from prepare import save


def format_value(v,spec):
    for s in spec.split('+'):v=cut(v,s)
    return v


def main():
    data=[]
    for p in json.loads((BASE/'d0009-kernel-frontier.json').read_text())['pairs']:
        t={};prevalue(*p['raw'],trace=t)
        if t['kind']=='direct':
            band=observation_interval(p['rows']);data.append((p['raw'],p['rows'][0]['input'],t,band))
    data.sort(key=lambda v:v[3].lo!=v[3].hi)
    formats=('chop67','rn64','chop64','chop67+rn64','exact')
    results=[];survivors=[]
    # Cache a real common computation, not a per-input choice of policy.
    prefix={}
    for square_h,mul in itertools.product(formats,('chop67','exact')):
        for _,_,t,_ in data:
            z=t['z'];key=(z,square_h,mul)
            if key in prefix:continue
            u=format_value(z*z,square_h);h=ROM[123]
            for k in range(122,117,-1):h=cut(ROM[k]+cut(u*h,mul),'rn64')
            prefix[key]=h
    for args in itertools.product(formats,formats,('chop67','exact'),formats,formats,
             ('square-h-z','square-z-h','z-h-square'),('exact','rn64','chop64')):
        sh,st,mul,first,last,order,zread=args;cache={};failure=None;tested=0
        for raw,line,t,band in data:
            z=t['z'];tested+=1
            if z not in cache:
                u=format_value(z*z,st);h=prefix[(z,sh,mul)];rz=cut(z,zread)
                if order=='square-h-z':tail=format_value(format_value(u*h,first)*rz,last)
                elif order=='square-z-h':tail=format_value(format_value(u*rz,first)*h,last)
                else:tail=format_value(format_value(rz*h,first)*u,last)
                cache[z]=z+tail
            v=restore(cache[z],t,raw)
            if not band.contains(abs(v)):failure=dict(input=line,prevalue=str(v),tested_groups=tested);break
        r=dict(horner_square=sh,tail_square=st,horner_multiply=mul,tail_first=first,
               tail_second=last,tail_order=order,z_read=zread,counterexample=failure)
        results.append(r)
        if failure is None:survivors.append(r);print('TARGET SURVIVOR',r,flush=True)
    print('programs',len(results),'direct survivors',len(survivors),flush=True)
    save(BASE/'d0010-split-power-audit.json',dict(status='DIRECT_TARGET_SCREEN_ONLY',results=results,
         survivors=survivors,hardware_executed=False))


if __name__=='__main__':main()
