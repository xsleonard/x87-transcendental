"""Authenticated software replay of saved logarithm evidence; no hardware run."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
from model import predict_full
from protocol import validate_inputs,validate_output

HERE=Path(__file__).resolve().parent


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('jobs',nargs='+',type=Path)
    p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--python-stride',type=int,default=1);a=p.parse_args()
    assert a.python_stride>=1
    report=dict(status='AUTHENTICATED_LOGARITHM_REPLAY',source_sha256=digest(HERE/'log_model.c'),
        python_sha256=digest(HERE/'model.py'),candidate_sha256=digest(a.candidate),jobs=[],totals={})
    total=Counter()
    for job in a.jobs:
        manifest=json.loads((job/'MANIFEST.json').read_text());complete=json.loads((job/'COMPLETE.json').read_text())
        started=json.loads((job/'STARTED.json').read_text())
        assert complete['state']=='OBSERVED'
        assert digest(job/'MANIFEST.json')==complete['manifest_sha256']==started['manifest_sha256']
        for name,want in manifest['files'].items():assert digest(job/name)==want
        for name,want in manifest['source_pins'].items():assert digest(job/'sources'/name)==want
        assert digest(job/'hardware.txt')==complete['hardware_sha256']
        assert started['identity'].split()[1]==manifest['expected_signature']=='00050654'
        assert started['microcode']==[manifest['expected_microcode']]==['0x1']
        raw=(job/'inputs.txt').read_text();inputs,_=validate_inputs(raw)
        hardware=(job/'hardware.txt').read_text().splitlines()
        process=subprocess.run([str(a.candidate.resolve())],input=raw,text=True,capture_output=True,check=True)
        predictions=process.stdout.splitlines()
        assert len(inputs)==len(hardware)==len(predictions)==manifest['rows']==complete['rows']
        counts=Counter();examples=[]
        for i,(source,line,pred) in enumerate(zip(inputs,hardware,predictions)):
            h=validate_output(line,source);t=pred.split();s=source.split();assert t[0]==s[0]
            want=(h['se'],h['sig'],h['C1'],h['sw']&63,h['before']&63)
            got=(int(t[1],16),int(t[2],16),int(t[3]),int(t[4],16),int(t[5],16))
            counts['rows']+=1;counts[s[1]]+=1;counts['rc:'+s[2]]+=1;counts['pc:'+s[3]]+=1
            for n,(x,y) in enumerate(zip(got,want)):
                if x!=y:counts[('se','sig','C1','exception','preload')[n]+'_misses']+=1
            if got!=want and len(examples)<8:examples.append(dict(input=source,got=got,want=want))
            if i%a.python_stride==0:
                independent=(*predict_full(source),0);counts['independent_rows']+=1
                if independent!=want:counts['independent_misses']+=1
        record=dict(job=job.name,counts=dict(counts),examples=examples,
            current_c_identical_to_frozen=manifest['source_pins'].get('log_model.c')==report['source_sha256'],
            inputs_sha256=manifest['files']['inputs.txt'],hardware_sha256=complete['hardware_sha256'],
            manifest_sha256=complete['manifest_sha256'],signature='00050654',microcode='0x1')
        report['jobs'].append(record);total.update(counts)
        print(job.name,json.dumps(dict(counts)),flush=True)
    report['totals']=dict(total)
    if any(v for k,v in total.items() if k.endswith('_misses')):report['status']='REPLAY_MISMATCHES'
    a.out.write_text(json.dumps(report,indent=2)+'\n')
    print(report['status'],dict(total),flush=True)


if __name__=='__main__':main()
