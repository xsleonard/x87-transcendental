#!/usr/bin/env python3
"""Bounded full-corpus one-shot capture with persistent compact reservations.

The fixed corpus ordinal and instruction/RC bit give a globally stable case
index within this immutable corpus. A bit is fsynced BEFORE execution and
never cleared. The original tuple ledger is checked and preserved. Receipts
link compressed public inputs/results to the durable local archive.
"""
import argparse
import fcntl
import gzip
import json
import mmap
import os
import shutil
import sqlite3
import struct
import subprocess
from pathlib import Path
import suite
from run_capture import identify, now

INSNS=('fsin','fcos','fsincos');MODES=('rn','rd','ru','rz')
CORPUS='x87-trig-v1-2126cf9ff5272e9d'
CASES=507477240
NBYTES=(CASES+7)//8


def syncsave(path,value):
    with path.open('x') as f:
        json.dump(value,f,sort_keys=True,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())


def reserve(bits,indices):
    if len(set(indices))!=len(indices):raise ValueError('duplicate index in batch')
    if any(i<0 or i>=CASES for i in indices):raise ValueError('case index out of range')
    if any(bits[i//8]&(1<<(i%8)) for i in indices):raise ValueError('previously reserved case; no retry')
    for i in indices:bits[i//8]=bits[i//8]|(1<<(i%8))


def run(base,job,binary,ledger):
    spec=json.loads((job/'JOB.json').read_text())
    if (job/'STARTED.json').exists() or (job/'COMPLETE.json').exists():raise ValueError('job already attempted; no retry')
    assert spec['corpus_id']==CORPUS and spec['pc']==64
    for name in ('inputs.txt.gz','indices.bin'):
        assert suite.digest(job/name)==spec['files'][name]
    assert suite.digest(binary)==spec['binary_sha256']
    if shutil.disk_usage(base).free<96*1024*1024:raise RuntimeError('insufficient safe disk headroom')
    allowed=os.sched_getaffinity(0);cpu=min(allowed);os.sched_setaffinity(0,{cpu})
    meta=identify(binary,cpu,spec['host'])
    assert meta['context_id']==spec['cpu_context_id']
    cases=[]
    with gzip.open(job/'inputs.txt.gz','rt') as f:
        for line in f:
            case=line.split()[0]
            assert suite.capture_line(case)+'\n'==line
            cases.append(case)
    raw=(job/'indices.bin').read_bytes();assert len(raw)==len(cases)*8
    indices=[x[0] for x in struct.iter_unpack('<Q',raw)]
    assert len(cases)==spec['rows'] and len(set(cases))==len(cases)
    assert indices==sorted(indices)
    for case,index in zip(cases,indices):
        insn,mode,pc,op=suite.decode_case(case)
        assert pc==64 and index%12==INSNS.index(insn)*4+MODES.index(mode)
    # Keep the old ledger authoritative for its existing rows. Its SQLite
    # lock also serializes this reservation against legacy guarded runners.
    old=sqlite3.connect(ledger);old.execute('BEGIN IMMEDIATE')
    for case in cases:
        if old.execute('SELECT 1 FROM reservations WHERE cpu=? AND case_id=?',(meta['context_id'],case)).fetchone():
            raise ValueError('case occurs in original ledger; no capture')
    bitpath=base/'RESERVED.bits'
    if not bitpath.exists():
        with bitpath.open('xb') as f:f.truncate(NBYTES);f.flush();os.fsync(f.fileno())
    assert bitpath.stat().st_size==NBYTES
    with bitpath.open('r+b') as f:
        bits=mmap.mmap(f.fileno(),NBYTES)
        reserve(bits,indices)
        lo=(min(indices)//8)//mmap.PAGESIZE*mmap.PAGESIZE
        hi=min(NBYTES,((max(indices)//8)//mmap.PAGESIZE+1)*mmap.PAGESIZE)
        bits.flush(lo,hi-lo);os.fsync(f.fileno());bits.close()
    old.execute('CREATE TABLE IF NOT EXISTS full_corpus_jobs(cpu TEXT,job_hash TEXT PRIMARY KEY,corpus_id TEXT,job_path TEXT,state TEXT)')
    jobhash=suite.digest(job/'JOB.json')
    old.execute('INSERT INTO full_corpus_jobs VALUES(?,?,?,?,?)',(meta['context_id'],jobhash,CORPUS,str(job),'RESERVED'))
    old.commit()
    syncsave(job/'cpu.json',meta)
    syncsave(job/'STARTED.json',dict(status='RESERVED_DO_NOT_RETRY',rows=len(cases),time=now(),
        job_sha256=jobhash,persistent_bits=str(bitpath),original_ledger=str(ledger)))
    try:
        # The reviewed capture binary remains unmodified. A gzip member is
        # completed on disk before any result transfer/acknowledgment.
        with gzip.open(job/'inputs.txt.gz','rb') as inputs,(job/'inputs.txt').open('xb') as out:
            shutil.copyfileobj(inputs,out)
        with (job/'inputs.txt').open('rb') as inputs,(job/'stderr.txt').open('xb') as err,gzip.open(job/'outputs.txt.gz','xb',compresslevel=1) as out:
            proc=subprocess.Popen([str(binary)],stdin=inputs,stdout=subprocess.PIPE,stderr=err)
            for case in cases:
                line=proc.stdout.readline()
                if not line:raise RuntimeError('short hardware output')
                insn,mode,pc,op=suite.decode_case(case)
                suite.validate_numeric(suite.parse_numeric(line.decode()),insn,mode,pc,op,case)
                out.write(line)
            if proc.stdout.read(1):raise RuntimeError('extra hardware output')
            if proc.wait():raise RuntimeError('capture process failed')
        if (job/'stderr.txt').stat().st_size:raise RuntimeError('capture diagnostic')
        after=identify(binary,cpu,spec['host'])
        assert after['context_id']==meta['context_id'] and suite.digest(binary)==spec['binary_sha256']
        syncsave(job/'cpu-after.json',after)
        syncsave(job/'COMPLETE.json',dict(status='OPENED_ONCE_DO_NOT_RERUN',rows=len(cases),instruction_retries=0,
            outputs_sha256=suite.digest(job/'outputs.txt.gz'),inputs_sha256=spec['files']['inputs.txt.gz'],
            cpu_context_id=meta['context_id'],binary_sha256=spec['binary_sha256'],completed=now()))
        old.execute('UPDATE full_corpus_jobs SET state=? WHERE job_hash=?',('OBSERVED',jobhash));old.commit()
        print(json.dumps(dict(status='CAPTURED_ONCE',rows=len(cases))),flush=True)
    except BaseException:
        if 'proc' in locals() and proc.poll() is None:
            # Interrupting a failed batch does not release any reservation.
            proc.terminate();proc.wait()
        syncsave(job/'FAILED.json',dict(status='FAILED_ALL_CASES_REMAIN_RESERVED',time=now()))
        raise
    finally:old.close()


def ack(job):
    receipt=json.loads((job/'OFFLOAD.json').read_text())
    assert (job/'COMPLETE.json').is_file()
    # Remove only exact scratch payloads after the local archive hashes have
    # been acknowledged. The reservation bitmap and metadata stay forever.
    for name in ('inputs.txt.gz','indices.bin','outputs.txt.gz','inputs.txt','stderr.txt'):
        path=job/name
        assert path.is_file() and suite.digest(path)==receipt['files'][name]
    syncsave(job/'OFFLOADED.json',dict(status='ARCHIVED_LOCALLY',receipt_sha256=suite.digest(job/'OFFLOAD.json')))
    for name in ('inputs.txt.gz','indices.bin','outputs.txt.gz','inputs.txt','stderr.txt'):
        (job/name).unlink()
    print('Archived scratch payloads released; reservations and receipts retained.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('capture','ack'))
    p.add_argument('--base',type=Path,required=True);p.add_argument('--job',required=True)
    p.add_argument('--binary',type=Path);p.add_argument('--ledger',type=Path)
    a=p.parse_args();base=a.base.resolve();job=base/a.job
    assert job.parent==base and job.is_dir()
    with (base/'campaign.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if a.action=='capture':run(base,job,a.binary.resolve(),a.ledger.resolve())
        else:ack(job)
