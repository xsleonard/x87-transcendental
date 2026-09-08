#!/usr/bin/env python3
"""Exact interval bounds for every paired polynomial binade, not input sampling.

Source-backed graph transcription with explicit trust boundary, extending the
established shared integer-helper certificate to the paired Horner schedule.
"""
import argparse
from pathlib import Path
import h1699_candidate_carrier_bounds as bound
from h1713_promoted_regression import SOURCE, HEADER
from h1709_paired_retained_census import digest, save


def fused(g,x,y,c,name):
    emin=x.e_lo+y.e_lo;emax=x.e_hi+y.e_hi;scale=min(emin,c.e_lo)
    shift=max(emax-scale,c.e_hi-scale)
    width=max(x.width+y.width+emax-scale,c.width+c.e_hi-scale)+1
    assert 0<=shift<256 and width<=255 and -(1<<31)<scale<1<<31
    values=[a*b for a in (x.lo,x.hi) for b in (y.lo,y.hi)]
    g.events.append(dict(name=name,kind='exact_product_plus_coefficient',accumulator_bits=width,
        alignment_shift_max=shift,scale_min=scale,scale_max=min(emax,c.e_hi)))
    return bound.quantized(min(values)+c.lo,max(values)+c.hi,64,'rn')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True,type=Path);p.add_argument('--output-dir',required=True,type=Path)
    a=p.parse_args();root=a.root.resolve();out=a.output_dir.resolve();assert not out.exists()
    assert digest(root/'src/fsincos_skylake.c')==SOURCE and digest(root/'src/general/paired.h')==HEADER
    c,_=bound.constants(root);cases=[]
    for e in range(-32,-2):
        g=bound.Graph(dict(residual_binade=e));r=bound.Carrier(bound.p2(e),bound.p2(e+1),e-63,e-63,64)
        square=g.product(r,r,name='square');states=[]
        for name in ('S6','C6'):
            state=c[name][6]
            for i in (5,4,3,2):state=fused(g,state,square,c[name][i],name+str(i))
            state=g.product(state,square,name=name+'.last_product')
            state=g.add(state,c[name][1],name=name+'.last_add');states.append(state)
        ps=g.product(states[0],square,64,'rn','sine_RN64_product')
        tails=[g.product(ps,r,name='sine_tail'),g.product(states[1],square,name='cosine_tail')]
        endpoints=[g.final(r,tails[0],'sine_final'),g.final(bound.ONE,tails[1],'cosine_final')]
        cases.append(dict(domain=g.domain,events=g.events,endpoints=endpoints))
    events=[v for case in cases for v in case['events']]
    out.mkdir(parents=True);save(out/'cases.json',cases)
    report=dict(experiment='h1713_paired_carrier_bounds',status='PASS_PAIRED_POLYNOMIAL_INTERVAL_BOUNDS',
        binades=len(cases),operation_checks=len(events),maximum_accumulator_bits=max(v['accumulator_bits'] for v in events),
        maximum_alignment_shift=max(v['alignment_shift_max'] for v in events),
        scale_min=min(v['scale_min'] for v in events),scale_max=max(v['scale_max'] for v in events),
        scope='Every normalized64-bit polynomial residual 2^-32<=r<1/4; exact fixed-sign interval enclosure. Products, both signed addends and C1 reencoding fit signed256. Source-backed transcription and established helper/reducer contracts are trusted; no universal silicon claim.',
        hardware_execution='none',sha256=dict(source=SOURCE,header=HEADER,script=digest(Path(__file__)),
            interval_helpers=digest(Path(bound.__file__)),cases=digest(out/'cases.json')))
    save(out/'report.json',report);print({k:v for k,v in report.items() if k!='sha256'})


if __name__=='__main__':main()
