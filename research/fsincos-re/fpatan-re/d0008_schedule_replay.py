"""Stream named analysis C schedules against authenticated saved labels.

Read-only hardware reuse. Retain all mismatch rows and source/binary hashes.
The output report is exclusive-create and explicitly discovery-only.
"""
import argparse
import collections
import gzip
import hashlib
import itertools
import json
import subprocess
import threading
from pathlib import Path
from protocol import validate_output
from prepare import save

BASE = Path(__file__).resolve().parents[1] / 'tmp/fpatan-re'


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
    return h.hexdigest()


def opened(path):
    return gzip.open(path,'rt') if path.suffix=='.gz' else path.open()


def replay(binary, policy, job):
    root=BASE/job;compressed=(root/'inputs.txt.gz').exists()
    inp=root/('inputs.txt.gz' if compressed else 'inputs.txt')
    hw=root/('hardware.txt.gz' if compressed else 'hardware.txt')
    complete=json.loads((root/'COMPLETE.json').read_text())
    manifest=json.loads((root/'MANIFEST.json').read_text())
    assert digest(root/'MANIFEST.json')==complete['manifest_sha256']
    assert digest(inp)==manifest['files'][inp.name]
    errors=[]
    command = [str(binary)] if policy is None else [str(binary), str(policy)]
    child=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE,text=True,bufsize=1<<20)
    def feed():
        try:
            with opened(inp) as f:
                for block in iter(lambda:f.read(1<<20),''):child.stdin.write(block)
            child.stdin.close()
        except BaseException as error:errors.append(repr(error))
    thread=threading.Thread(target=feed);thread.start()
    counts=collections.Counter();misses=[];hardware_hash=hashlib.sha256();output_hash=hashlib.sha256()
    with opened(inp) as inputs,opened(hw) as hardware:
        for i,h,c in itertools.zip_longest(inputs,hardware,child.stdout):
            assert None not in (i,h,c),'length mismatch'
            o=validate_output(h,i);t=c.split();assert t[0]==i.split()[0] and len(t)==6
            se,sig,c1,flags,before=(int(s,16) for s in t[1:])
            om=(se,sig)!=(o['se'],o['sig']);cm=c1!=o['C1'];fm=flags!=(o['sw']&63);bm=before!=(o['before']&63)
            counts.update(rows=1,output_misses=int(om),C1_misses=int(cm),exception_misses=int(fm),before_misses=int(bm))
            if om or cm or fm or bm:misses.append(dict(input=i.strip(),candidate=c.strip(),hardware=h.strip(),output=om,C1=cm,exception=fm,before=bm))
            hardware_hash.update(h.encode());output_hash.update(c.encode())
    thread.join();stderr=child.stderr.read();assert child.wait()==0 and not errors and not stderr,(errors,stderr)
    assert hardware_hash.hexdigest()==complete['hardware_sha256']
    assert counts['rows']==complete['rows']
    return dict(counts=dict(counts),misses=misses,hardware_sha256=hardware_hash.hexdigest(),output_sha256=output_hash.hexdigest())


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--binary',type=Path,required=True)
    ap.add_argument('--policy',type=int,required=True);ap.add_argument('--jobs',nargs='+',required=True)
    ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    assert not a.out.exists();report=dict(status='OPENED_CORPUS_DISCOVERY_ONLY',hardware_executed=False,
        policy=a.policy,binary_sha256=digest(a.binary),sources={p:digest(Path(__file__).with_name(p)) for p in
        ('d0008_schedule_audit.c','fpatan_candidate.c','d0008_schedule_replay.py')},jobs={})
    for job in a.jobs:
        report['jobs'][job]=replay(a.binary,a.policy,job)
        print(a.policy,job,report['jobs'][job]['counts'],flush=True)
    save(a.out,report)


if __name__=='__main__':main()
