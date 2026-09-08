"""Public durable FPTAN one-shot guard. Reserved/uncertain tuples never retry."""
import fcntl
import gzip
import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import threading
import time

from protocol import parse, validate_output
from support import digest, read, save


def reserve(base, job, context, manifest):
    db = sqlite3.connect(base / 'ledger.sqlite')
    db.execute('PRAGMA synchronous=FULL')
    db.execute('CREATE TABLE IF NOT EXISTS tuples(context TEXT, key TEXT, job TEXT, PRIMARY KEY(context,key))')
    db.execute('CREATE TABLE IF NOT EXISTS batches(context TEXT, job TEXT, rows INTEGER, state TEXT, PRIMARY KEY(context,job))')
    db.commit()
    try:
        db.execute('BEGIN IMMEDIATE')
        assert not db.execute('SELECT 1 FROM batches WHERE context=? AND job=?', (context, job.name)).fetchone()
        count = 0
        with gzip.open(job / 'inputs.txt.gz', 'rt') as stream:
            for line in stream:
                db.execute('INSERT INTO tuples VALUES(?,?,?)', (context, parse(line), job.name))
                count += 1
        assert count == manifest['rows'] and count
        db.execute('INSERT INTO batches VALUES(?,?,?,?)', (context, job.name, count, 'RESERVED'))
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def run(base, job):
    assert not (job / 'STARTED.json').exists()
    manifest = read(job / 'MANIFEST.json')
    assert manifest['status'] == 'FROZEN_UNOPENED'
    for name in ('capture.c', 'protocol.py', 'support.py', 'guard.py'):
        assert digest(job / name) == manifest['public_sources'][name]
    assert digest(job / 'inputs.txt.gz') == manifest['files']['inputs.txt.gz']
    assert read(job / 'CLEARANCE.json')['status'] == 'CLEARED_COMMON_TWO_HOST_INPUTS'
    assert digest(job / 'CLEARANCE.json') == manifest['clearance_sha256']
    assert shutil.disk_usage(base).free > 5 * (job / 'inputs.txt.gz').stat().st_size + 64 * (1 << 20)
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    identity = subprocess.check_output([str(job / 'capture'), '--identity'], text=True).strip()
    assert identity.split()[1] == manifest['signature']
    microcodes = {line.split(':', 1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('microcode')}
    assert microcodes == {manifest['microcode']}
    context = manifest['signature'] + ':' + manifest['microcode']
    reserve(base, job, context, manifest)
    save(job / 'STARTED.json', dict(state='RESERVED_DO_NOT_RETRY', rows=manifest['rows'],
        time=time.time(), identity=identity, microcode=sorted(microcodes),
        manifest_sha256=digest(job / 'MANIFEST.json'), capture_sha256=digest(job / 'capture')))
    errors, count, rawhash = [], 0, hashlib.sha256()
    with (job / 'hardware.stderr').open('xb') as err, (job / 'hardware.txt.gz').open('xb') as raw:
        child = subprocess.Popen([str(job / 'capture')], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err)
        def feed():
            try:
                with gzip.open(job / 'inputs.txt.gz', 'rb') as source:
                    shutil.copyfileobj(source, child.stdin, 1 << 20)
                child.stdin.close()
            except BaseException as error:
                errors.append(type(error).__name__)
        writer = threading.Thread(target=feed)
        writer.start()
        try:
            with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as output, gzip.open(job / 'inputs.txt.gz', 'rt') as source:
                for expected in source:
                    observed = child.stdout.readline()
                    assert observed, 'Incomplete capture: no retry'
                    validate_output(observed.decode('ascii'), expected)
                    output.write(observed)
                    rawhash.update(observed)
                    count += 1
                assert not child.stdout.read(1), 'Extra output'
            writer.join()
            assert child.wait() == 0 and not errors
        except BaseException:
            child.terminate()
            writer.join()
            child.wait()
            raise
        finally:
            child.stdout.close()
        raw.flush()
        os.fsync(raw.fileno())
    assert count == manifest['rows']
    assert (job / 'hardware.stderr').read_text() == f'COMPLETE {count}\n'
    db = sqlite3.connect(base / 'ledger.sqlite')
    db.execute('UPDATE batches SET state=? WHERE context=? AND job=?', ('OBSERVED', context, job.name))
    db.commit()
    integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
    recorded = db.execute('SELECT count(*) FROM tuples WHERE context=? AND job=?', (context, job.name)).fetchone()[0]
    db.close()
    assert integrity == 'ok' and recorded == count
    save(job / 'COMPLETE.json', dict(state='OBSERVED', rows=count, time=time.time(),
        hardware_sha256=rawhash.hexdigest(), hardware_gzip_sha256=digest(job / 'hardware.txt.gz'),
        manifest_sha256=digest(job / 'MANIFEST.json'), ledger_integrity=integrity, reserved_rows=recorded))
    print('COMPLETE', count, 'one-shot FPTAN observations', flush=True)


if __name__ == '__main__':
    base = Path('/root/fptan-re')
    name = sys.argv[1]
    assert Path(name).name == name and name not in ('.', '..')
    with (base / 'capture.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        run(base, base / name)
