"""Freeze explicit alternative predictions before D0009 labels are opened.

Numeric schedule identifiers are local analysis only. All alternatives reuse
the same inputs and will be scored without executing any instruction again.
"""
import argparse
import collections
import gzip
import itertools
import json
from pathlib import Path
import subprocess
import threading
from compressed_guard import digest
from prepare import save
from protocol import validate_output

NAMES={0:'V4 long ROM and wide tail read',1:'short table ROM, wide tail read',
       2:'short table ROM, RN64 tail-z read',3:'V5 short table ROM, CHOP64 tail-z read',
       4:'short table ROM, CHOP64 first tail product',5:'short table ROM, CHOP67 last Horner add',
       6:'short table ROM, RN67 direct divider'}


def freeze(job,binary):
    assert not (job/'DISPATCHED.json').exists() and not (job/'hardware.txt.gz').exists()
    m=json.loads((job/'MANIFEST.json').read_text())
    for name,sha in m['files'].items():assert digest(job/name)==sha
    folder=job/'alternatives';folder.mkdir();entries={}
    for policy,name in NAMES.items():
        child=subprocess.Popen([str(binary),str(policy)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,text=True,bufsize=1<<20);errors=[]
        def feed():
            try:
                with gzip.open(job/'inputs.txt.gz','rt') as f:
                    for b in iter(lambda:f.read(1<<20),''):child.stdin.write(b)
                child.stdin.close()
            except BaseException as e:errors.append(repr(e))
        thread=threading.Thread(target=feed);thread.start();rows=0;path=folder/f'p{policy}.txt.gz'
        with gzip.open(path,'xt') as out,gzip.open(job/'predictions.txt.gz','rt') as main:
            for line,expected in itertools.zip_longest(child.stdout,main):
                assert line is not None and expected is not None
                assert line.split()[0]==expected.split()[0] and len(line.split())==6
                if policy==3:assert line==expected,'V5 C/Python parity'
                out.write(line);rows+=1
        thread.join();err=child.stderr.read();assert child.wait()==0 and not err and not errors
        assert rows==m['rows'];entries[str(policy)]=dict(name=name,file=path.name,sha256=digest(path),rows=rows)
        print('Frozen',policy,name,rows,flush=True)
    save(job/'ALTERNATIVES.json',dict(status='FROZEN_UNOPENED',policies=entries,
         binary_sha256=digest(binary),script_sha256=digest(Path(__file__)),
         manifest_sha256=digest(job/'MANIFEST.json'),hardware_labels_opened=False))


def score(job):
    m=json.loads((job/'ALTERNATIVES.json').read_text());complete=json.loads((job/'COMPLETE.json').read_text())
    assert digest(job/'MANIFEST.json')==m['manifest_sha256']==complete['manifest_sha256']
    assert digest(job/'hardware.txt.gz')==complete['hardware_gzip_sha256']
    results={}
    for policy,p in m['policies'].items():
        file=job/'alternatives'/p['file'];assert digest(file)==p['sha256'];counts=collections.Counter();examples=[]
        with gzip.open(file,'rt') as predictions,gzip.open(job/'hardware.txt.gz','rt') as hardware,gzip.open(job/'inputs.txt.gz','rt') as inputs:
            for pred,hw,line in itertools.zip_longest(predictions,hardware,inputs):
                assert None not in (pred,hw,line);obs=validate_output(hw,line);t=pred.split()
                assert t[0]==line.split()[0];se,sig,c1,flags,before=(int(s,16) for s in t[1:])
                om=(se,sig)!=(obs['se'],obs['sig']);cm=c1!=obs['C1'];fm=flags!=(obs['sw']&63);bm=before!=(obs['before']&63)
                counts.update(rows=1,output_misses=int(om),C1_misses=int(cm),exception_misses=int(fm),before_misses=int(bm))
                if om or cm or fm or bm:
                    if len(examples)<20:examples.append(dict(input=line.strip(),prediction=pred.strip(),hardware=hw.strip()))
        assert counts['rows']==p['rows']==complete['rows']
        results[policy]=dict(name=p['name'],counts=dict(counts),examples=examples)
        print(policy,p['name'],dict(counts),flush=True)
    save(job/'ALTERNATIVE-SCORE.json',dict(status='FROZEN_ALTERNATIVES_SCORED',results=results,hardware_executed=False,
         alternatives_sha256=digest(job/'ALTERNATIVES.json'),hardware_sha256=complete['hardware_sha256']))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('step',choices=('freeze','score'));ap.add_argument('--job',type=Path,required=True)
    ap.add_argument('--binary',type=Path);a=ap.parse_args()
    if a.step=='freeze':assert a.binary;freeze(a.job,a.binary)
    else:score(a.job)
