"""Bounded fixed-width synthesis against exact observed direct endpoints.

The global stage graph has a square, uniform Horner multiply/add, and two
tail products in one of three orders. Widths 64--70 and exact arithmetic are
enumerated, never selected per operand. Exact endpoint points constrain the
whole graph before ordinary interval controls. This is NOT a hardware proof.
"""
import collections
import argparse
import functools
import itertools
import json
from d0010_causal_intervals import BASE,observation_interval,restore
from graph_v5 import prevalue
from model import ROM,cut
from prepare import save

FORMATS=tuple(f'{m}{w}' for m in ('chop','rn') for w in range(64,71))+('exact',)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',default='d0010-width-synthesis.json');args=ap.parse_args()
    assert args.out.startswith('d0010-') and '/' not in args.out
    points=[];controls=[];seen=set()
    for p in json.loads((BASE/'d0009-kernel-frontier.json').read_text())['pairs']:
        raw=p['raw'];t={};prevalue(*raw,trace=t)
        if t['kind']!='direct':continue
        band=observation_interval(p['rows']);controls.append((raw,p['rows'][0]['input'],t,band))
        if not t['swap'] and not(raw[0]&32768 or raw[2]&32768) and band.lo==band.hi and t['z'] not in seen:
            points.append((t['z'],band.lo-t['z'],p['rows'][0]['input']));seen.add(t['z'])
    assert len(points)>=3
    @functools.lru_cache(maxsize=None)
    def prefix(z,s,m,a):
        u=cut(z*z,s);h=ROM[123]
        for k in range(122,117,-1):h=cut(ROM[k]+cut(u*h,m),a)
        return u,h
    def tail(z,s,m,a,f,l,order):
        u,h=prefix(z,s,m,a)
        if order==0:return cut(cut(u*h,f)*z,l)
        if order==1:return cut(cut(u*z,f)*h,l)
        return cut(cut(z*h,f)*u,l)
    rejected=collections.Counter();survivors=[];exact_survivors=0;count=0;point_candidates=[]
    for s,m,a,f,l,order in itertools.product(FORMATS,FORMATS,FORMATS,FORMATS,FORMATS,range(3)):
        count+=1
        for index,(z,want,line) in enumerate(points):
            if tail(z,s,m,a,f,l,order)!=want:rejected['point-'+str(index)]+=1;break
        else:
            exact_survivors+=1
            recipe=dict(square=s,horner_multiply=m,horner_add=a,tail_first=f,tail_second=l,order=order)
            for raw,line,t,band in controls:
                v=restore(t['z']+tail(t['z'],s,m,a,f,l,order),t,raw)
                if not band.contains(abs(v)):
                    rejected['interval-control']+=1
                    point_candidates.append(dict(recipe=recipe,counterexample=dict(input=line,prevalue=str(v),interval=band.json())))
                    break
            else:
                point_candidates.append(dict(recipe=recipe,counterexample=None))
                survivors.append(recipe);print('DIRECT TARGET SURVIVOR',recipe,flush=True)
        if count%250000==0:print('tested',count,'exact-point survivors',exact_survivors,'full-frontier survivors',len(survivors),flush=True)
    save(BASE/args.out,dict(status='BOUNDED_DIRECT_DISCOVERY_SYNTHESIS',programs=count,
        formats=FORMATS,points=[dict(z=str(z),exact_tail=str(want),input=line) for z,want,line in points],
        rejected=dict(rejected),exact_point_survivors=exact_survivors,point_candidates=point_candidates,survivors=survivors,hardware_executed=False))
    print('COMPLETE',count,'exact-point survivors',exact_survivors,'direct frontier survivors',len(survivors),flush=True)


if __name__=='__main__':main()
