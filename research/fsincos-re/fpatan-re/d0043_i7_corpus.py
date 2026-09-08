"""One-shot i7 transfer of the full authenticated D0040 FPATAN corpus.

The historical project configuration identifies the i7 as 142.132.217.243;
the shorter .24 address in an earlier message is not that configured host.
Reference fields come from authenticated Skylake observations, never old
candidate predictions. Only inputs and generic capture infrastructure leave
this machine. Every native tuple is reserved once by the existing guard.
"""
import argparse
from collections import Counter
from contextlib import ExitStack
import gzip
import json
from pathlib import Path
import sys

import campaign
from compressed_guard import digest, packed
from prepare import save
from protocol import parse_line, validate_output

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASE = ROOT / 'tmp/fpatan-re'
JOB = BASE / 'd0043'
HOST = 'root@142.132.217.243'


def prepare():
    JOB.mkdir(exist_ok=False)
    corpus = HERE / 'corpus-v1'
    catalog_path = corpus / 'CATALOG-D0040.json'
    catalog = json.loads(catalog_path.read_text())
    save(JOB / 'PREPARING.json', dict(status='PREPARING_I7_REFERENCE_NO_CAPTURE',
        catalog_sha256=digest(catalog_path), host=HOST, hardware_executed=False))
    sys.path.insert(0, str(ROOT / 'experiments'))
    from h1725_select_full import private_signatures
    private, _ = private_signatures()
    counts, lineage, seen = Counter(), {}, set()
    with ExitStack() as stack:
        outputs = {name: stack.enter_context(gzip.open(JOB / name, 'xt')) for name in
            ('inputs.txt.gz', 'predictions.txt.gz', 'categories.tsv.gz')}
        for name, pack in catalog['packs'].items():
            inputs_path = corpus / pack['path']
            old = BASE / name
            complete = json.loads((old / 'COMPLETE.json').read_text())
            manifest_path = old / 'MANIFEST.json'
            compressed = complete.get('format') == 'fpatan-gzip-v2'
            hardware_path = old / ('hardware.txt.gz' if compressed else 'hardware.txt')
            assert complete['state'] == 'OBSERVED'
            assert digest(inputs_path) == pack['sha256']
            assert digest(manifest_path) == complete['manifest_sha256'] == pack['source_manifest_sha256']
            assert digest(hardware_path) == complete['hardware_gzip_sha256' if compressed else 'hardware_sha256']
            rows = 0
            with gzip.open(inputs_path, 'rt') as inputs, \
                 (gzip.open(hardware_path, 'rt') if compressed else hardware_path.open()) as hardware:
                for line, actual in zip(inputs, hardware, strict=True):
                    key = packed(parse_line(line))
                    assert key not in seen
                    seen.add(key)
                    fields = line.split()
                    if int(fields[4], 16) in private and int(fields[6], 16) in private:
                        counts['private_possible_tuple_holds'] += 1
                        continue
                    observed = validate_output(actual, line)
                    ident = fields[0]
                    outputs['inputs.txt.gz'].write(line)
                    outputs['predictions.txt.gz'].write(
                        f'{ident} {observed["se"]:04x} {observed["sig"]:016x} '
                        f'{observed["C1"]} {observed["sw"] & 63:02x} {observed["before"] & 63:02x}\n')
                    outputs['categories.tsv.gz'].write(f'{ident}\tsource-pack:{name}\n')
                    counts['rows'] += 1
                    counts['rc:' + fields[1]] += 1
                    counts['pc:' + fields[2]] += 1
                    rows += 1
            assert rows == pack['counts']['rows'] == complete['rows']
            lineage[name] = dict(rows=rows, input_sha256=pack['sha256'],
                hardware_sha256=complete['hardware_sha256'],
                completion_sha256=digest(old / 'COMPLETE.json'), source_manifest_sha256=digest(manifest_path))
            print('Prepared i7 reference pack', name, rows, flush=True)
    del private
    assert not counts['private_possible_tuple_holds']
    assert counts['rows'] == catalog['counts']['rows'] == 4612536
    source_names = ('capture.c', 'protocol.py', 'compressed_guard.py', 'audit_history.py',
                    'campaign.py', 'd0043_i7_corpus.py', 'fpatan_candidate.c')
    snapshot = JOB / 'sources'
    snapshot.mkdir()
    for name in source_names:
        with (snapshot / name).open('xb') as target:
            target.write((HERE / name).read_bytes())
    save(JOB / 'SKYLAKE-REFERENCE.json', dict(status='AUTHENTICATED_REFERENCE_BEFORE_I7_CAPTURE',
        catalog_sha256=digest(catalog_path), source_packs=lineage,
        counts=counts, hardware_executed=False, i7_labels_opened=False,
        comparison='Raw result, C1, masked arithmetic exception and pre-load flags; undefined condition bits are not model requirements.'))
    save(JOB / 'MANIFEST.json', dict(status='FROZEN_DISCOVERY_UNOPENED', format='fpatan-gzip-v2',
        rows=counts['rows'], counts=counts, reference_host='142.132.217.243',
        expected_signature='000506e3', expected_microcode='0xf0',
        purpose='Full seventeen-pack FPATAN corpus cross-CPU comparison against authenticated Skylake observations',
        files={name: digest(JOB / name) for name in outputs},
        source_pins={name: digest(snapshot / name) for name in source_names},
        reference_receipt_sha256=digest(JOB / 'SKYLAKE-REFERENCE.json'),
        hardware_executed=False, C1_predictions=True, status_predictions=True,
        privacy='Private supplemental history was checked locally; no private records, model or reference outputs are uploaded.',
        limits='The i7 identity must match at execution. No prior-use clearance is inferred from the corpus having run on Skylake.'))
    print('PASS prepared full i7 corpus reference', counts['rows'], 'rows; no hardware', flush=True)


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
