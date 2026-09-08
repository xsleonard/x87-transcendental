"""Transfer the newly captured D0042 extension to i7 without repeating D0043.

This supplements the request-time full-corpus snapshot so both CPUs receive
the same completed input catalog. Only previously unseen i7 tuples may run.
"""
import argparse
import gzip
import json
from pathlib import Path
import shutil
import sys

import campaign
from compressed_guard import digest
from prepare import save

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASE = ROOT / 'tmp/fpatan-re'
JOB = BASE / 'd0044'
HOST = 'root@142.132.217.243'


def prepare():
    old = BASE / 'd0042'
    complete = json.loads((old / 'COMPLETE.json').read_text())
    manifest = json.loads((old / 'MANIFEST.json').read_text())
    score = json.loads((old / 'SCORE.json').read_text())
    assert complete['state'] == 'OBSERVED'
    assert complete['manifest_sha256'] == digest(old / 'MANIFEST.json')
    assert digest(old / 'hardware.txt.gz') == complete['hardware_gzip_sha256']
    assert all(score['counts'][name] == 0 for name in ('candidate_misses', 'candidate_C1_misses',
        'exception_misses', 'before_exception_misses'))
    assert score['hardware_sha256'] == complete['hardware_sha256']
    JOB.mkdir(exist_ok=False)
    save(JOB / 'PREPARING.json', dict(status='PREPARING_ADDITIVE_I7_COMPARISON',
        source_completion_sha256=digest(old / 'COMPLETE.json'), hardware_executed=False))
    sys.path.insert(0, str(ROOT / 'experiments'))
    from h1725_select_full import private_signatures
    private, _ = private_signatures()
    rows = 0
    with gzip.open(old / 'inputs.txt.gz', 'rt') as source:
        for line in source:
            fields = line.split()
            assert not (int(fields[4], 16) in private and int(fields[6], 16) in private)
            rows += 1
    del private
    assert rows == manifest['rows'] == 2485048
    for name in manifest['files']:
        assert digest(old / name) == manifest['files'][name]
        with (JOB / name).open('xb') as target, (old / name).open('rb') as source:
            shutil.copyfileobj(source, target)
    # These receipts are reused only because both complete input and frozen
    # expected streams are byte-identical; no new C execution is claimed.
    for name in ('C-PREFLIGHT.json', 'C-SANITIZED-PREFLIGHT.json'):
        result = json.loads((old / name).read_text())
        assert result['rows'] == rows and result['C_frozen_Python_differences'] == 0
        with (JOB / name).open('xb') as target, (old / name).open('rb') as source:
            shutil.copyfileobj(source, target)
    snapshot = JOB / 'sources'
    snapshot.mkdir()
    names = ('capture.c', 'protocol.py', 'compressed_guard.py', 'audit_history.py',
        'campaign.py', 'd0044_i7_new_adversaries.py', 'fpatan_candidate.c')
    for name in names:
        with (snapshot / name).open('xb') as target:
            target.write((HERE / name).read_bytes())
    catalog = HERE / 'corpus-v1/CATALOG-D0042.json'
    save(JOB / 'SKYLAKE-REFERENCE.json', dict(status='AUTHENTICATED_REFERENCE_BEFORE_I7_CAPTURE',
        catalog_sha256=digest(catalog), counts=dict(rows=rows),
        source_packs={'d0042': dict(rows=rows, input_sha256=manifest['files']['inputs.txt.gz'],
            hardware_sha256=complete['hardware_sha256'], completion_sha256=digest(old / 'COMPLETE.json'),
            source_manifest_sha256=digest(old / 'MANIFEST.json'))},
        C_preflight_reused_from='d0042; identical complete input/prediction streams',
        zero_miss_reference_score_sha256=digest(old / 'SCORE.json'), hardware_executed=False))
    save(JOB / 'MANIFEST.json', dict(status='FROZEN_DISCOVERY_UNOPENED', format='fpatan-gzip-v2',
        rows=rows, reference_host='142.132.217.243', expected_signature='000506e3', expected_microcode='0xf0',
        purpose='Add new early/table-halfway corpus extension to the full i7/Skylake comparison',
        files=manifest['files'], source_pins={name: digest(snapshot / name) for name in names},
        reference_receipt_sha256=digest(JOB / 'SKYLAKE-REFERENCE.json'),
        C1_predictions=True, status_predictions=True, hardware_executed=False,
        privacy='No model, reference outputs or private records are uploaded.',
        limits='This is the nonoverlapping D0042 extension; D0043 must not be recaptured.'))
    print('PASS prepared additive i7 comparison', rows, 'new i7 tuples', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('step', choices=('prepare', 'history', 'stage', 'capture', 'fetch', 'score', 'ledger'))
    args = parser.parse_args()
    campaign.HOST = HOST
    campaign.SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', HOST]
    if args.step == 'prepare':
        prepare()
    else:
        getattr(campaign, args.step)(JOB)
