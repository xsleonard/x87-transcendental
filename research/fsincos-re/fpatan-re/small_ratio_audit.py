"""Localize small-ratio FPATAN on both immutable one-shot datasets.

Compare divider widths and bypass hypotheses as operation-level models.
No thresholds or corrections are promoted; every tested alternative is saved.
"""
import collections
import dataclasses
import json
from pathlib import Path
from graph_v2 import Graph,prevalue
from model import Policy,value,cut,encode,pow2,ROM,exponent
from protocol import validate_output
from prepare import save

BASE=Path(__file__).resolve().parents[1]/'tmp/fpatan-re'
BEST=Graph(arithmetic=dataclasses.replace(Policy(),denominator='chop67',direct_limit=32),reduction_mul='exact')


def data():
    out=collections.defaultdict(list)
    for job in ('d0001','d0002'):
        p=BASE/job
        for actual,line in zip((p/'hardware.txt').read_text().splitlines(),(p/'inputs.txt').read_text().splitlines()):
            t=line.split();key=tuple(int(s,16) for s in t[3:]);ys,ym,xs,xm=key
            y,x=abs(value(ys,ym)),abs(value(xs,xm));ratio=min(y,x)/max(y,x)
            if ratio>=pow2(-30):continue
            observed=validate_output(actual,line)
            out[key].append((job,t[1],observed))
    return out


def rotated(angle,ys,xs,swap):
    if swap or xs&0x8000:angle=cut(angle,'chop67')
    if swap:v=ROM[20]+(angle if xs&0x8000 else -angle)
    elif xs&0x8000:v=ROM[19]-angle
    else:v=angle
    return -v if ys&0x8000 else v


def main():
    records=data();summaries=[]
    # Collapse the software-only comparisons into cached rounded endpoints;
    # the original raw inputs and every hardware row stay unmodified.
    prepared=[]
    for key,rows in records.items():
        ys,ym,xs,xm=key;y,x=abs(value(ys,ym)),abs(value(xs,xm));swap=y>x
        r=min(y,x)/max(y,x);ordinary=prevalue(*key,dataclasses.replace(BEST,tiny=0))
        divs={s:rotated(cut(r,s),ys,xs,swap) for s in ('exact','chop64','chop65','chop66','chop67','rn64','rn67')}
        endpoints={s:{rc:encode(v,rc) for rc in ('rn','rd','ru','rz')} for s,v in divs.items()}
        endpoints['poly']={rc:encode(ordinary,rc) for rc in ('rn','rd','ru','rz')}
        prepared.append((exponent(r),endpoints,rows))
    for width in ('exact','chop64','chop65','chop66','chop67','rn64','rn67'):
        for threshold in (0,*range(30,81)):
            counts=collections.Counter();bins=collections.defaultdict(collections.Counter)
            for e,endpoints,rows in prepared:
                chosen=width if e < -threshold else 'poly'
                for job,rc,o in rows:
                    miss=endpoints[chosen][rc]!=(o['se'],o['sig'])
                    counts[job+'_rows']+=1;counts[job+'_misses']+=miss
                    bins[str(e)]['rows']+=1;bins[str(e)]['misses']+=miss
            summaries.append(dict(divider=width,threshold=threshold,counts=dict(counts),bins={k:dict(v) for k,v in bins.items()}))
    order=lambda r:sum(v for k,v in r['counts'].items() if k.endswith('_misses'))
    ranked=sorted(summaries,key=order)
    save(BASE/'small-ratio-audit.json',dict(status='DISCOVERY_ONLY_NO_THRESHOLD_PROMOTED',
        tested=len(summaries),best=ranked[:16],results=summaries,hardware_executed=False))
    print(json.dumps([{k:v for k,v in r.items() if k!='bins'} for r in ranked[:16]],indent=2))


if __name__=='__main__':main()
