#!/usr/bin/env python3
"""Authenticate copied public input snapshots against a read-only remote digest."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',required=True,type=Path);a=p.parse_args()
    names=[f'comb{i}_inputs.txt' for i in range(3,20)]+['comb13n_inputs.txt','hostv1_inputs.txt','randv1_inputs.txt']
    script='''import hashlib,json
from pathlib import Path
names=NAMES
files={}
for name in names:
 p=Path('/root/h491')/name;h=hashlib.sha256();rows=0
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(1<<20),b''):
   h.update(chunk);rows+=chunk.count(b'\\n')
 files[name]=dict(sha256=h.hexdigest(),rows=rows,bytes=p.stat().st_size)
print(json.dumps(dict(host='142.132.217.243',remote_directory='/root/h491',files=files,hardware_executions=0),sort_keys=True))
'''.replace('NAMES',repr(names))
    proc=subprocess.run(['ssh','-o','BatchMode=yes','root@142.132.217.243','python3 -'],input=script,text=True,capture_output=True,check=True)
    assert not proc.stderr;record=json.loads(proc.stdout)
    for name,meta in record['files'].items():
        h=hashlib.sha256();rows=0
        with (a.directory/name).open('rb') as f:
            for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk);rows+=chunk.count(b'\n')
        assert h.hexdigest()==meta['sha256'] and rows==meta['rows'],name
    with (a.directory/'SNAPSHOT.json').open('x') as f:json.dump(record,f,indent=2,sort_keys=True)
    print('AUTHENTICATED',len(names),'banks',sum(x['rows'] for x in record['files'].values()),'input appearances')


if __name__=='__main__':main()
