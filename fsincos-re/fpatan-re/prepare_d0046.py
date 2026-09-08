"""Freeze genuinely endpoint-visible short-correction tie discriminators."""
from collections import Counter
from dataclasses import replace
import gzip
import json
from pathlib import Path

from architecture import POLICY
from compressed_guard import digest
import d0031_internal_rounding_coverage as audit
from freeze_stream import freeze
from prepare import save
from prepare_d0033 import neighbor, orbits
from prepare_d0042 import values

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'tmp/fpatan-re'
MINING = BASE / 'd0045-node3-upper'


def generate():
    report = json.loads((MINING / 'REPORT.json').read_text())
    assert report['status'] == 'VERIFIED_BOUNDED_TIE_OBSERVABILITY_SEARCH'
    assert digest(MINING / 'miner.tsv') == report['target_sha256']
    for name, sha in report['source_sha256'].items():
        assert digest(HERE / name) == sha
    for index, witness in enumerate(report['witnesses']):
        if witness['status'] != 'EXACT_EXTERNAL_ENDPOINT_SEPARATOR':
            continue
        ys, ym, xs, xm = (int(word, 16) for word in witness['raw'])
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                a, b = neighbor(ys, ym, dy), neighbor(xs, xm, dx)
                for raw in orbits((*a, *b)):
                    yield raw, (f'node3:seed{index}:cell{witness["cell"]}:'
                                f'parity{witness["parity"]}:y{dy}:x{dx}')


def freeze_controls(job):
    assert not (job / 'DISPATCHED.json').exists()
    counts = Counter()
    sparse = job / 'CONTROL-DIFFERENCES.jsonl.gz'
    with gzip.open(job / 'inputs.txt.gz', 'rt') as inputs, \
         gzip.open(job / 'predictions.txt.gz', 'rt') as predictions, \
         gzip.open(sparse, 'xt') as output:
        for line, expected in zip(inputs, predictions, strict=True):
            ident, rc, pc, ys, ym, xs, xm = line.split()
            y = audit.Raw80(int(ys, 16), int(ym, 16))
            x = audit.Raw80(int(xs, 16), int(xm, 16))
            fixed, alternatives, events = values(audit.core_key(y, x))
            quadrant = 2 * int(audit.normalized(y) > audit.normalized(x)) + int(bool(x.se & 32768))
            sign = -1 if y.se & 32768 else 1
            value, c1 = audit.SPEC['pack_angle'](sign * fixed[quadrant], rc.upper())
            baseline = value.se, value.sig, c1, 32, 0
            assert expected.split()[0] == ident
            assert baseline == tuple(int(word, 16) for word in expected.split()[1:])
            counts['rows'] += 1
            for node, (event, parity) in events.items():
                counts[f'node{node}:{event}:parity{parity}'] += 1
                if event != 'tie':
                    continue
                other, flag = audit.SPEC['pack_angle'](sign * alternatives[node][quadrant], rc.upper())
                alternative = other.se, other.sig, flag, 32, 0
                if alternative != baseline:
                    output.write(json.dumps(dict(id=ident, node=node, parity=parity,
                                                 alternative=alternative)) + '\n')
                    counts[f'node{node}:separators:parity{parity}'] += 1
    manifest = json.loads((job / 'MANIFEST.json').read_text())
    assert counts['rows'] == manifest['rows']
    assert all(counts[f'node3:separators:parity{p}'] for p in (0, 1))
    save(job / 'STRUCTURAL-HYPOTHESIS.json', dict(status='FROZEN_ENDPOINT_VISIBLE_TIE_CONTROLS',
        rule='Flip exactly one targeted RN64 half decision from nearest/even to nearest/odd; all other arithmetic is unchanged.',
        candidate_rules=['nearest-even', 'nearest-odd', 'ties-away', 'ties-zero'],
        rule_mapping='At retained parity 0, odd equals away and even equals zero; at parity 1, odd equals zero and even equals away.',
        representation='Omitted input/node pairs are the frozen baseline, after evaluating every input.',
        counts=counts, sparse_predictions_sha256=digest(sparse),
        manifest_sha256=digest(job / 'MANIFEST.json'), mining_report_sha256=digest(MINING / 'REPORT.json'),
        hardware_executed=False, hardware_labels_opened=False, numerical_model_changed=False,
        limits='Distinguishes fixed half rules at nodes with actual separators only. Does not identify masked nodes or rule out arbitrary state-dependent rules.'))
    print('PASS frozen discriminators', json.dumps(counts), flush=True)


if __name__ == '__main__':
    freeze('d0046', 'd0046-table-correction-visible-ties-20260906', generate,
        ('prepare_d0046.py', 'd0045_tie_observability.py', 'd0045_tie_observability_miner.c',
         'd0041_inner_tie_miner.c', 'd0041_inner_tie_preimages.py',
         'd0037_polynomial_node_census.py', 'd0031_internal_rounding_coverage.py',
         'prepare_d0033.py', 'prepare_d0042.py', 'PSEUDOCODE.md',
         'graph_v5.py', 'graph_v6.py', 'graph_v7.py', 'd0023_index_hypotheses.py',
         'd0010_causal_intervals.py'), policy=replace(POLICY, numerical_graph='v7'),
        purpose='Endpoint-visible short-kernel correction RN64 ties, both retained parities and fresh external neighborhoods')
    freeze_controls(BASE / 'd0046')
