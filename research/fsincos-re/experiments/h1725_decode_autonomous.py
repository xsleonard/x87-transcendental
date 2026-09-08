#!/usr/bin/env python3
"""Recover portable hardware observations from a native-delta archive.

Software only. No SSH or native captures. A compatible frozen predictor is
the codec dictionary, authenticated by each archive's prediction-content hash.
All decoded native bytes must match the original hardware-stream hash before
the portable dataset is sealed as hardware observations.
"""
import argparse
import base64
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'corpus-suite'))
import suite
import h1725_autonomous as auto


def decode(package, archive, predictor, out):
    payload = json.loads(gzip.decompress(archive.read_bytes()))
    index = json.loads((package / 'PLAN.json').read_text())
    assert payload['selection_sha256'] == index['selection_sha256']
    number = int(payload['job'].split('-')[1]); records = auto.plan_chunk(package, index, number)
    assert auto.sha(b''.join(auto.RECORD.pack(*r) for r in records)) == payload['records_sha256']
    out.mkdir(parents=True, exist_ok=False)
    predict, _ = auto.original_functions(package, {})
    predictions = predict(out, records, predictor)
    ordered = [case for case, _ in auto.cases(records)]
    observations = []
    with suite.gzwrite(out / 'native-output.txt.gz') as f:
        for raw in auto.decode_lines(payload, ordered, predictions):
            f.write(raw.decode('ascii'))
            fields = suite.parse_numeric(raw.decode('ascii'))
            insn, mode, pc, op = suite.decode_case(fields['CASE'])
            observations.append(suite.validate_numeric(fields, insn, mode, pc, op, fields['CASE']))
    portable = out / 'observations'; portable.mkdir()
    with suite.gzwrite(portable / 'observations.tsv.gz') as f:
        f.write('\t'.join(suite.FIELDS) + '\n')
        for row in sorted(observations):
            f.write('\t'.join(map(str, row)) + '\n')
    auto.durable(portable / 'cpu.json', base64.b64decode(payload['metadata']['cpu.json'], validate=True))
    auto.save(portable / 'provenance.json', dict(source='losslessly decoded H1725 native hardware observations',
        native_text_sha256=payload['native_text_sha256'], archive_sha256=suite.digest(archive),
        original_capture_receipt=json.loads(base64.b64decode(payload['metadata']['COMPLETE.json'])),
        prediction_content_sha256=payload['prediction_content_sha256'],
        hardware_executions=0, observations_reused=True,
        note='Native text is byte-exact. Gzip container bytes are regenerated, not claimed identical to the original scratch container.'))
    auto.save(portable / 'MANIFEST.json', dict(schema='x87-suite-v1', kind='hardware_observations', rows=len(ordered),
        files={n: suite.digest(portable / n) for n in ('observations.tsv.gz', 'cpu.json', 'provenance.json')}))
    assert sum(1 for _ in suite.observations(portable)) == len(ordered)
    print(json.dumps(dict(status='LOSSLESS_DECODE_PASS', rows=len(ordered), native_text_sha256=payload['native_text_sha256'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('package', 'archive', 'predictor', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args(); decode(a.package, a.archive, a.predictor, a.out)
