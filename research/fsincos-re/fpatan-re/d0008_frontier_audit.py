"""Global polynomial-stage hypotheses on the five fresh failing pairs.

Never a selector: any survivor must next pass the complete opened corpus and
new frozen adversaries. Original D0008 predictions and labels are immutable.
"""
import collections
import dataclasses
import gzip
import itertools
import json
from pathlib import Path
from graph_v4 import PROGRAM
from graph_v3 import prevalue
from model import encode,value
from prepare import save
from protocol import validate_output

BASE=Path(__file__).resolve().parents[1]/'tmp/fpatan-re'


def targets():
    job=BASE/'d0008'
    with gzip.open(job/'candidate-misses.jsonl.gz','rt') as f:
        keys={tuple(json.loads(l)['input'].split()[3:]) for l in f}
    groups=collections.defaultdict(list)
    with gzip.open(job/'inputs.txt.gz','rt') as inputs,gzip.open(job/'hardware.txt.gz','rt') as hw:
        for i,h in zip(inputs,hw):
            t=i.split();key=tuple(t[3:])
            if key not in keys:continue
            raw=tuple(int(x,16) for x in key);ys,ym,xs,xm=raw;shift=(xs&32767)-16383
            normalized=((ys&32768)|((ys&32767)-shift),ym,(xs&32768)|16383,xm)
            o=validate_output(h,i)
            groups[normalized].append(dict(input=i.strip(),rc=t[1],se=o['se'],sig=o['sig'],C1=o['C1']))
    return groups


def score(program,data):
    c=collections.Counter();failures=[]
    for key,rows in data.items():
        before=prevalue(*key,program)
        for r in rows:
            se,sig=encode(before,r['rc']);c1=int(abs(value(se,sig))>abs(before))
            om=(se,sig)!=(r['se'],r['sig']);cm=c1!=r['C1']
            c['rows']+=1;c['output_misses']+=om;c['C1_misses']+=cm
            if om or cm:failures.append(dict(input=r['input'],output=om,C1=cm))
    return dict(program=dataclasses.asdict(program),counts=dict(c),failures=failures)


def main():
    data=targets();results=[]
    save(BASE/'d0008-frontier.json',dict(pairs=[dict(raw=k,rows=v) for k,v in data.items()],baseline=score(PROGRAM,data),hardware_executed=False))
    for square,first,last,order in itertools.product(('chop67','rn64','rn67','exact'),
            ('chop67','rn64','chop64','rn67','exact'),('chop67','rn64','chop64','rn67','exact'),
            ('square-h-z','z-h-square','square-z-h')):
        p=dataclasses.replace(PROGRAM,square_cut=square,tail_first=first,tail_second=last,tail_order=order)
        result=score(p,data);results.append(result)
    results.sort(key=lambda r:r['counts']['output_misses']+r['counts']['C1_misses'])
    zero=[r for r in results if not (r['counts']['output_misses'] or r['counts']['C1_misses'])]
    print('programs',len(results),'target-exact',len(zero),'best',[(r['counts'],{k:r['program'][k] for k in ('square_cut','tail_first','tail_second','tail_order')}) for r in results[:12]],flush=True)
    save(BASE/'d0008-polynomial-stage-audit.json',dict(status='TARGET_SCREEN_ONLY_NOT_VALIDATED',results=results,zero_target_misses=zero,hardware_executed=False))


if __name__=='__main__':main()
