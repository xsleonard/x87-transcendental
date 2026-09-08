#!/usr/bin/env python3
"""Resume the SAME frozen H1725 selection; reuse captures, never recapture.

Run under launchd, independently of the chat's tool sessions. Read-only
network transfers may retry; native instructions are dispatched at most
once behind both a persistent dispatch marker and the original tuple guard.
All interrupted files are preserved. No model, corpus or paper changes.
"""
import argparse
import collections
import fcntl
import gzip
import hashlib
import io
import json
import os
import shlex
import struct
import subprocess
import sys
import tarfile
import tempfile
import time
import traceback
from pathlib import Path
from h1725_full_campaign import BASE, ROOT, HOSTS, CORPUS, INSNS, MODES, PINS, save, suite
from h1725_run_full import REMOTE, CAPTURE, LEDGER, BINARY_SHA, predict, score

SSH_OPTIONS = ['-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15',
               '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3']
DOWNLOADS = ('outputs.txt.gz', 'COMPLETE.json', 'STARTED.json', 'cpu.json', 'cpu-after.json', 'stderr.txt')


def verify_execution_model(preflight, frozen=None, predictor=None):
    """Pin the campaign artifact, not the independently editable worktree.

    Prediction executes the original binary; it never rebuilds live C. The
    matching historical sources are retained separately for provenance.
    Editing F2XM1 (or any other live source) cannot change this experiment.
    Tampering with the actual predictor or its frozen provenance still stops
    before the next shard. Historical JOB/PREFLIGHT pins remain unchanged.
    """
    frozen = BASE / 'frozen-model' if frozen is None else frozen
    predictor = BASE / 'predictor' if predictor is None else predictor
    manifest = json.loads((frozen / 'MANIFEST.json').read_text())
    assert manifest['source_pins'] == preflight['source_pins'] == PINS
    assert manifest['predictor_sha256'] == preflight['predictor_sha256']
    assert suite.digest(predictor) == preflight['predictor_sha256'], 'frozen predictor changed'
    for name, sha in manifest['files'].items():
        path = frozen / name
        assert path.is_relative_to(frozen) and '..' not in Path(name).parts
        assert suite.digest(path) == sha, 'frozen provenance changed: ' + name
    for name, sha in PINS.items():
        assert manifest['files'][name] == sha


def event(out, stage, **extra):
    value = dict(stage=stage, updated_unix=time.time(), pid=os.getpid(), **extra)
    temporary = out / ('CONTROLLER.' + str(os.getpid()) + '.next.json')
    with temporary.open('w') as f:
        json.dump(value, f, indent=2, sort_keys=True); f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(temporary, out / 'CONTROLLER.json')
    print(json.dumps(value), flush=True)


def remote(host, command, data=None):
    # The caller uses this only for reads or idempotent guarded preparation.
    # A successful SSH command returning application failure is NOT retried.
    while True:
        try:
            result = subprocess.run(['ssh', *SSH_OPTIONS, 'root@' + HOSTS[host], command],
                input=data, capture_output=True, timeout=240)
        except subprocess.TimeoutExpired:
            print('SSH transport timeout; rechecking the same guarded operation', flush=True)
        else:
            if result.returncode == 0:
                return result.stdout
            if result.returncode != 255:
                raise RuntimeError(result.stderr.decode(errors='replace') + result.stdout.decode(errors='replace'))
            print('SSH unavailable; waiting 30 seconds. No native instruction retry.', flush=True)
        time.sleep(30)


def helper(host, action, name):
    command = ['python3', REMOTE + '/h1725_dispatch_remote.py', action,
               '--base', REMOTE, '--job', name]
    if action == 'dispatch':
        command += ['--binary', CAPTURE[host], '--ledger', LEDGER[host]]
    return json.loads(remote(host, shlex.join(command)))


def install_identical_or_new(path, source):
    if path.exists():
        if suite.digest(path) == suite.digest(source):
            return
        # Keep the old partial transfer or interrupted derived output intact.
        previous = path.with_name(path.name + '.interrupted-' + str(time.time_ns()))
        path.rename(previous)
    source.rename(path)


def download(host, job):
    data = remote(host, shlex.join(['tar', '-C', REMOTE + '/' + job.name, '-cf', '-', *DOWNLOADS]))
    stage = Path(tempfile.mkdtemp(prefix='download-', dir=job))
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as archive:
        members = archive.getmembers()
        assert {m.name for m in members} == set(DOWNLOADS) and len(members) == len(DOWNLOADS)
        for member in members:
            assert member.isfile()
            with (stage / member.name).open('xb') as f:
                f.write(archive.extractfile(member).read()); f.flush(); os.fsync(f.fileno())
    complete = json.loads((stage / 'COMPLETE.json').read_text())
    assert complete['outputs_sha256'] == suite.digest(stage / 'outputs.txt.gz')
    assert not (stage / 'stderr.txt').stat().st_size
    for name in DOWNLOADS:
            install_identical_or_new(job / name, stage / name)


