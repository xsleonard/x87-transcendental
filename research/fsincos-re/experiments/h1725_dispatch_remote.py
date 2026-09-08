#!/usr/bin/env python3
"""Session-independent dispatch of ONE guarded H1725 capture; never retry it.

Only public capture orchestration is installed on the capture hosts. The
unchanged capture helper owns persistent tuple reservation and validation.
"""
import argparse
import base64
import fcntl
import gzip
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from h1725_remote_capture import syncsave


def state(job):
    result = {'job': job.name}
    packed = job.parent / 'receipts' / (job.name + '.json.gz')
    if packed.exists():
        with gzip.open(packed, 'rt') as f:
            archived = json.load(f)
        assert archived['job'] == job.name
        files = {n: base64.b64decode(v) for n, v in archived['files'].items()}
        for name in ('JOB.json', 'STARTED.json', 'COMPLETE.json', 'OFFLOADED.json'):
            result[name] = json.loads(files[name])
        result['state'] = 'CAPTURED'
        result['receipt_archive'] = str(packed)
        return result
    for name in ('JOB.json', 'STARTED.json', 'COMPLETE.json', 'FAILED.json',
                 'DISPATCHED.json', 'WORKER_EXIT.json', 'OFFLOADED.json'):
        if (job / name).exists():
            result[name] = json.loads((job / name).read_text())
    if 'COMPLETE.json' in result:
        result['state'] = 'CAPTURED'
    elif 'FAILED.json' in result or 'WORKER_EXIT.json' in result:
        result['state'] = 'FAILED_RESERVED_NO_RETRY'
    elif 'DISPATCHED.json' in result or 'STARTED.json' in result:
        result['state'] = 'IN_FLIGHT_OR_UNCERTAIN_NO_RETRY'
    else:
        result['state'] = 'UNATTEMPTED'
    return result


def compact(job):
    """Losslessly pack acknowledged metadata; retain a permanent remote copy.

    Numerical outputs/inputs already have checksum-verified local archives.
    Compaction avoids thousands of mostly empty filesystem blocks on the
    small reference host. No tuple reservation or ledger row is removed.
    """
    before = state(job)
    assert 'OFFLOADED.json' in before
    if 'DISPATCHED.json' in before:
        assert before.get('WORKER_EXIT.json', {}).get('returncode') == 0
    packed = job.parent / 'receipts' / (job.name + '.json.gz')
    packed.parent.mkdir(exist_ok=True)
    allowed = {'JOB.json', 'STARTED.json', 'COMPLETE.json', 'cpu.json', 'cpu-after.json',
               'OFFLOAD.json', 'OFFLOADED.json', 'DISPATCHED.json', 'WORKER_EXIT.json', 'worker.log'}
    if not packed.exists():
        files = {}
        for path in job.iterdir():
            assert path.name in allowed and path.is_file() and not path.is_symlink(), path
            files[path.name] = base64.b64encode(path.read_bytes()).decode()
        temporary = packed.with_suffix('.pending')
        with temporary.open('xb') as raw:
            with gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as f:
                f.write(json.dumps(dict(job=job.name, files=files), sort_keys=True).encode())
            raw.flush(); os.fsync(raw.fileno())
        temporary.rename(packed)
    with gzip.open(packed, 'rt') as f:
        archived = json.load(f)
    assert archived['job'] == job.name
    if job.exists():
        for path in job.iterdir():
            assert path.name in allowed and path.is_file() and not path.is_symlink()
            assert path.read_bytes() == base64.b64decode(archived['files'][path.name])
        for path in list(job.iterdir()):
            path.unlink()
        job.rmdir()
    return dict(status='LOSSLESS_REMOTE_RECEIPTS_ARCHIVED', job=job.name, path=str(packed),
                sha256=hashlib.sha256(packed.read_bytes()).hexdigest())


def dispatch(base, job, binary, ledger):
    with (base / 'dispatch.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        before = state(job)
        if before['state'] != 'UNATTEMPTED':
            return before
        # This marker precedes process creation. Even a crash in the gap must
        # stop for inspection, never silently repeat an uncertain instruction.
        syncsave(job / 'DISPATCHED.json', {'status': 'DO_NOT_REDISPATCH',
                 'job': job.name, 'dispatcher_pid': os.getpid()})
        with (job / 'worker.log').open('xb') as log:
            subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                'worker', '--base', str(base), '--job', job.name,
                '--binary', str(binary), '--ledger', str(ledger)],
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True, close_fds=True)
        return state(job)


def worker(base, job, binary, ledger):
    code = subprocess.call([sys.executable, str(base / 'h1725_remote_capture.py'),
        'capture', '--base', str(base), '--job', job.name,
        '--binary', str(binary), '--ledger', str(ledger)])
    syncsave(job / 'WORKER_EXIT.json', {'returncode': code, 'worker_pid': os.getpid()})
    return code


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('state', 'dispatch', 'worker', 'compact'))
    p.add_argument('--base', type=Path, required=True)
    p.add_argument('--job', required=True)
    p.add_argument('--binary', type=Path)
    p.add_argument('--ledger', type=Path)
    a = p.parse_args(); base = a.base.resolve(); job = base / a.job
    assert job.parent == base and job.name.startswith('job-')
    assert job.is_dir() or (base / 'receipts' / (job.name + '.json.gz')).is_file()
    if a.action == 'worker':
        raise SystemExit(worker(base, job, a.binary, a.ledger))
    if a.action == 'compact':
        with (base / 'dispatch.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            value = compact(job)
    else:
        value = state(job) if a.action == 'state' else dispatch(base, job, a.binary, a.ledger)
    print(json.dumps(value), flush=True)
