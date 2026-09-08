"""Freeze all verified early/table halfways and 3x3 external neighborhoods."""
from collections import Counter
from dataclasses import replace
from functools import lru_cache
import gzip
import json
from pathlib import Path

from architecture import POLICY
from compressed_guard import digest
import d0031_internal_rounding_coverage as audit
from d0037_polynomial_node_census import restored, traced_kernel
from d0041_inner_tie_preimages import NODES
from freeze_stream import freeze
from prepare import save
from prepare_d0033 import neighbor, orbits

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'tmp/fpatan-re'
MINING = BASE / 'd0041-inner-ties'
SEED = 'd0042-early-and-table-exact-halfways-neighbors-20260906'


def generate():
    report = json.loads((MINING / 'REPORT.json').read_text())
    assert report['status'] == 'EXACT_EARLY_AND_TABLE_HALF_PREIMAGES_VERIFIED'
    assert digest(MINING / 'candidate-pool.tsv') == report['pool_sha256']
    with (MINING / 'candidate-pool.tsv').open() as stream:
        for index, line in enumerate(stream):
            node, ident, cell, sign, ys, ym, xs, xm, parity, mask, zm, zs = line.split()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    a = neighbor(int(ys, 16), int(ym, 16), dy)
                    b = neighbor(int(xs, 16), int(xm, 16), dx)
                    for raw in orbits((*a, *b)):
                        yield raw, f'node{node}:cell{cell}:sign{sign}:seed{index}:y{dy}:x{dx}'


@lru_cache(maxsize=8192)
def values(key):
    state = audit.reduction(key)
    assert state['path'] in ('direct', 'table')
    table = state['path'] == 'table'
    value, records = traced_kernel(state['z'], table)
    baseline = restored(state, value)
    alternatives, events = {}, {}
    nodes = {record[0]: record for record in records}
    for node in ((2, 3) if table else (0, 1)):
        record = nodes[NODES[node]]
        events[node] = record[3], record[4]
        if record[3] == 'tie':
            other, _ = traced_kernel(state['z'], table,
                (NODES[node], 'ties-away' if record[4] == 0 else 'ties-zero'))
            alternatives[node] = restored(state, other)
    return baseline, alternatives, events


def freeze_controls(job):
    assert not (job / 'DISPATCHED.json').exists()
    counts, events = Counter(), Counter()
    sparse_path = job / 'CONTROL-DIFFERENCES.jsonl.gz'
    with gzip.open(job / 'inputs.txt.gz', 'rt') as inputs, \
         gzip.open(job / 'predictions.txt.gz', 'rt') as predictions, \
         gzip.open(sparse_path, 'xt') as sparse:
        for line, expected in zip(inputs, predictions, strict=True):
            ident, rc, pc, ys, ym, xs, xm = line.split()
            y, x = audit.Raw80(int(ys, 16), int(ym, 16)), audit.Raw80(int(xs, 16), int(xm, 16))
            baseline, alternatives, node_events = values(audit.core_key(y, x))
            quadrant = 2 * int(audit.normalized(y) > audit.normalized(x)) + int(bool(x.se & 32768))
            sign = -1 if y.se & 32768 else 1
            result, c1 = audit.SPEC['pack_angle'](sign * baseline[quadrant], rc.upper())
            reference = (result.se, result.sig, c1, 32, 0)
            assert expected.split()[0] == ident
            assert reference == tuple(int(word, 16) for word in expected.split()[1:])
            for node, event in node_events.items():
                events[f'{node}:{event[0]}:parity{event[1]}'] += 1
            for node, alternate in alternatives.items():
                value, flag = audit.SPEC['pack_angle'](sign * alternate[quadrant], rc.upper())
                other = (value.se, value.sig, flag, 32, 0)
                counts[f'node{node}:exact_ties'] += 1
                counts[f'node{node}:output_separators'] += other[:2] != reference[:2]
                counts[f'node{node}:C1_separators'] += other[2] != reference[2]
                counts[f'node{node}:union_separators'] += other != reference
                if other != reference:
                    sparse.write(json.dumps(dict(id=ident, node=node, alternative=other)) + '\n')
            counts['rows'] += 1
            if counts['rows'] % 200000 == 0:
                print('Checked frozen node controls', counts['rows'], flush=True)
    manifest = json.loads((job / 'MANIFEST.json').read_text())
    assert counts['rows'] == manifest['rows']
    save(job / 'STRUCTURAL-HYPOTHESIS.json', dict(status='FROZEN_EARLY_TABLE_TIE_CONTROLS',
        controls={str(i): ('direct:' if i < 2 else 'table:') + name for i, name in enumerate(NODES)},
        rule='Each independent control flips nearest/even to nearest/odd at exact halfways of only its named RN64 addition; other nodes are unchanged.',
        representation='Sparse per-control overrides. Every omitted input/control pair is exactly the frozen baseline; every input was evaluated before capture.',
        counts=counts, event_counts=events, sparse_predictions_sha256=digest(sparse_path),
        manifest_sha256=digest(job / 'MANIFEST.json'),
        mining_report_sha256=digest(MINING / 'REPORT.json'), pool_sha256=digest(MINING / 'candidate-pool.tsv'),
        hardware_executed=False, hardware_labels_opened=False, numerical_model_changed=False,
        limits='Exact halfway coverage does not distinguish hidden tie behavior where its effect is masked. Bounded searches and local windows are not exhaustive.'))
    print('PASS frozen early/table controls', json.dumps(counts), flush=True)


if __name__ == '__main__':
    freeze('d0042', SEED, generate,
        ('prepare_d0042.py', 'd0041_inner_tie_miner.c', 'd0041_inner_tie_preimages.py',
         'd0037_polynomial_node_census.py', 'd0031_internal_rounding_coverage.py',
         'prepare_d0033.py', 'PSEUDOCODE.md', 'graph_v5.py', 'graph_v6.py', 'graph_v7.py',
         'd0023_index_hypotheses.py', 'd0010_causal_intervals.py'),
        policy=replace(POLICY, numerical_graph='v7'),
        purpose='All exact early/table RN64-halfway raw80 pairs, full 3x3 operand neighborhoods and all sign/octant/RC orbits')
    freeze_controls(BASE / 'd0042')
