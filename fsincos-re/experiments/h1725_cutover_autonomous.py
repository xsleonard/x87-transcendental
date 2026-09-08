#!/usr/bin/env python3
"""Drain the live Mac controller at a fully prepared batch; never discard work.

SIGSTOP applies only to the coordinator, not the independent capture worker.
The existing one-shot protocol finishes/reuses its single pending shard. This
script leaves the coordinator paused until reviewed autonomous activation.
"""
import argparse
import collections
import json
import os
import signal
import subprocess
import time
from pathlib import Path

import h1725_resume_full as old
from h1725_full_campaign import BASE, save


def drain(host):
    out = BASE / host
    assert not (out / 'CUTOVER_READY.json').exists()
    assert not (out / 'RESUME_STOPPED.json').exists()
    stop = time.time() + 60
    while True:
        assert time.time() < stop, 'No suitable batch boundary yet; controller remains running'
        state = json.loads((out / 'CONTROLLER.json').read_text())
        if state['stage'] != 'CAPTURING':
            time.sleep(0.1); continue
        pid = state['pid']
        command = subprocess.check_output(['ps', '-p', str(pid), '-o', 'command='], text=True)
        assert 'h1725_resume_full.py --host ' + host in command
        os.kill(pid, signal.SIGSTOP)
        pending = sorted(p for p in (out / 'jobs').glob('job-*') if p.is_dir() and not (p / 'DONE.json').exists())
        if len(pending) != 1 or not all((pending[0] / n).is_file() for n in ('JOB.json', 'predictions.json.gz', 'inputs.txt.gz', 'indices.bin')):
            os.kill(pid, signal.SIGCONT); time.sleep(0.1); continue
        break
    save(out / 'CUTOVER_PAUSED.json', dict(pid=pid, host=host, time=time.time(), job=pending[0].name,
         note='Only the Mac coordinator is paused. Drain the guarded pending capture; never clear reservations.'))
    job = pending[0]; number = int(job.name.split('-')[1])
    # Allow its already spawned SSH control request to settle. This is not a
    # new instruction retry: dispatch itself is durably idempotent under lock.
    time.sleep(2)
    with (out / 'selected.bin').open('rb') as f:
        f.seek(number * 100000); records = list(old.struct.iter_unpack('<QHQH', f.read(100000)))
    selection = json.loads((out / 'SELECTION.json').read_text())
    context = json.loads((job / 'JOB.json').read_text())['cpu_context_id']
    spec = old.validate_frozen(job, records, host, selection, context)
    state = old.helper(host, 'state', job.name)
    if state['state'] == 'UNATTEMPTED':
        state = old.helper(host, 'dispatch', job.name)
    deadline = time.time() + 120
    while (state['state'] == 'IN_FLIGHT_OR_UNCERTAIN_NO_RETRY'
           or state['state'] == 'CAPTURED' and 'DISPATCHED.json' in state and 'WORKER_EXIT.json' not in state):
        assert time.time() < deadline, 'Uncertain native capture; do not retry'
        time.sleep(1); state = old.helper(host, 'state', job.name)
    assert state['state'] == 'CAPTURED' and state.get('WORKER_EXIT.json', {'returncode': 0})['returncode'] == 0
    old.ensure_download(host, job, spec)
    result = old.score_recoverably(job)
    assert result['status'] == 'PASS' and not result['misses'], 'Real miss: preserve before cutover'
    previous = json.loads((out / 'jobs' / f'job-{number-1:06d}' / 'DONE.json').read_text())
    totals = collections.Counter(previous['totals']); totals.update(result['counts'])
    old.acknowledge(host, job)
    save(job / 'DONE.json', dict(status='PASS', totals=dict(totals), seconds=previous['seconds'],
                               recovery_controller=True, autonomous_cutover_drain=True))
    all_jobs = sorted(p.name for p in (out / 'jobs').glob('job-*') if p.is_dir())
    assert all_jobs == [f'job-{i:06d}' for i in range(number + 1)]
    assert all((out / 'jobs' / name / 'DONE.json').is_file() for name in all_jobs)
    result = dict(host=host, paused_pid=pid, start_job=number + 1, last_mac_job=job.name,
                  prior_totals=dict(totals), cpu_context_id=context, completed_unix=time.time(),
                  last_receipt_sha256=old.suite.digest(job / 'remote-receipts.json.gz'),
                  native_instructions_repeated=0, status='DRAINED_READY_FOR_REMOTE_OWNER')
    save(out / 'CUTOVER_READY.json', result)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--host', choices=('i7', 'skylake'), required=True)
    drain(parser.parse_args().host)
