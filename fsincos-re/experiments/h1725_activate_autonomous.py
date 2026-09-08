#!/usr/bin/env python3
"""Activate one reviewed remote owner after the exact Mac prefix is drained."""
import argparse
import hashlib
import io
import json
import os
import shlex
import signal
import subprocess
import tarfile
from pathlib import Path

import h1725_resume_full as old
from h1725_full_campaign import BASE, ROOT, save, suite

REMOTE = '/root/h1725-full-corpus/autonomous-20260907'
UNIT = 'h1725-autonomous.service'


def read_remote(host, path):
    return old.remote(host, shlex.join(['cat', path]))


def activate(host):
    out = BASE / host; package = BASE / ('autonomous-' + host + '-20260907')
    ready = json.loads((out / 'CUTOVER_READY.json').read_text())
    assert ready['status'] == 'DRAINED_READY_FOR_REMOTE_OWNER'
    selection = json.loads((out / 'SELECTION.json').read_text())
    preflight_bytes = read_remote(host, REMOTE + '/PREFLIGHT.json'); preflight = json.loads(preflight_bytes)
    assert preflight['status'] == 'PASS' and preflight['hardware_executions'] == 0
    assert len(preflight['replays']) == 2 and all(r['predictor_matches_original'] and r['original_score_matches'] for r in preflight['replays'])
    assert read_remote(host, old.REMOTE + '/receipts/' + ready['last_mac_job'] + '.json.gz') == (out / 'jobs' / ready['last_mac_job'] / 'remote-receipts.json.gz').read_bytes()
    names = {}
    for path in package.rglob('*'):
        if path.is_file():
            name = str(path.relative_to(package))
            if name == 'h1725_autonomous_preflight.py':
                path = ROOT / 'experiments/h1725_autonomous_preflight.py'
            names[name] = suite.digest(path)
    # Check every staged input/code/fixture byte against the local allowlist.
    command = "import hashlib,json,pathlib; p=pathlib.Path(%r); names=%r; print(json.dumps({n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in names}))" % (REMOTE, list(names))
    actual = json.loads(old.remote(host, shlex.join(['python3', '-c', command])))
    assert names == actual, 'Remote package differs from staged public allowlist'
    names['predictor'] = preflight['predictor_sha256']; names['PREFLIGHT.json'] = hashlib.sha256(preflight_bytes).hexdigest()
    cfg = dict(host=host, remote_base=old.REMOTE, predictor=REMOTE + '/predictor',
        predictor_sha256=preflight['predictor_sha256'], capture_binary=old.CAPTURE[host], capture_sha256=old.BINARY_SHA,
        ledger=old.LEDGER[host], cpu_context_id=ready['cpu_context_id'], algorithm_pins=old.PINS,
        start_job=ready['start_job'], prior_totals=ready['prior_totals'],
        selection_sha256=selection['selected_sha256'], selected_cases=selection['counts']['selected_cases'],
        selection_counts=selection['counts'], predecessor_receipt_sha256=ready['last_receipt_sha256'])
    activation = out / 'autonomous-activation'; activation.mkdir()
    save(activation / 'CUTOVER.json', cfg)
    save(activation / 'PACKAGE.json', dict(files=names, cutover_sha256=suite.digest(activation / 'CUTOVER.json'),
         algorithm_changed=False, capture_guard_changed=False, prior_reservations_preserved=True))
    unit = ('[Unit]\nDescription=Autonomous one-shot H1725 x87 verification\nAfter=local-fs.target\n\n'
            '[Service]\nType=simple\nWorkingDirectory=' + REMOTE + '\n'
            'ExecStart=/usr/bin/python3 -u ' + REMOTE + '/h1725_autonomous.py --package ' + REMOTE + '\n'
            'Restart=no\nStandardOutput=append:' + REMOTE + '/service.stdout.log\n'
            'StandardError=append:' + REMOTE + '/service.stderr.log\n\n[Install]\nWantedBy=multi-user.target\n')
    with (activation / UNIT).open('x') as f:
        f.write(unit)
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode='w') as archive:
        for name in ('CUTOVER.json', 'PACKAGE.json', UNIT):
            archive.add(activation / name, arcname=name)
    next_name = f'job-{ready["start_job"]:06d}'
    check = 'test ! -e ' + shlex.quote(REMOTE + '/CUTOVER.json') + ' && test ! -e ' + shlex.quote(old.REMOTE + '/' + next_name)
    check += ' && test ! -e ' + shlex.quote(old.REMOTE + '/receipts/' + next_name + '.json.gz')
    old.remote(host, check + ' && tar -C ' + shlex.quote(REMOTE) + ' -xf -', payload.getvalue())
    # Native freshness is still checked by the old bitmap/ledger, not inferred
    # from the absent directory above. No reservation is imported or cleared.
    old.remote(host, 'python3 -c ' + shlex.quote("import sys; from pathlib import Path; sys.path.insert(0,%r); import h1725_autonomous as a; a.verify_package(Path(%r)); print('PACKAGE_PASS')" % (REMOTE, REMOTE)))
    marker = dict(status='REMOTE_AUTONOMOUS_OWNER', remote_package=REMOTE, service=UNIT,
        start_job=ready['start_job'], prior_totals=ready['prior_totals'],
        cutover_sha256=suite.digest(activation / 'CUTOVER.json'),
        package_sha256=suite.digest(activation / 'PACKAGE.json'), original_controller_pid=ready['paused_pid'])
    save(out / 'AUTONOMOUS_CUTOVER.json', marker)
    # Remove only the drained Mac service. No capture process is signalled.
    subprocess.run(['launchctl', 'remove', 'com.steve.x87.h1725.' + host], check=True)
    try:
        os.kill(ready['paused_pid'], signal.SIGCONT)
    except ProcessLookupError:
        pass
    command = ('test ! -e /etc/systemd/system/' + UNIT + ' && cp ' + REMOTE + '/' + UNIT + ' /etc/systemd/system/' + UNIT +
               ' && systemctl daemon-reload && systemctl enable --now ' + UNIT +
               ' && systemctl show ' + UNIT + ' -p ActiveState -p SubState -p MainPID -p UnitFileState')
    result = old.remote(host, command)
    with (activation / 'activation.stdout.txt').open('xb') as f:
        f.write(result)
    with (activation / 'PREFLIGHT.json').open('xb') as f:
        f.write(preflight_bytes)
    print(result.decode(), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--host', choices=('i7', 'skylake'), required=True)
    activate(p.parse_args().host)
