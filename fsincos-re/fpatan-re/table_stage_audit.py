"""Offline structural coefficient/denominator audit over all opened banks.

These are operation-wide hypotheses, never operand-specific repairs. A
discovery winner is not a recovered law until fresh prospective validation.
"""
import collections
import dataclasses
import itertools
from pathlib import Path
from model import value,encode,F
from graph_v3 import Program,prevalue
from protocol import validate_output
from prepare import save

BASE=Path(__file__).resolve().parents[1]/'tmp/fpatan-re'


def groups():
    data=collections.defaultdict(list)
    for job in ('d0001','d0002','d0003'):
        p=BASE/job
        for actual,line in zip((p/'hardware.txt').read_text().splitlines(),(p/'inputs.txt').read_text().splitlines()):
            t=line.split();ys,ym,xs,xm=(int(s,16) for s in t[3:])
            y,x=abs(value(ys,ym)),abs(value(xs,xm));r=min(y,x)/max(y,x)
            if r<F(1,256):continue
            # Use the effective exponent for subnormals/pseudo-denormals.
            shift=max(xs&32767,1)-16383
            key=((ys&32768)|(max(ys&32767,1)-shift),ym,
                 (xs&32768)|16383,xm)
            assert value(key[0],ym)/value(key[2],xm)==value(ys,ym)/value(xs,xm)
            data[key].append((job,t[1],validate_output(actual,line),t[0]))
    return data


def score(p,data):
    counts=collections.Counter();misses=[]
    for key,rows in data.items():
        v=prevalue(*key,p)
        for job,rc,o,ident in rows:
            result=encode(v,rc);miss=result!=(o['se'],o['sig'])
            c1=int(abs(value(*result))>abs(v));cmiss=c1!=o['C1']
            counts[job+'_rows']+=1;counts[job+'_misses']+=miss;counts[job+'_C1_misses']+=cmiss
            if miss or cmiss:misses.append(dict(job=job,id=ident,rc=rc,raw=[f'{k:x}' for k in key],output=miss,C1=cmiss))
    return dict(program=dataclasses.asdict(p),counts=dict(counts),misses=misses)


def main():
    data=groups();results=[]
    for dispatch,coeff,den in itertools.product(('ratio32','ratio16','exponent'),('long','short'),('chop67','rn67','rn64','exact')):
        p=Program(direct_test='exponent' if dispatch=='exponent' else 'ratio',
                  direct_limit=16 if dispatch=='ratio16' else 32,
                  table_coefficients=coeff,denominator=den)
        result=score(p,data);results.append(result)
        print(dispatch,coeff,den,result['counts'],flush=True)
    results.sort(key=lambda x:sum(v for k,v in x['counts'].items() if k.endswith('_misses')))
    save(BASE/'table-stage-audit.json',dict(status='DISCOVERY_ONLY',results=results,best=results[:8],hardware_executed=False))


if __name__=='__main__':main()
