"""Freeze the complete D0039 inverse-tie pool and its endpoint neighborhoods.

All independently verified external pairs receive eight sign/octant orbits
and four RC. Visible witnesses also receive a 5x5 raw-operand neighborhood
and exact common scales at the normal exponent limits. The sole alternative
flips exact halfway decisions at correction_sum only, leaving every other
node untouched. No experimental behavior is installed in the main program.
"""
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
from freeze_stream import freeze
from prepare import save
from prepare_d0033 import neighbor, orbits

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'tmp/fpatan-re'
MINING = BASE / 'd0039-correction-ties'
SEED = 'fpatan-d0040-inverse-correction-sum-halfways-20260906'
CONTROL = 'correction-ties-odd'


def generate():
    report = json.loads((MINING / 'REPORT.json').read_text())
    assert report['status'] == 'INDEPENDENTLY_VERIFIED_CORRECTION_SUM_TIES'
    assert digest(MINING / 'candidate-pool.tsv') == report['pool_sha256']
    # Every base pair is admitted, not only the endpoint-visible successes.
    with (MINING / 'candidate-pool.tsv').open() as stream:
        for line in stream:
            ident, uexp, usig, zm, zs, ys, ym, xs, xm, mask = line.split()
            raw = tuple(int(word, 16) for word in (ys, ym, xs, xm))
            for pair in orbits(raw):
                yield pair, f'correction-tie-pool:e{uexp}:seed{ident}'
    for number, witness in enumerate(report['visible_witnesses']):
        ys, ym, xs, xm = (int(word, 16) for word in witness['raw'])
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                raw = (*neighbor(ys, ym, dy), *neighbor(xs, xm, dx))
                for pair in orbits(raw):
                    yield pair, f'visible-correction-neighbor:seed{number}:y{dy}:x{dx}'
        for shift in (1 - ys, 32766 - xs, 97):
            assert 1 <= ys + shift <= xs + shift <= 32766
            a, b = audit.Raw80(ys + shift, ym), audit.Raw80(xs + shift, xm)
            assert audit.core_key(a, b) == audit.core_key(audit.Raw80(ys, ym), audit.Raw80(xs, xm))
            for pair in orbits((a.se, a.sig, b.se, b.sig)):
                yield pair, f'visible-correction-scale:seed{number}:shift{shift}'


@lru_cache(maxsize=8192)
def positive_values(key):
    state = audit.reduction(key)
    assert state['path'] == 'direct'
    fixed, records = traced_kernel(state['z'], False)
    record = next(r for r in records if r[0] == 'correction_sum')
    tie = record[3] == 'tie'
    other = fixed
    if tie:
        other, _ = traced_kernel(state['z'], False,
            ('correction_sum', 'ties-away' if record[4] == 0 else 'ties-zero'))
    return restored(state, fixed), restored(state, other), tie, record[4]


def prediction(angle, rc):
    result, c1 = audit.SPEC['pack_angle'](angle, rc.upper())
    assert abs(angle) >= audit.two(-16382)
    return result.se, result.sig, c1, 32, 0


def freeze_control(job):
    assert not (job / 'DISPATCHED.json').exists()
    counts, ties = Counter(), Counter()
    target_path = job / (CONTROL + '.txt.gz')
    with gzip.open(job / 'inputs.txt.gz', 'rt') as inputs, \
         gzip.open(job / 'predictions.txt.gz', 'rt') as fixed, \
         gzip.open(target_path, 'xt') as target:
        for line, reference in zip(inputs, fixed, strict=True):
            ident, rc, pc, ys, ym, xs, xm = line.split()
            y, x = audit.Raw80(int(ys, 16), int(ym, 16)), audit.Raw80(int(xs, 16), int(xm, 16))
            q = 2 * int(audit.normalized(y) > audit.normalized(x)) + int(bool(x.se & 32768))
            sign = -1 if y.se & 32768 else 1
            base, alternative, tie, parity = positive_values(audit.core_key(y, x))
            baseline = prediction(sign * base[q], rc)
            other = prediction(sign * alternative[q], rc)
            assert reference.split()[0] == ident
            assert baseline == tuple(int(word, 16) for word in reference.split()[1:])
            se, sig, c1, flags, before = other
            target.write(f'{ident} {se:04x} {sig:016x} {c1} {flags:02x} {before:02x}\n')
            counts['rows'] += 1
            counts['output_separators'] += baseline[:2] != other[:2]
            counts['C1_separators'] += baseline[2] != other[2]
            counts['union_separators'] += baseline != other
            ties[f'tie{int(tie)}:parity{parity}'] += 1
            if counts['rows'] % 100000 == 0:
                print('Frozen correction control', counts['rows'], flush=True)
    manifest = json.loads((job / 'MANIFEST.json').read_text())
    assert counts['rows'] == manifest['rows'] and counts['union_separators'] > 0
    save(job / 'STRUCTURAL-HYPOTHESIS.json', dict(status='FROZEN_CORRECTION_TIE_CONTROL_BEFORE_DISPATCH',
        control=CONTROL, hypothesis='Only exact halfway decisions at the direct kernel correction_sum RN64 node change from nearest/even to nearest/odd.',
        counts=counts, tie_observation_counts=ties,
        alternative_predictions_sha256=digest(target_path),
        manifest_sha256=digest(job / 'MANIFEST.json'), mining_report_sha256=digest(MINING / 'REPORT.json'),
        candidate_pool_sha256=digest(MINING / 'candidate-pool.tsv'),
        hardware_executed=False, hardware_labels_opened=False, numerical_model_changed=False,
        limits='Complete D0039 software pool is submitted to history admission; this is a bounded set, not exhaustive rounding-node coverage. The alternative is a control, not a promoted model.'))
    print('PASS frozen correction control', json.dumps(dict(counts=counts, ties=ties)), flush=True)


if __name__ == '__main__':
    freeze('d0040', SEED, generate,
        ('prepare_d0040.py', 'd0039_correction_tie_miner.c', 'd0039_correction_tie_mining.py',
         'd0037_polynomial_node_census.py', 'd0031_internal_rounding_coverage.py',
         'prepare_d0033.py', 'PSEUDOCODE.md', 'graph_v5.py', 'graph_v6.py', 'graph_v7.py',
         'd0023_index_hypotheses.py', 'd0010_causal_intervals.py'),
        policy=replace(POLICY, numerical_graph='v7'),
        purpose='The complete exact correction-sum-halfway external pool, endpoint-visible 5x5 operand neighborhoods, sign/octant/RC orbits and normal-exponent-limit transports')
    freeze_control(BASE / 'd0040')
