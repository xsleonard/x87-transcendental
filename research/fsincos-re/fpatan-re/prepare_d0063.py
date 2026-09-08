"""Freeze both-parity, endpoint-visible long odd-inner tie discriminators."""
from collections import Counter
from dataclasses import replace
import gzip
import json
from pathlib import Path

from architecture import POLICY
from compressed_guard import digest
import d0031_internal_rounding_coverage as audit
from d0037_polynomial_node_census import restored, traced_kernel
from freeze_stream import freeze
from prepare import save
from prepare_d0033 import neighbor, orbits
from prepare_d0042 import values

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'tmp/fpatan-re'
MINING = (BASE / 'd0062-long-prefix2',)


def witnesses():
    parities, result = Counter(), []
    for directory in MINING:
        report = json.loads((directory / 'REPORT.json').read_text())
        assert report['status'] == 'VERIFIED_LIVE_SCAN_PREFIX_ENDPOINT_WITNESSES'
        assert digest(directory / 'targets-prefix.tsv') == report['prefix_sha256']
        assert report['scan_completion_claimed'] is False
        for source, sha in report['source_sha256'].items():
            assert digest(HERE / source) == sha
        for row in report['witnesses']:
            assert row['status'] == 'EXACT_EXTERNAL_ENDPOINT_SEPARATOR' and row['node'] == 0
            ys, ym, xs, xm = (int(word, 16) for word in row['raw'])
            y, x = audit.Raw80(ys, ym), audit.Raw80(xs, xm)
            state = audit.reduction(audit.core_key(y, x))
            assert state['path'] == 'direct' and state['z'] == int(row['z_sig'], 16) * audit.two(row['z_step'])
            first, records = traced_kernel(state['z'], False)
            event = next(r for r in records if r[0] == 'odd_inner_sum')
            assert event[3:5] == ('tie', row['parity'])
            second, _ = traced_kernel(state['z'], False,
                ('odd_inner_sum', 'ties-away' if row['parity'] == 0 else 'ties-zero'))
            a, b = audit.endpoint_vector(restored(state, first)), audit.endpoint_vector(restored(state, second))
            mask = sum((v != w) << i for i, (v, w) in enumerate(zip(a, b)))
            assert mask == int(row['endpoint_mask'], 16) and mask
            assert first == audit.SPEC['finite_angle'](y, x)
            parities[row['parity']] += 1
            result.append(row)
    assert all(parities[p] for p in (0, 1))
    return result


def generate():
    for index, row in enumerate(witnesses()):
        ys, ym, xs, xm = (int(word, 16) for word in row['raw'])
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                a, b = neighbor(ys, ym, dy), neighbor(xs, xm, dx)
                for raw in orbits((*a, *b)):
                    yield raw, f'node0:seed{index}:parity{row["parity"]}:y{dy}:x{dx}'


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
            baseline, alternatives, events = values(audit.core_key(y, x))
            quadrant = 2 * int(audit.normalized(y) > audit.normalized(x)) + int(bool(x.se & 32768))
            sign = -1 if y.se & 32768 else 1
            result, c1 = audit.SPEC['pack_angle'](sign * baseline[quadrant], rc.upper())
            reference = result.se, result.sig, c1, 32, 0
            assert expected.split()[0] == ident
            assert reference == tuple(int(word, 16) for word in expected.split()[1:])
            counts['rows'] += 1
            for node, (event, parity) in events.items():
                counts[f'node{node}:{event}:parity{parity}'] += 1
                if event != 'tie':
                    continue
                result, flag = audit.SPEC['pack_angle'](sign * alternatives[node][quadrant], rc.upper())
                alternative = result.se, result.sig, flag, 32, 0
                if alternative != reference:
                    output.write(json.dumps(dict(id=ident, node=node, parity=parity, alternative=alternative)) + '\n')
                    counts[f'node{node}:separators:parity{parity}'] += 1
    manifest = json.loads((job / 'MANIFEST.json').read_text())
    assert counts['rows'] == manifest['rows']
    assert all(counts[f'node0:separators:parity{p}'] for p in (0, 1))
    save(job / 'STRUCTURAL-HYPOTHESIS.json', dict(status='FROZEN_ENDPOINT_VISIBLE_TIE_CONTROLS',
        target_nodes=[0], candidate_rules=['nearest-even', 'nearest-odd', 'ties-away', 'ties-zero'],
        rule='Change only one named RN64 exact-half decision; all other arithmetic stays fixed.',
        rule_mapping='At retained parity 0, odd equals away and even equals zero; at parity 1, odd equals zero and even equals away.',
        representation='Every input/node is evaluated. Omitted sparse overrides exactly equal the baseline.',
        counts=counts, sparse_predictions_sha256=digest(sparse),
        manifest_sha256=digest(job / 'MANIFEST.json'),
        mining_report_sha256={d.name: digest(d / 'REPORT.json') for d in MINING},
        hardware_executed=False, hardware_labels_opened=False, numerical_model_changed=False,
        limits='Identifies only fixed rules at nodes with separating observations; not masked nodes or arbitrary state-dependent alternatives.'))
    print('PASS frozen both-parity controls', json.dumps(counts), flush=True)


if __name__ == '__main__':
    freeze('d0063', 'd0063-long-odd-inner-visible-ties-20260906', generate,
        ('prepare_d0063.py', 'd0062_freeze_long_prefix.py', 'd0060_long_odd_sweep.py', 'd0060_fast_offsets.py', 'd0060_boundary_offsets.c', 'd0056_outer_boundary_lattice.py', 'd0049_algebraic_tie_preimages.py',
         'd0045_tie_observability.py', 'd0037_polynomial_node_census.py',
         'd0031_internal_rounding_coverage.py', 'prepare_d0033.py', 'prepare_d0042.py',
         'PSEUDOCODE.md', 'graph_v5.py', 'graph_v6.py', 'graph_v7.py',
         'd0023_index_hypotheses.py', 'd0010_causal_intervals.py'),
        policy=replace(POLICY, numerical_graph='v7'),
        purpose='Exact long odd-inner RN64 tie witnesses at both retained parities, full 3x3 operand neighborhoods and all sign/octant/RC orbits')
    freeze_controls(BASE / 'd0063')

