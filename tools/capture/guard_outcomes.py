"""Durably reserve and execute a frozen outcome campaign exactly once.

Started, incomplete and uncertain batches retain every reservation. A failed
run is not retried. This guard accepts only public sources and cleared inputs.
"""
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,data):
    with path.open('x') as stream:
        json.dump(data,stream,indent=2,sort_keys=True);stream.write('\n')
        stream.flush();os.fsync(stream.fileno())


def main():
    job=Path(sys.argv[1]).resolve()
    with (job.parent/'capture.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        manifest=json.loads((job/'MANIFEST.json').read_text())
        assert manifest['status']=='FROZEN_CLEARED'
        for name,sha in manifest['files'].items():assert digest(job/name)==sha,name
        assert not (job/'STARTED.json').exists(),'no retry'
        identity=subprocess.check_output([str(job/'capture'),'--identity'],text=True).strip()
        assert identity=='CPUID '+manifest['signature']
        microcodes={s.split(':',1)[1].strip() for s in Path('/proc/cpuinfo').read_text().splitlines() if s.startswith('microcode')}
        assert microcodes=={manifest['microcode']}
        lines=gzip.decompress((job/'inputs.txt.gz').read_bytes()).decode().splitlines()
        assert len(lines)==manifest['rows'] and lines
        context=identity+':'+manifest['microcode']
        db=sqlite3.connect(job.parent/'ledger.sqlite')
        db.execute('PRAGMA synchronous=FULL')
        db.execute('CREATE TABLE IF NOT EXISTS tuples(context TEXT, key TEXT, job TEXT, PRIMARY KEY(context,key))')
        db.execute('CREATE TABLE IF NOT EXISTS batches(context TEXT, job TEXT, state TEXT, PRIMARY KEY(context,job))')
        db.commit()
        try:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT INTO batches VALUES(?,?,?)',(context,job.name,'RESERVED'))
            for line in lines:
                f=line.split();assert len(f)==9
                db.execute('INSERT INTO tuples VALUES(?,?,?)',(context,' '.join(f[1:]),job.name))
            db.commit()
        except BaseException:
            db.rollback();raise
        save(job/'STARTED.json',dict(state='RESERVED_DO_NOT_RETRY',time=time.time(),rows=len(lines),
             manifest_sha256=digest(job/'MANIFEST.json'),capture_sha256=digest(job/'capture'),identity=identity))
        os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
        # communicate drains stdout while feeding input, avoiding pipe deadlocks.
        run=subprocess.run([str(job/'capture')],input=('\n'.join(lines)+'\n').encode(),capture_output=True)
        with (job/'hardware.txt.gz').open('xb') as stream:
            with gzip.GzipFile(filename='',mode='wb',fileobj=stream,mtime=0) as zipped:zipped.write(run.stdout)
            stream.flush();os.fsync(stream.fileno())
        with (job/'hardware.stderr').open('xb') as stream:stream.write(run.stderr)
        assert run.returncode==0,('incomplete capture; do not retry',run.returncode)
        observed=run.stdout.decode().splitlines()
        assert len(observed)==len(lines)
        for expected,line in zip(lines,observed):
            f=line.split();assert len(f)==5 and f[0]==expected.split()[0]
            assert len(f[1])==len(f[2])==1024 and f[3] in ('0','1','2')
            assert f[4]=='-' if f[3]=='0' else len(f[4])==1024
        assert run.stderr.decode()==f'COMPLETE {len(lines)}\n'
        db.execute('UPDATE batches SET state=? WHERE context=? AND job=?',('OBSERVED',context,job.name));db.commit()
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        db.close()
        save(job/'COMPLETE.json',dict(state='OBSERVED',rows=len(lines),time=time.time(),
             hardware_sha256=hashlib.sha256(run.stdout).hexdigest(),hardware_gzip_sha256=digest(job/'hardware.txt.gz'),
             manifest_sha256=digest(job/'MANIFEST.json'),ledger_integrity='ok'))
        print('COMPLETE',len(lines),'one-attempt outcome observations')


if __name__=='__main__':main()
