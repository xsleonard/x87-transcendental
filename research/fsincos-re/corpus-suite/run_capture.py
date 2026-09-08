#!/usr/bin/env python3
"""Run one frozen job once on x86, with a persistent per-CPU reservation ledger.

A partial/failed job remains reserved in full. There is deliberately no
--force, retry or reset-ledger option. Import all prior observations when
using an already tested CPU; a blank ledger does not prove global freshness.
"""
import argparse
import hashlib
import json
import os
import platform
import shutil
import sqlite3
import subprocess
from datetime import datetime,timezone
from pathlib import Path
import suite


def now():return datetime.now(timezone.utc).isoformat()


def identify(binary,logical_cpu,label):
    proc=subprocess.run([str(binary),'--identity'],text=True,capture_output=True,check=True)
    if proc.stderr:raise RuntimeError('capture identity emitted a diagnostic')
    rows=proc.stdout.splitlines();ident=[x.split() for x in rows if x.startswith('IDENTITY ')]
    if len(ident)!=1 or len(ident[0])!=7:raise ValueError('invalid CPU identity protocol')
    _,vendor,signature,family,model,stepping,hypervisor=ident[0]
    leaves={}
    for line in rows:
        words=line.split()
        if words[0]=='CPUID':
            if len(words)!=7:raise ValueError('invalid CPUID record')
            leaves[words[1]+':'+words[2]]=words[3:]
    microcode=None
    cpuinfo=Path('/proc/cpuinfo')
    if cpuinfo.is_file():
        for block in cpuinfo.read_text().split('\n\n'):
            fields=dict((k.strip(),v.strip()) for k,v in (line.split(':',1) for line in block.splitlines() if ':' in line))
            if fields.get('processor')==str(logical_cpu):microcode=fields.get('microcode');break
    context=dict(vendor=vendor,signature=signature,family=int(family),model=int(model),stepping=int(stepping),
        microcode=microcode,hypervisor_present=bool(int(hypervisor)),hypervisor_leaf=leaves.get('40000000:00000000'),
        core_type_leaf=leaves.get('0000001a:00000000'))
    key=hashlib.sha256(json.dumps(context,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return dict(schema='x87-cpu-context-v1',label=label,identity_kind='direct_reported_CPUID',context=context,
        context_id=key,cpuid_leaves=leaves,logical_cpu=logical_cpu,affinity_pinned=True,
        machine=platform.machine(),kernel_release=platform.release(),captured_utc=now(),
        limits='CPUID is reported identity, not proof of underlying physical silicon. Hypervisor and microcode differences remain separate contexts.')


def verify_prior_cpu(metadata,current):
    if metadata.get('identity_kind')=='direct_reported_CPUID':
        if metadata['context_id']!=current['context_id']:raise ValueError('prior observation CPU context differs')
    elif metadata.get('identity_kind')=='historical_reported_FMS':
        old=metadata['reported'];new=current['context']
        if old.get('vendor_id')!=new['vendor'] or any(int(old[k])!=new[v] for k,v in
            (('cpu family','family'),('model','model'),('stepping','stepping'))):raise ValueError('historical CPU FMS differs')
        if old.get('microcode') and old['microcode']!=new['microcode']:raise ValueError('historical microcode differs')
    else:raise ValueError('unrecognized prior CPU identity')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--job',type=Path,required=True)
    p.add_argument('--binary',type=Path,required=True);p.add_argument('--ledger',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--label',required=True)
    p.add_argument('--logical-cpu',type=int);p.add_argument('--known-observations',type=Path,nargs='*',default=[])
    a=p.parse_args();job=a.job.resolve();binary=a.binary.resolve();out=a.output.resolve()
    if out.exists():p.error('output already exists; never restart a partial capture')
    if not hasattr(os,'sched_getaffinity') or not hasattr(os,'sched_setaffinity'):p.error('this guarded runner requires Linux CPU affinity')
    allowed=os.sched_getaffinity(0);logical=a.logical_cpu if a.logical_cpu is not None else min(allowed)
    if logical not in allowed:p.error('logical CPU is not allowed by current affinity')
    os.sched_setaffinity(0,{logical})
    metadata=identify(binary,logical,a.label)
    spec=json.loads((job/'JOB.json').read_text())
    if suite.digest(job/'inputs.txt')!=spec['inputs_sha256']:raise ValueError('input checksum mismatch')
    if spec.get('binary_sha256') and suite.digest(binary)!=spec['binary_sha256']:
        raise ValueError('job-pinned capture binary checksum mismatch')
    cases=[]
    with (job/'inputs.txt').open() as f:
        for line in f:
            words=line.split()
            if len(words)!=9:raise ValueError('malformed input')
            case=words[0]
            if suite.capture_line(case)!=line.rstrip('\n'):raise ValueError('noncanonical capture tuple')
            cases.append(case)
    if len(cases)!=spec['rows'] or len(set(cases))!=len(cases):raise ValueError('duplicate or truncated input job')
    a.ledger.parent.mkdir(parents=True,exist_ok=True);db=sqlite3.connect(a.ledger)
    db.execute('PRAGMA synchronous=FULL')
    db.execute('CREATE TABLE IF NOT EXISTS reservations(cpu TEXT,case_id TEXT,state TEXT,source TEXT,PRIMARY KEY(cpu,case_id)) WITHOUT ROWID')
    db.execute('CREATE TABLE IF NOT EXISTS jobs(cpu TEXT,job_hash TEXT,state TEXT,output TEXT,PRIMARY KEY(cpu,job_hash)) WITHOUT ROWID')
    for prior in a.known_observations:
        suite.verify_dataset(prior);old=json.loads((prior/'cpu.json').read_text());verify_prior_cpu(old,metadata)
        prior_sha=suite.digest(prior/'MANIFEST.json')
        db.executemany('INSERT OR IGNORE INTO reservations VALUES(?,?,?,?)',
            ((metadata['context_id'],r['case_id'],'IMPORTED_OBSERVED',prior_sha) for r in suite.observations(prior)))
    db.commit();jobhash=suite.digest(job/'JOB.json')
    # Begin before checking overlap, so competing jobs cannot both see a
    # fresh tuple. Reserve the entire batch before the first target opcode.
    db.execute('BEGIN IMMEDIATE')
    try:
        db.execute('INSERT INTO jobs VALUES(?,?,?,?)',(metadata['context_id'],jobhash,'RESERVED',str(out)))
        db.executemany('INSERT INTO reservations VALUES(?,?,?,?)',
            ((metadata['context_id'],case,'RESERVED',jobhash) for case in cases))
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback();db.close();raise SystemExit('REFUSED: an input or job is already observed/reserved for this CPU context; no hardware executed')
    out.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(job/'inputs.txt',out/'inputs.txt');shutil.copyfile(job/'JOB.json',out/'JOB.json')
    binary_sha=suite.digest(binary)
    suite.save(out/'cpu.json',metadata);suite.save(out/'STARTED.json',dict(started_utc=now(),
        binary_sha256=binary_sha,source_job_sha256=jobhash,rows=len(cases),one_observation_maximum=True,
        partial_failure_policy='All tuples remain reserved, even after failure. No automatic retry.',
        ledger_scope='This persistent CPU context ledger plus explicitly imported observations; not an assertion of undisclosed global-history completeness.'))
    try:
        with (out/'inputs.txt').open('rb') as inputs,(out/'outputs.txt').open('xb') as outputs,(out/'stderr.txt').open('xb') as errors:
            result=subprocess.run([str(binary)],stdin=inputs,stdout=outputs,stderr=errors)
        if result.returncode or (out/'stderr.txt').stat().st_size:raise RuntimeError('capture exited with error or diagnostic')
        with (out/'outputs.txt').open() as f:
            for case in cases:
                insn,mode,pc,op=suite.decode_case(case)
                suite.validate_numeric(suite.parse_numeric(next(f)),insn,mode,pc,op,case)
            if f.readline():raise ValueError('excess output lines')
        after=identify(binary,logical,a.label)
        if after['context_id']!=metadata['context_id']:raise RuntimeError('CPU identity changed during capture')
        if suite.digest(binary)!=binary_sha:raise RuntimeError('capture binary changed during execution')
        suite.save(out/'cpu-after.json',after)
        suite.save(out/'COMPLETE.json',dict(status='OPENED_ONCE_DO_NOT_RERUN',rows=len(cases),completed_utc=now(),
            inputs_sha256=suite.digest(out/'inputs.txt'),outputs_sha256=suite.digest(out/'outputs.txt'),
            binary_sha256=suite.digest(binary),cpu_sha256=suite.digest(out/'cpu.json'),cpu_after_sha256=suite.digest(out/'cpu-after.json'),
            instruction_retries=0,affinity_pinned=True))
        db.execute('UPDATE jobs SET state=? WHERE cpu=? AND job_hash=?',('COMPLETE',metadata['context_id'],jobhash))
        db.execute('UPDATE reservations SET state=? WHERE cpu=? AND source=?',('OBSERVED',metadata['context_id'],jobhash));db.commit()
        print(json.dumps(dict(status='CAPTURED_ONCE',rows=len(cases),cpu_context=metadata['context_id'])))
    except BaseException as e:
        suite.save(out/'FAILED.json',dict(status='PARTIAL_OR_FAILED_DO_NOT_RERUN',time_utc=now(),error_type=type(e).__name__,all_tuples_remain_reserved=True))
        raise
    finally:db.close()


if __name__=='__main__':main()
