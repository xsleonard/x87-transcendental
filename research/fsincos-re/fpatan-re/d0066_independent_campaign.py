"""Freeze independent inputs first, then predictions, then one-shot campaigns.

The mathematical generator and its immutable pool never import the model.
This orchestration reuses the established conservative local exclusion and
remote reservation policies. No prediction or private record is uploaded.
"""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import shutil
import sqlite3
import sys

from compressed_guard import digest, packed, save
from protocol import case_key, make_line, parse_line

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASE = ROOT / 'tmp/fpatan-re'
POOL = BASE / 'd0068-independent-lattice-v2'
JOBS = {'skylake': ('d0066', 'root@45.32.204.118', '00050654', '0x1'),
        'i7': ('d0067', 'root@142.132.217.243', '000506e3', '0xf0')}


def prepare():
    job = BASE / 'd0066'
    receipt = json.loads((POOL / 'INPUT-POOL-FROZEN.json').read_text())
    assert receipt['status'] == 'MODEL_INDEPENDENT_INPUT_POOL_FROZEN'
    for name, sha in receipt['files'].items():
        assert digest(POOL / name) == sha
    job.mkdir(exist_ok=False)
    source_names = ('d0066_independent_campaign.py', 'd0065_independent_inputs.py',
        'd0065_math_bounds.c', 'd0068_lattice_inputs.py', 'test_d0065_independent_inputs.py',
        'architecture.py', 'model.py', 'graph_v3.py', 'graph_v4.py', 'graph_v5.py',
        'graph_v6.py', 'graph_v7.py', 'protocol.py', 'capture.c', 'compressed_guard.py',
        'fpatan_candidate.c', 'audit_history.py', 'campaign.py', 'score_stream.py')
    snapshot = job / 'sources'
    snapshot.mkdir()
    for name in source_names:
        with (snapshot / name).open('xb') as target:
            target.write((HERE / name).read_bytes())
    sys.path.insert(0, str(ROOT / 'experiments'))
    from h1725_select_full import private_signatures
    private, _ = private_signatures()
    db = sqlite3.connect('file:' + str(ROOT / 'tmp/ledger33/current/h1725_full_campaign/skylake/possible-history.sqlite') + '?mode=ro', uri=True)
    public = {int(op.split()[1], 16) for op, in db.execute('SELECT op FROM possible')}
    db.close()
    catalog = sqlite3.connect('file:' + str(ROOT / 'corpus-suite/corpus-v1/catalog.sqlite') + '?mode=ro', uri=True)
    previous = set()
    for old in sorted(BASE.iterdir()):
        if old == job or not (old / 'MANIFEST.json').exists():
            continue
        manifest = json.loads((old / 'MANIFEST.json').read_text())
        compressed = manifest.get('format') == 'fpatan-gzip-v2'
        path = old / ('inputs.txt.gz' if compressed else 'inputs.txt')
        with (gzip.open(path, 'rt') if compressed else path.open()) as stream:
            for line in stream:
                previous.add(packed(parse_line(line)))
    print('Local previous tuple audit', len(previous), flush=True)
    counts = Counter()
    with gzip.open(POOL / 'pair-pool.tsv.gz', 'rt') as pool, \
         gzip.open(job / 'inputs.txt.gz', 'xt') as inputs, \
         gzip.open(job / 'categories.tsv.gz', 'xt') as categories:
        for index, row in enumerate(pool):
            raw, kind = row.rstrip().split('\t')
            pair = tuple(int(word, 16) for word in raw.split())
            ys, ym, xs, xm = pair
            counts['generated_pairs'] += 1
            if ym in private and xm in private:
                counts['private_possible_pair_holds'] += 1
                continue
            if ym in public and xm in public:
                counts['public_possible_pair_holds'] += 1
                continue
            if all(catalog.execute('SELECT 1 FROM operands WHERE op=?',
                    (f'{se:04x} {sig:016x}',)).fetchone() for se, sig in ((ys, ym), (xs, xm))):
                counts['corpus_possible_pair_holds'] += 1
                continue
            counts['selected_pairs'] += 1
            for pc in ((24, 53, 64) if index % 257 == 0 else (64,)):
                for rc in ('rn', 'rd', 'ru', 'rz'):
                    key = packed(case_key(rc, pc, *pair))
                    if key in previous:
                        counts['previous_tuple_holds'] += 1
                        continue
                    line = make_line(rc, pc, *pair)
                    inputs.write(line + '\n')
                    categories.write(line.split()[0] + '\t' + kind + '\n')
                    counts['rows'] += 1
                    counts['family:' + kind.split(':')[0]] += 1
    catalog.close()
    del private, public, previous
    assert not any(n in sys.modules for n in ('model', 'architecture', 'graph_v7'))
    save(job / 'INPUTS-FROZEN.json', dict(status='INPUTS_FROZEN_BEFORE_CANDIDATE_IMPORT',
        rows=counts['rows'], counts=counts, model_loaded=False, hardware_executed=False,
        pool_receipt_sha256=digest(POOL / 'INPUT-POOL-FROZEN.json'),
        files={name: digest(job / name) for name in ('inputs.txt.gz', 'categories.tsv.gz')}))
    print('Inputs frozen before model import', counts['rows'], flush=True)

    from architecture import predict
    with gzip.open(job / 'inputs.txt.gz', 'rt') as inputs, \
         gzip.open(job / 'predictions.txt.gz', 'xt') as predictions:
        for index, line in enumerate(inputs):
            ident, rc, pc, *raw = line.split()
            se, sig, c1, flags, before = predict(*(int(v, 16) for v in raw), rc)
            predictions.write(f'{ident} {se:04x} {sig:016x} {c1} {flags:02x} {before:02x}\n')
            if index and index % 65536 == 0:
                print('Frozen independent predictions', index, flush=True)
    inputs_frozen = json.loads((job / 'INPUTS-FROZEN.json').read_text())
    for name, sha in inputs_frozen['files'].items():
        assert digest(job / name) == sha
    save(job / 'MANIFEST.json', dict(status='FROZEN_DISCOVERY_UNOPENED', format='fpatan-gzip-v2',
        rows=counts['rows'], counts=counts, reference_host='45.32.204.118',
        expected_signature='00050654', expected_microcode='0x1',
        purpose='Model-independent mathematical/SMT boundaries, raw-bit strata and exhaustive 2D windows',
        files={name: digest(job / name) for name in
               ('inputs.txt.gz', 'categories.tsv.gz', 'predictions.txt.gz')},
        source_pins={name: digest(snapshot / name) for name in source_names},
        input_freeze_sha256=digest(job / 'INPUTS-FROZEN.json'),
        C1_predictions=True, status_predictions=True, mathematical_oracle=False,
        hardware_executed=False, privacy='Only cleared inputs and generic capture support are uploaded.',
        limits='Finite challenge, not all-input proof. Mathematical boundaries select tests; they do not prescribe silicon results.'))
    print('PASS independent campaign freeze', json.dumps(counts), flush=True)


