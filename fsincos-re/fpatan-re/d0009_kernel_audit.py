"""Global kernel-read and coefficient-domain tests on saved counterexamples.

Every rejected program retains an actual counterexample. Survivors, if any,
are discovery-only and must next face the full saved corpus and fresh labels.
No boundary correction, operand selector or hardware capture is performed.
"""
import collections
import dataclasses
import gzip
import itertools
import json
from pathlib import Path
from d0008_operand_format_audit import Ports,restore
from graph_v5 import prevalue
from model import F,ROM,cut,encode,value
from prepare import save
from protocol import validate_output

BASE=Path(__file__).resolve().parents[1]/'tmp/fpatan-re'


def targets():
    out=collections.defaultdict(list)
    for job in ('d0008','d0009'):
        root=BASE/job
        with gzip.open(root/'candidate-misses.jsonl.gz','rt') as f:
            selected={tuple(json.loads(l)['input'].split()[3:]) for l in f}
        with gzip.open(root/'inputs.txt.gz','rt') as inputs,gzip.open(root/'hardware.txt.gz','rt') as hardware:
            for line,hw in itertools.zip_longest(inputs,hardware):
                assert line is not None and hw is not None
                t=line.split()
                if tuple(t[3:]) not in selected or t[2]!='64':continue
                ys,ym,xs,xm=(int(s,16) for s in t[3:]);shift=(xs&32767)-16383
                raw=((ys&32768)|((ys&32767)-shift),ym,(xs&32768)|16383,xm)
                h=validate_output(hw,line)
                out[raw].append(dict(input=line.strip(),rc=t[1],se=h['se'],sig=h['sig'],C1=h['C1']))
    data=[]
    for raw,rows in out.items():
        t={};prevalue(*raw,trace=t);data.append((raw,rows,t))
    # The original D0008 failures and the fresh table failure constrain ROM
    # choice first; direct cases then constrain polynomial reads.
    data.sort(key=lambda x:(x[2]['kind']!='table',x[2]['ratio']))
    return data


def kernel(z,p,coefficient_set,last_add):
    square=cut(cut(z,p.square_left)*cut(z,p.square_right),'chop67')
    low,high=(114,117) if coefficient_set=='short' else (118,123)
    h=ROM[high]
    for k in range(high-1,low-1,-1):
        h=cut(ROM[k]+cut(cut(square,p.horner_square)*h,'chop67'),last_add if k==low else 'rn64')
    product=cut(cut(square,p.tail_square)*h,'chop67')
    tail=cut(cut(product,p.tail_product)*cut(z,p.tail_z),'chop67')
    return z+tail


def check(p,domain,last,data):
    cache={};tested=0
    for raw,rows,t in data:
        z=t['z']
        short=(t['kind']=='table') if domain=='table' else (True if domain=='short' else
                abs(z)<F(1,int(domain)) if domain in ('64','32') else False)
        key=(z,short)
        if key not in cache:cache[key]=kernel(z,p,'short' if short else 'long',last)
        before=restore(cache[key],t,raw[0],raw[2])
        for r in rows:
            se,sig=encode(before,r['rc']);c1=int(abs(value(se,sig))>abs(before));tested+=1
            if (se,sig,c1)!=(r['se'],r['sig'],r['C1']):
                return dict(input=r['input'],predicted=[se,sig,c1],observed=[r['se'],r['sig'],r['C1']],tested_rows=tested)
    return None


def main():
    data=targets();save(BASE/'d0009-kernel-frontier.json',dict(pairs=[dict(raw=r,rows=rows) for r,rows,t in data],hardware_executed=False))
    reads=('exact','rn64','chop64');pairs=tuple(itertools.combinations_with_replacement(reads,2))
    results=[];survivors=[]
    for (a,b),hs,ts,tp,tz,domain,last in itertools.product(pairs,reads,reads,reads,reads,
             ('table','long','short','64','32'),('rn64','chop67','rn67')):
        p=Ports(square_left=a,square_right=b,horner_square=hs,tail_square=ts,tail_product=tp,tail_z=tz)
        failure=check(p,domain,last,data)
        r=dict(ports=dataclasses.asdict(p),coefficient_domain=domain,last_add=last,counterexample=failure)
        results.append(r)
        if failure is None:survivors.append(r);print('TARGET SURVIVOR',r,flush=True)
    print('programs',len(results),'survivors',len(survivors),'raw groups',len(data),'rows',sum(len(r) for _,r,_ in data),flush=True)
    save(BASE/'d0009-kernel-read-audit.json',dict(status='TARGET_SCREEN_ONLY',results=results,survivors=survivors,hardware_executed=False))


if __name__=='__main__':main()
