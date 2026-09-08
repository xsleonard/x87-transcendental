"""Public one-shot FPATAN guard. No model or private material is accepted.

Never retry after STARTED/reservation, including after partial or absent output.
The permanent tuple ledger survives all captures and future jobs.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import time
from protocol import validate_inputs,validate_output


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path,obj):
    with path.open('x') as f:json.dump(obj,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())


def run(base,job):
    manifest=json.loads((job/'MANIFEST.json').read_text())
    assert manifest['status']=='FROZEN_DISCOVERY_UNOPENED'
    assert digest(job/'inputs.txt')==manifest['files']['inputs.txt']
    assert digest(job/'capture.c')==manifest['source_pins']['capture.c']
    assert digest(job/'protocol.py')==manifest['source_pins']['protocol.py']
    lines,keys=validate_inputs((job/'inputs.txt').read_text())
    assert len(lines)==manifest['rows']
    if (job/'STARTED.json').exists():raise RuntimeError('Prior start; NO RETRY')
    audit=json.loads((job/'HISTORY.json').read_text())
    assert audit['status']=='NO_PRIOR_FPATAN_FOUND' and audit['hardware_executed'] is False
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    identity=subprocess.check_output([str(job/'capture'),'--identity'],text=True).strip()
    assert identity.split()[1]==manifest['expected_signature']
    cpu=Path('/proc/cpuinfo').read_text()
    microcodes={s.split(':',1)[1].strip() for s in cpu.splitlines() if s.startswith('microcode')}
    assert microcodes=={manifest['expected_microcode']}
    context=manifest['expected_signature']+':'+manifest['expected_microcode']
    db=sqlite3.connect(base/'ledger.sqlite');db.execute('PRAGMA synchronous=FULL')
    db.execute('CREATE TABLE IF NOT EXISTS reservations(context TEXT,tuple TEXT,job TEXT,state TEXT,PRIMARY KEY(context,tuple))')
    db.execute('BEGIN IMMEDIATE')
    for key in keys:
        if db.execute('SELECT 1 FROM reservations WHERE context=? AND tuple=?',(context,key)).fetchone():
            raise RuntimeError('Tuple already reserved; NO RETRY')
    db.executemany('INSERT INTO reservations VALUES(?,?,?,?)',[(context,k,job.name,'RESERVED') for k in keys]);db.commit()
    save(job/'STARTED.json',dict(state='RESERVED_DO_NOT_RETRY',rows=len(lines),time=time.time(),
        identity=identity,microcode=sorted(microcodes),cpuinfo=cpu,capture_sha256=digest(job/'capture'),
        manifest_sha256=digest(job/'MANIFEST.json'),affinity=sorted(os.sched_getaffinity(0))))
    with (job/'inputs.txt').open('rb') as source,(job/'hardware.txt').open('xb') as output,(job/'hardware.stderr').open('xb') as err:
        result=subprocess.run([str(job/'capture')],stdin=source,stdout=output,stderr=err)
        output.flush();os.fsync(output.fileno())
    if result.returncode:raise RuntimeError('Capture failed; preserve partial result; NO RETRY')
    observed=(job/'hardware.txt').read_text().splitlines()
    assert len(observed)==len(lines)
    for row,expected in zip(observed,lines):validate_output(row,expected)
    assert (job/'hardware.stderr').read_text()==f'COMPLETE {len(lines)}\n'
    db.execute('UPDATE reservations SET state=? WHERE context=? AND job=?',('OBSERVED',context,job.name));db.commit();db.close()
    save(job/'COMPLETE.json',dict(state='OBSERVED',rows=len(lines),time=time.time(),
        hardware_sha256=digest(job/'hardware.txt'),manifest_sha256=digest(job/'MANIFEST.json')))
    print('COMPLETE',len(lines))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--job',required=True)
    a=p.parse_args();assert Path(a.job).name==a.job and a.job not in ('.','..')
    with (a.base/'capture.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);run(a.base,a.base/a.job)