def prepare_i7():
    source, job = BASE / 'd0066', BASE / 'd0067'
    manifest = json.loads((source / 'MANIFEST.json').read_text())
    job.mkdir(exist_ok=False)
    # The destination guard audits its own context before any observation.
    # These inputs and both preflights are identical, not additional runs.
    for name in (*manifest['files'], 'INPUTS-FROZEN.json', 'C-PREFLIGHT.json', 'C-SANITIZED-PREFLIGHT.json'):
        with (job / name).open('xb') as target, (source / name).open('rb') as original:
            shutil.copyfileobj(original, target)
    snapshot = job / 'sources'
    snapshot.mkdir()
    for name, sha in manifest['source_pins'].items():
        assert digest(source / 'sources' / name) == sha == digest(HERE / name)
        with (snapshot / name).open('xb') as target, (source / 'sources' / name).open('rb') as original:
            shutil.copyfileobj(original, target)
    manifest.update(reference_host='142.132.217.243', expected_signature='000506e3',
                    expected_microcode='0xf0', identical_input_source='d0066')
    save(job / 'MANIFEST.json', manifest)
    print('PASS identical independent input pack prepared for i7', manifest['rows'], flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('step', choices=('prepare', 'prepare-i7', 'history', 'stage', 'capture', 'fetch', 'score', 'ledger'))
    parser.add_argument('--host', choices=JOBS, default='skylake')
    args = parser.parse_args()
    if args.step == 'prepare':
        prepare()
    elif args.step == 'prepare-i7':
        prepare_i7()
    else:
        import campaign
        job, host, _, _ = JOBS[args.host]
        campaign.HOST = host
        campaign.SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', host]
        getattr(campaign, args.step)(BASE / job)


if __name__ == '__main__':
    main()
