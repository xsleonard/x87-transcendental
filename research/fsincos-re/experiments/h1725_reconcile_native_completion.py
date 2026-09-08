#!/usr/bin/env python3
"""Reconcile completed native receipts; no capture or portable-closure claim."""
import argparse
import base64
import collections
import gzip
import hashlib
import json
import shlex
import subprocess

from h1725_full_campaign import BASE, HOSTS, suite, save


def audit(host):
    out = BASE / host; marker = json.loads((out / 'AUTONOMOUS_CUTOVER.json').read_text())
    package = marker['remote_package']
    script = '''import sys,json,pathlib,hashlib,base64,subprocess
p=pathlib.Path(PACKAGE);sys.path.insert(0,str(p))
import h1725_autonomous as a
a.verify_package(p)
assert not (p/'STOPPED.json').exists()
names=('RUN_COMPLETE.json','CUTOVER.json','PACKAGE.json','PREFLIGHT.json','STATUS.json')
files={n:base64.b64encode((p/n).read_bytes()).decode() for n in names}
receipts={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in (p/'observed').glob('job-*.DONE.json')}
service=subprocess.check_output(['systemctl','show','h1725-autonomous.service','-p','ActiveState','-p','SubState','-p','ExecMainStatus','-p','Result'],text=True)
print(json.dumps(dict(files=files,receipts=receipts,service=service,package_verified=True,stderr_bytes=(p/'service.stderr.log').stat().st_size)))'''.replace('pathlib.Path(PACKAGE)', 'pathlib.Path(' + repr(package) + ')')
    evidence = json.loads(subprocess.check_output(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15',
        'root@' + HOSTS[host], shlex.join(['python3', '-c', script])], timeout=60))
    assert evidence['package_verified'] and evidence['stderr_bytes'] == 0
    assert 'ExecMainStatus=0\n' in evidence['service'] and 'Result=success\n' in evidence['service']
    files = {n: base64.b64decode(v, validate=True) for n, v in evidence['files'].items()}
    complete = json.loads(files['RUN_COMPLETE.json']); cfg = json.loads(files['CUTOVER.json'])
    assert complete['status'] == 'PASS_SELECTED_REMAINING_CASES' and not complete['full_matrix_complete']
    assert hashlib.sha256(files['CUTOVER.json']).hexdigest() == marker['cutover_sha256']
    assert hashlib.sha256(files['PACKAGE.json']).hexdigest() == marker['package_sha256']
    selection = json.loads((out / 'SELECTION.json').read_text())
    assert cfg['selection_sha256'] == selection['selected_sha256']
    assert complete['remaining_holds'] == cfg['selection_counts'] == selection['counts']
    plan = json.loads((BASE / ('autonomous-' + host + '-20260907') / 'PLAN.json').read_text())
    assert plan['selection_sha256'] == selection['selected_sha256']
    totals = collections.Counter()
    # Prefix captures were already hash-validated/offloaded by the original
    # runner. Reconcile all their score/checkpoint identities and counts here.
    for number in range(cfg['start_job']):
        job = out / 'jobs' / f'job-{number:06d}'
        score = json.loads((job / 'score.json').read_text()); done = json.loads((job / 'DONE.json').read_text())
        spec = json.loads((job / 'JOB.json').read_text()); native = json.loads((job / 'COMPLETE.json').read_text())
        assert score['status'] == done['status'] == 'PASS' and not score['misses']
        assert score['counts']['rows'] == spec['rows'] == native['rows']
        assert score['raw_sha256'] == native['outputs_sha256']
        assert score['prediction_sha256'] == spec['predictions_sha256']
        assert spec['selection_sha256'] == cfg['selection_sha256'] and spec['cpu_context_id'] == cfg['cpu_context_id']
        totals.update(score['counts']); assert dict(totals) == done['totals']
    assert dict(totals) == cfg['prior_totals'] == marker['prior_totals']
    expected_names = {f'job-{n:06d}.DONE.json' for n in range(cfg['start_job'], plan['end_job'])}
    assert set(evidence['receipts']) == expected_names
    archive_hashes = {}; rows_new = 0
    for number in range(cfg['start_job'], plan['end_job']):
        name = f'job-{number:06d}'; path = out / 'autonomous-observed' / (name + '.DONE.json')
        assert suite.digest(path) == evidence['receipts'][path.name]
        done = json.loads(path.read_text()); archive = path.with_name(name + '.json.gz')
        assert suite.digest(archive) == done['archive_sha256']
        archive_hashes[archive.name] = done['archive_sha256']
        with gzip.open(archive, 'rt') as f:
            payload = json.load(f)
        meta = {n: json.loads(base64.b64decode(payload['metadata'][n], validate=True))
                for n in ('JOB.json','COMPLETE.json','score.json','cpu.json')}
        spec = meta['JOB.json']; native = meta['COMPLETE.json']; score = meta['score.json']
        assert payload['job'] == name and payload['selection_sha256'] == cfg['selection_sha256']
        assert payload['predictor_sha256'] == cfg['predictor_sha256']
        assert payload['records_sha256'] == plan['jobs'][str(number)]['records_sha256']
        assert payload['rows'] == done['rows'] == spec['rows'] == native['rows'] == plan['jobs'][str(number)]['rows']
        assert payload['native_text_sha256'] == done['native_text_sha256']
        assert native['status'] == 'OPENED_ONCE_DO_NOT_RERUN' and native['instruction_retries'] == 0
        assert native['cpu_context_id'] == spec['cpu_context_id'] == meta['cpu.json']['context_id'] == cfg['cpu_context_id']
        assert native['binary_sha256'] == spec['binary_sha256'] == cfg['capture_sha256']
        assert score['status'] == 'PASS' and not score['misses'] and score['counts'] == done['counts']
        assert score['raw_sha256'] == native['outputs_sha256'] and score['prediction_sha256'] == spec['predictions_sha256']
        assert done['status'] == 'PASS_NATIVE_OBSERVATIONS_RETAINED'
        totals.update(done['counts']); rows_new += done['counts']['rows']; assert dict(totals) == done['totals']
    assert dict(totals) == complete['totals'] and totals['rows'] == cfg['selected_cases']
    assert not any(v for k, v in totals.items() if k.endswith('_misses'))
    counts = selection['counts']
    assert sum(counts[k] for k in ('selected_cases','prior_excluded_cases','binary64_domain_hold_cases','ambiguous_or_generated_hold_cases')) == 507477240
    portable = list((out / 'autonomous-portable').glob('job-*/observations/MANIFEST.json'))
    target = out / 'native-completion-20260907'; target.mkdir()
    for name, data in files.items():
        with (target / name).open('xb') as f:
            f.write(data)
    save(target / 'remote-evidence.json', evidence)
    save(target / 'archive-hashes.json', archive_hashes)
    report = dict(status='NATIVE_SELECTED_RUN_RECONCILED_PASS', host=host, total_shards=plan['end_job'],
        original_prefix_shards=cfg['start_job'], autonomous_shards=len(expected_names), autonomous_rows=rows_new,
        totals=dict(totals), full_matrix_complete=False, selection_counts=counts,
        completed_unix=complete['completed_unix'], portable_autonomous_shards_at_audit=len(portable),
        portable_export_complete=False, hardware_executions=0,
        note='Portable materialization is separately ongoing; no universal/full-matrix claim, native repeats, or paper changes.')
    save(target / 'REPORT.json', report); print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--host', choices=HOSTS, required=True)
    audit(p.parse_args().host)
