"""Public compressed one-shot capture guard; no model or private data.

Batch reservations retain every exact tuple in their immutable gzip input.
All prior legacy tuples AND all reserved/observed batch inputs are checked.
No old record is removed. A SQLite trigger rejects legacy-guard INSERTs once
batch reservations exist, so an old guard cannot bypass this new ledger.
"""
import argparse
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import struct
import subprocess
import threading
import time
from protocol import parse_line,validate_output,MODES


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()


def save(path,obj):
    with path.open('x') as f:
        json.dump(obj,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())


def packed(key):
    _,rc,pc,ys,ym,xs,xm=key.split(':')
    return struct.pack('>BBHQHQ',MODES.index(rc),int(pc),int(ys,16),int(ym,16),int(xs,16),int(xm,16))


def input_keys(path):
    with gzip.open(path,'rt',encoding='ascii') as f:
        for line in f:yield packed(parse_line(line))


def schema(db):
    db.execute('CREATE TABLE IF NOT EXISTS reservations(context TEXT,tuple TEXT,job TEXT,state TEXT,PRIMARY KEY(context,tuple))')
    db.execute('CREATE TABLE IF NOT EXISTS batch_reservations(context TEXT,job TEXT,input_sha256 TEXT,rows INTEGER,state TEXT,PRIMARY KEY(context,job))')
    db.execute("""CREATE TRIGGER IF NOT EXISTS require_batch_guard
        BEFORE INSERT ON reservations WHEN EXISTS(SELECT 1 FROM batch_reservations)
        BEGIN SELECT RAISE(ABORT,'Compressed batch ledger present; use current guard'); END""")
    db.commit()


def reserve(base,job,context,sha,rows):
    """Reserve all tuples atomically. Any subsequent failure forbids retry."""
    db=sqlite3.connect(base/'ledger.sqlite');db.execute('PRAGMA synchronous=FULL');schema(db)
    try:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT 1 FROM batch_reservations WHERE context=? AND job=?',(context,job.name)).fetchone():
            raise RuntimeError('Prior batch reservation; NO RETRY')
        previous={packed(k) for k, in db.execute('SELECT tuple FROM reservations WHERE context=?',(context,))}
        for name,oldsha,n in db.execute('SELECT job,input_sha256,rows FROM batch_reservations WHERE context=?',(context,)):
            if Path(name).name!=name or name in ('.','..'):raise RuntimeError('Invalid historical batch path')
            path=base/name/'inputs.txt.gz'
            if digest(path)!=oldsha:raise RuntimeError('Prior immutable input unavailable or changed; no capture')
            count=0
            for key in input_keys(path):previous.add(key);count+=1
            if count!=n:raise RuntimeError('Prior immutable row count mismatch')
        if digest(job/'inputs.txt.gz')!=sha:raise RuntimeError('New input hash mismatch')
        seen=set();count=0
        for key in input_keys(job/'inputs.txt.gz'):
            if key in previous or key in seen:raise RuntimeError('Repeated tuple; NO CAPTURE')
            seen.add(key);count+=1
        if count!=rows or not count:raise RuntimeError('New input count mismatch')
        db.execute('INSERT INTO batch_reservations VALUES(?,?,?,?,?)',(context,job.name,sha,rows,'RESERVED'))
        db.commit()
    except BaseException:
        db.rollback();db.close();raise
    db.close()


def run(base,job):
    manifest=json.loads((job/'MANIFEST.json').read_text());rows=manifest['rows']
    assert manifest['format']=='fpatan-gzip-v2' and manifest['status']=='FROZEN_DISCOVERY_UNOPENED'
    for name in ('capture.c','protocol.py','compressed_guard.py'):
        assert digest(job/name)==manifest['source_pins'][name]
    if (job/'STARTED.json').exists():raise RuntimeError('Prior start; NO RETRY')
    assert json.loads((job/'HISTORY.json').read_text())['status']=='NO_PRIOR_FPATAN_FOUND'
    # Room for compressed results, stderr/receipts, and an emergency margin.
    assert shutil.disk_usage(base).free >= 3*(job/'inputs.txt.gz').stat().st_size+64*(1<<20)
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    identity=subprocess.check_output([str(job/'capture'),'--identity'],text=True).strip()
    assert identity.split()[1]==manifest['expected_signature']
    cpu=Path('/proc/cpuinfo').read_text()
    microcodes={s.split(':',1)[1].strip() for s in cpu.splitlines() if s.startswith('microcode')}
    assert microcodes=={manifest['expected_microcode']}
    context=manifest['expected_signature']+':'+manifest['expected_microcode']
    reserve(base,job,context,manifest['files']['inputs.txt.gz'],rows)
    save(job/'STARTED.json',dict(state='RESERVED_DO_NOT_RETRY',rows=rows,time=time.time(),
        identity=identity,microcode=sorted(microcodes),cpuinfo=cpu,capture_sha256=digest(job/'capture'),
        manifest_sha256=digest(job/'MANIFEST.json'),affinity=sorted(os.sched_getaffinity(0))))
    errors=[];count=0;rawhash=hashlib.sha256()
    with (job/'hardware.stderr').open('xb') as err,(job/'hardware.txt.gz').open('xb') as dest:
        child=subprocess.Popen([str(job/'capture')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err)
        def feed():
            try:
                with gzip.open(job/'inputs.txt.gz','rb') as source:
                    shutil.copyfileobj(source,child.stdin,1<<20)
                child.stdin.close()
            except BaseException as e:errors.append(type(e).__name__)
        writer=threading.Thread(target=feed);writer.start()
        try:
            with gzip.GzipFile(filename='',mode='wb',fileobj=dest,mtime=0,compresslevel=6) as output,gzip.open(job/'inputs.txt.gz','rt',encoding='ascii') as source:
                for expected in source:
                    actual=child.stdout.readline()
                    if not actual:raise RuntimeError('Incomplete capture; preserve partial gzip, NO RETRY')
                    validate_output(actual.decode('ascii'),expected)
                    output.write(actual);rawhash.update(actual);count+=1
                if child.stdout.read(1):raise RuntimeError('Extra hardware output; NO RETRY')
            writer.join();rc=child.wait()
            if rc or errors:raise RuntimeError('Capture/input pipe failed; NO RETRY')
        except BaseException:
            child.terminate();writer.join();child.wait();raise
        finally:child.stdout.close()
        dest.flush();os.fsync(dest.fileno())
    assert count==rows and (job/'hardware.stderr').read_text()==f'COMPLETE {rows}\n'
    db=sqlite3.connect(base/'ledger.sqlite');db.execute('PRAGMA synchronous=FULL')
    db.execute('UPDATE batch_reservations SET state=? WHERE context=? AND job=?',('OBSERVED',context,job.name));db.commit();db.close()
    save(job/'COMPLETE.json',dict(state='OBSERVED',format='fpatan-gzip-v2',rows=rows,time=time.time(),
        hardware_sha256=rawhash.hexdigest(),hardware_gzip_sha256=digest(job/'hardware.txt.gz'),
        manifest_sha256=digest(job/'MANIFEST.json')))
    print('COMPLETE',rows,'compressed one-shot rows',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--job',required=True)
    a=p.parse_args();assert Path(a.job).name==a.job and a.job not in ('.','..')
    with (a.base/'capture.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);run(a.base,a.base/a.job)
