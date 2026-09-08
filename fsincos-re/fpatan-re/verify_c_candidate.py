"""Local C/Python parity; never executes the native FPATAN instruction."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import subprocess
from graph_v3 import prevalue
from model import encode, value
from protocol import validate_output
from prepare import save

BASE=Path(__file__).resolve().parents[1]/'tmp/fpatan-re'


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--binary',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--graph',choices=('v3','v4','architecture'),default='v3')
    ap.add_argument('--jobs',nargs='+',default=('d0001','d0002','d0003'))
    args=ap.parse_args()
    evaluator=prevalue
    if args.graph=='v4':
        from graph_v4 import prevalue as evaluator
    if args.graph=='architecture':
        from architecture import predict as architecture_predict
    report={'status':'IMPLEMENTATION_PARITY_NOT_HARDWARE_CLOSURE','graph':args.graph,
            'hardware_executed':False,'jobs':{},
            'binary_sha256':hashlib.sha256(args.binary.read_bytes()).hexdigest()}
    for job in args.jobs:
        p=BASE/job;inputs=(p/'inputs.txt').read_text()
        run=subprocess.run([str(args.binary)],input=inputs,text=True,capture_output=True,check=True)
        assert not run.stderr,run.stderr
        rows=run.stdout.splitlines();lines=inputs.splitlines()
        assert len(rows)==len(lines)
        cache={};counts=collections.Counter();examples=[]
        for actual,line,observed in zip(rows,lines,(p/'hardware.txt').read_text().splitlines()):
            ident,rc,pc,*raw=line.split();key=tuple(int(x,16) for x in raw)
            if args.graph=='architecture':
                se,sig,c1,flags,before=architecture_predict(*key,rc)
                expected=f'{ident} {se:04x} {sig:016x} {c1} {flags:02x} {before:02x}'
            else:
                if key not in cache:cache[key]=evaluator(*key)
                v=cache[key];se,sig=encode(v,rc);c1=int(abs(value(se,sig))>abs(v))
                expected=f'{ident} {se:04x} {sig:016x} {c1}'
            counts['rows']+=1;counts['C_Python_misses']+=actual!=expected
            if actual!=expected:examples.append({'input':line,'C':actual,'Python':expected})
            hw=validate_output(observed,line)
            counts['candidate_hardware_output_misses']+=(se,sig)!=(hw['se'],hw['sig'])
            counts['candidate_hardware_C1_misses']+=c1!=hw['C1']
            if args.graph=='architecture':
                counts['candidate_hardware_exception_misses']+=flags!=(hw['sw']&63)
                counts['candidate_hardware_before_exception_misses']+=before!=(hw['before']&63)
        if job=='d0003' and args.graph=='v3':
            counts['frozen_D3_prediction_differences']=sum(a!=b for a,b in
                zip(rows,(p/'predictions.txt').read_text().splitlines()))
        report['jobs'][job]={'counts':dict(counts),'parity_misses':examples,
            'output_sha256':hashlib.sha256(run.stdout.encode()).hexdigest()}
        print(job,dict(counts),flush=True)
    save(args.out,report)
    assert not any(j['counts']['C_Python_misses'] for j in report['jobs'].values())


if __name__=='__main__':main()