def validate_frozen(job, records, host, selection, context):
    spec = json.loads((job / 'JOB.json').read_text())
    assert spec['host'] == host and spec['corpus_id'] == CORPUS and spec['pc'] == 64
    assert spec['cpu_context_id'] == context and spec['binary_sha256'] == BINARY_SHA
    assert spec['algorithm_pins'] == PINS and spec['frozen_before_capture'] is True
    assert spec['selection_sha256'] == selection['selected_sha256']
    for name, digest in spec['files'].items():
        assert name in ('inputs.txt.gz', 'indices.bin') and suite.digest(job / name) == digest
    assert suite.digest(job / 'predictions.json.gz') == spec['predictions_sha256']
    expected = []; indices = []
    for ordinal, se, sig, mask in records:
        for i in range(12):
            if mask & (1 << i):
                expected.append(suite.capture_line(suite.case_id(INSNS[i // 4], MODES[i % 4], 64, f'{se:04x} {sig:016x}')) + '\n')
                indices.append(ordinal * 12 + i)
    with gzip.open(job / 'inputs.txt.gz', 'rt') as f:
        assert f.readlines() == expected
    assert (job / 'indices.bin').read_bytes() == b''.join(struct.pack('<Q', i) for i in indices)
    assert spec['rows'] == len(expected)
    return spec


def validate_capture(job, spec):
    complete = json.loads((job / 'COMPLETE.json').read_text())
    assert complete['status'] == 'OPENED_ONCE_DO_NOT_RERUN' and complete['instruction_retries'] == 0
    assert complete['rows'] == spec['rows'] and complete['cpu_context_id'] == spec['cpu_context_id']
    assert complete['binary_sha256'] == BINARY_SHA
    assert complete['inputs_sha256'] == suite.digest(job / 'inputs.txt.gz')
    assert complete['outputs_sha256'] == suite.digest(job / 'outputs.txt.gz')


def ensure_download(host, job, spec):
    # A prior controller may have archived remote scratch before losing its
    # final local DONE write. In that state the authenticated LOCAL payload is
    # authoritative; requesting remote raw files again would be wrong.
    if (job / 'COMPLETE.json').exists() and (job / 'outputs.txt.gz').exists():
        complete = json.loads((job / 'COMPLETE.json').read_text())
        if complete['outputs_sha256'] == suite.digest(job / 'outputs.txt.gz'):
            validate_capture(job, spec)
            assert all((job / name).is_file() for name in DOWNLOADS)
            return
    download(host, job)
    validate_capture(job, spec)


def scored(job):
    result = json.loads((job / 'score.json').read_text())
    assert result['raw_sha256'] == suite.digest(job / 'outputs.txt.gz')
    assert result['prediction_sha256'] == suite.digest(job / 'predictions.json.gz')
    manifest = suite.verify_dataset(job / 'observations')
    assert manifest['rows'] == result['counts']['rows']
    return result


def score_recoverably(job):
    if (job / 'score.json').exists() and (job / 'observations/MANIFEST.json').exists():
        return scored(job)
    stage = Path(tempfile.mkdtemp(prefix='score-recovery-', dir=job))
    for name in ('inputs.txt.gz', 'outputs.txt.gz', 'predictions.json.gz', 'cpu.json', 'COMPLETE.json'):
        os.link(job / name, stage / name)
    with gzip.open(job / 'predictions.json.gz', 'rt') as f:
        predictions = json.load(f)
    score(stage, predictions)
    for name in ('score.json', 'observations'):
        if (job / name).exists():
            (job / name).rename(job / (name + '.interrupted-' + str(time.time_ns())))
        (stage / name).rename(job / name)
    return scored(job)


def upload_files(host, job, names):
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode='w:') as archive:
        for name in names:
            archive.add(job / name, arcname=name, recursive=False)
    # Uploads never include model sources, private data, or raw hardware labels.
    remote(host, shlex.join(['tar', '-C', REMOTE + '/' + job.name, '-xf', '-']), payload.getvalue())


def acknowledge(host, job):
    hashes = {name: suite.digest(job / name) for name in ('inputs.txt.gz', 'indices.bin', 'outputs.txt.gz', 'stderr.txt')}
    h = hashlib.sha256()
    with gzip.open(job / 'inputs.txt.gz', 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    hashes['inputs.txt'] = h.hexdigest()
    receipt = dict(files=hashes, local_archive_verified=True)
    if (job / 'OFFLOAD.json').exists():
        assert json.loads((job / 'OFFLOAD.json').read_text()) == receipt
    else:
        save(job / 'OFFLOAD.json', receipt)
    current = helper(host, 'state', job.name)
    if 'OFFLOADED.json' not in current:
        upload_files(host, job, ['OFFLOAD.json'])
        # Idempotent wrapper: after an uncertain SSH acknowledgment, inspect
        # its durable receipt instead of executing the deletion twice.
        script = "from pathlib import Path; import sys; sys.path.insert(0, %r); from h1725_remote_capture import ack; j=Path(%r); ack(j) if not (j/'OFFLOADED.json').exists() else None" % (REMOTE, REMOTE + '/' + job.name)
        remote(host, shlex.join(['python3', '-c', script]))
    packed = helper(host, 'compact', job.name)
    payload = remote(host, shlex.join(['cat', packed['path']]))
    assert hashlib.sha256(payload).hexdigest() == packed['sha256']
    archive = job / 'remote-receipts.json.gz'
    if archive.exists():
        assert archive.read_bytes() == payload
    else:
        with archive.open('xb') as f:
            f.write(payload); f.flush(); os.fsync(f.fileno())


def prepare_job(job, records, host, selection, context, predictor):
    job.mkdir()
    predictions = predict(job, records, predictor)
    with gzip.open(job / 'inputs.txt.gz', 'xt', compresslevel=1) as f, (job / 'indices.bin').open('xb') as idx:
        for ordinal, se, sig, mask in records:
            for i in range(12):
                if mask & (1 << i):
                    case = suite.case_id(INSNS[i // 4], MODES[i % 4], 64, f'{se:04x} {sig:016x}')
                    f.write(suite.capture_line(case) + '\n'); idx.write(struct.pack('<Q', ordinal * 12 + i))
    save(job / 'JOB.json', dict(corpus_id=CORPUS, host=host, pc=64, rows=len(predictions),
        cpu_context_id=context, binary_sha256=BINARY_SHA,
        files={n: suite.digest(job / n) for n in ('inputs.txt.gz', 'indices.bin')},
        predictions_sha256=suite.digest(job / 'predictions.json.gz'), selection_sha256=selection['selected_sha256'],
        first_ordinal=records[0][0], last_ordinal=records[-1][0], frozen_before_capture=True, algorithm_pins=PINS))


def run(host):
    out = BASE / host; started = time.time(); totals = collections.Counter(); recovered = 0
    # After the deliberate batch-boundary cutover the server owns all future
    # dispatch. A restarted Mac service must never compete with that owner.
    if (out / 'AUTONOMOUS_CUTOVER.json').exists():
        event(out, 'REMOTE_AUTONOMOUS_OWNER_NO_LOCAL_DISPATCH', host=host)
        return
    if (out / 'RESUME_STOPPED.json').exists():
        raise RuntimeError('A prior resumed controller stopped: inspect RESUME_STOPPED before any restart')
    selection = json.loads((out / 'SELECTION.json').read_text())
    assert selection['corpus_id'] == CORPUS and suite.digest(out / 'selected.bin') == selection['selected_sha256']
    preflight = json.loads((BASE / 'PREFLIGHT.json').read_text())
    assert preflight['status'] == 'PASS'
    verify_execution_model(preflight)
    for name, sha in preflight['files'].items():
        assert suite.digest(ROOT / 'experiments' / name) == sha
    predictor = BASE / 'predictor'; assert suite.digest(predictor) == preflight['predictor_sha256']
    contexts = {r[0] for r in json.loads((out / 'prior-ledger-0.json').read_text())['counts']}
    assert len(contexts) == 1; context = next(iter(contexts))
    event(out, 'VERIFYING_EXISTING_CHECKPOINTS', host=host)
    # The reviewed helper/binary must be unchanged remotely before resumption.
    for path, sha in ((REMOTE + '/h1725_remote_capture.py', preflight['files']['h1725_remote_capture.py']),
                      (CAPTURE[host], BINARY_SHA),
                      (REMOTE + '/h1725_dispatch_remote.py', suite.digest(ROOT / 'experiments/h1725_dispatch_remote.py'))):
        assert remote(host, shlex.join(['sha256sum', path])).decode().split()[0] == sha
    jobs = out / 'jobs'; names = sorted(p.name for p in jobs.glob('job-*') if p.is_dir())
    assert names == [f'job-{i:06d}' for i in range(len(names))]
    base_rows = 0; base_seconds = 0; new_rows = 0
    with (out / 'selected.bin').open('rb') as stream:
        number = 0
        while raw := stream.read(20 * 5000):
            records = list(struct.iter_unpack('<QHQH', raw)); name = f'job-{number:06d}'; number += 1
            job = jobs / name
            verify_execution_model(preflight)
            if job.exists() and (job / 'DONE.json').exists():
                spec = validate_frozen(job, records, host, selection, context); validate_capture(job, spec)
                result = scored(job); assert result['status'] == 'PASS' and not result['misses']
                totals.update(result['counts'])
                done = json.loads((job / 'DONE.json').read_text())
                assert done['status'] == 'PASS' and done['totals'] == dict(totals)
                base_rows = totals['rows']; base_seconds = done['seconds']
                if number % 100 == 0 or number == len(names):
                    event(out, 'VERIFYING_EXISTING_CHECKPOINTS', host=host, job=name,
                          revalidated_shards=number, existing_shards=len(names),
                          revalidated_cases=totals['rows'])
                continue
            if not job.exists():
                prepare_job(job, records, host, selection, context, predictor)
                remote(host, shlex.join(['mkdir', '-p', REMOTE + '/' + name]))
                # A new local name must not reuse an existing remote job.
                current = helper(host, 'state', name)
                assert current['state'] == 'UNATTEMPTED' and 'JOB.json' not in current
                upload_files(host, job, ['JOB.json', 'inputs.txt.gz', 'indices.bin'])
            spec = validate_frozen(job, records, host, selection, context)
            current = helper(host, 'state', name)
            assert current['JOB.json'] == spec
            if current['state'] == 'UNATTEMPTED':
                event(out, 'CAPTURING', host=host, job=name, verified_fresh_cases=totals['rows'])
                current = helper(host, 'dispatch', name)
            wait_started = time.time()
            while current['state'] == 'IN_FLIGHT_OR_UNCERTAIN_NO_RETRY':
                if time.time() - wait_started > 900:
                    raise RuntimeError('Capture remains uncertain after 15 minutes; no redispatch')
                time.sleep(5); current = helper(host, 'state', name)
            assert current['state'] == 'CAPTURED', current
            while 'DISPATCHED.json' in current and 'WORKER_EXIT.json' not in current:
                if time.time() - wait_started > 900:
                    raise RuntimeError('Capture worker did not exit; preserve receipts for inspection')
                time.sleep(2); current = helper(host, 'state', name)
            if 'WORKER_EXIT.json' in current:
                assert current['WORKER_EXIT.json']['returncode'] == 0
            event(out, 'DOWNLOADING_AND_SCORING', host=host, job=name, verified_fresh_cases=totals['rows'])
            ensure_download(host, job, spec)
            result = score_recoverably(job); totals.update(result['counts']); new_rows += result['counts']['rows']
            # Numerical failure is recorded BEFORE housekeeping and stops the
            # controller even if its remote acknowledgment also has trouble.
            if result['status'] != 'PASS' or result['misses']:
                raise RuntimeError('MODEL_MISMATCH in ' + name + ': no further capture')
            acknowledge(host, job)
            elapsed = time.time() - started
            save(job / 'DONE.json', dict(status='PASS', totals=dict(totals), seconds=base_seconds + elapsed,
                recovery_controller=True, new_session_seconds=elapsed))
            recovered += 1
            event(out, 'RUNNING', host=host, job=name, verified_fresh_cases=totals['rows'],
                  numerical_or_C1_C2_misses=0, new_session_cases=new_rows,
                  new_session_seconds=elapsed, cases_per_second=new_rows / elapsed,
                  selected_fresh_cases=selection['counts']['selected_cases'])
    assert totals['rows'] == selection['counts']['selected_cases']
    save(out / 'RUN_COMPLETE.json', dict(status='PASS_SELECTED_REMAINING_CASES', totals=dict(totals),
        seconds=base_seconds + time.time() - started, full_matrix_complete=False,
        remaining_holds=selection['counts'], paper_changed=False, algorithm_changed=False))
    event(out, 'SELECTED_RUN_COMPLETE_HOLDS_REMAIN', host=host, verified_fresh_cases=totals['rows'])


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--host', choices=HOSTS, required=True)
    a = p.parse_args(); out = BASE / a.host
    with (out / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            run(a.host)
        except BaseException as exc:
            event(out, 'STOPPED_INSPECT_RECEIPTS', host=a.host, error=str(exc))
            if not (out / 'RESUME_STOPPED.json').exists():
                save(out / 'RESUME_STOPPED.json', dict(time=time.time(), error=repr(exc), traceback=traceback.format_exc()))
            raise
