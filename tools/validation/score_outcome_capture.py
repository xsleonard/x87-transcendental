"""Authenticate a completed one-attempt capture and compare frozen predictions.

No hardware execution or source mutation. Preserve failures as evidence rather
than regenerating predictions after observing outcomes.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/regression'))
import outcomes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    parser.add_argument('--predictions',type=Path)
    args=parser.parse_args();job=args.directory
    receipt=json.loads((job/'COMPLETE.json').read_text())
    raw=gzip.decompress((job/'hardware.txt.gz').read_bytes())
    assert hashlib.sha256(raw).hexdigest()==receipt['hardware_sha256']
    inputs=gzip.decompress((job/'inputs.txt.gz').read_bytes()).decode().splitlines()
    path=args.predictions or job/'predictions.txt'
    if not args.predictions:
        frozen=json.loads((job/'FROZEN.json').read_text())
        assert hashlib.sha256(path.read_bytes()).hexdigest()==frozen['predictions_sha256']
    predicted=path.read_text().splitlines();observed=raw.decode().splitlines()
    assert len(inputs)==len(predicted)==len(observed)==receipt['rows']
    counts=Counter();failures=[];cases=[]
    for index,(request,line,prediction) in enumerate(zip(inputs,observed,predicted)):
        f=line.split();r=request.split();assert f[0]==r[0]==prediction.split()[0]
        case=dict(id=f[0],op=r[1],before=f[1],after=f[2],fault_at=int(f[3]),
                  cc_mask=0x600 if r[1] in outcomes.TRIG else 0x200,
                  evidence='hardware full state',source='outcomes-v1/hardware.txt.gz',source_id=f[0])
        if outcomes.u16(bytes.fromhex(f[2]),2)&0x400 and r[1] in outcomes.TRIG:case['cc_mask']=0x400
        cases.append(case)
        try:
            fields=prediction.split();fields[0]='0'
            outcomes.check([case],[' '.join(fields)],Counter())
            cw=outcomes.u16(bytes.fromhex(f[1]),0)
            sw=outcomes.u16(bytes.fromhex(f[2]),2)
            assert int(f[3])==(2 if sw&~cw&63 else 0),('fault delivery',f[3])
            counts[r[1]]+=1
        except AssertionError as error:
            failures.append(dict(id=f[0],request=request,prediction=prediction,error=str(error),
                                 observed_sw=f'{outcomes.u16(bytes.fromhex(f[2]),2):04x}',
                                 primary=outcomes.operand(bytes.fromhex(f[2]),int(r[1] in outcomes.PAIRED))))
    result=dict(status='FAIL' if failures else 'PASS',rows=len(cases),passed=counts,
                failure_count=len(failures),failures=failures,
                predictions_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),hardware_sha256=receipt['hardware_sha256'])
    suffix='FROZEN-COMPARISON' if not args.predictions else 'CURRENT-COMPARISON'
    with (job/(suffix+'.json')).open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    with (job/(suffix+'-states.json')).open('x') as stream:json.dump(dict(cases=cases),stream)
    print(json.dumps({k:v for k,v in result.items() if k!='failures'},indent=2))


if __name__=='__main__':main()
