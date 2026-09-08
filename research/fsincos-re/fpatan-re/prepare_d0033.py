"""Freeze the first exact-square-tie adversarial wall and an explicit control.

All endpoint-visible D0032 witnesses, their 3x3 operand neighbors, exact
table-preimage controls and same-z integer transports are included. The full
D0032 software pool is retained separately for later corpus expansion.
This job uses the existing local history exclusions and remote one-shot guard.
"""
from collections import Counter
from dataclasses import replace
import gzip
import json
from pathlib import Path
import random

from architecture import POLICY
from compressed_guard import digest
import d0031_internal_rounding_coverage as audit
from freeze_stream import freeze
from prepare import save

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'tmp/fpatan-re'
MINING = BASE / 'd0032-square-tie-mining'
SEED = 'fpatan-d0033-exact-square-tie-discriminators-20260906'


def neighbor(exponent, significand, offset):
    """Adjacent normal raw80 values, including either side of a binade."""
    for _ in range(abs(offset)):
        if offset < 0:
            if significand == 1 << 63:
                exponent, significand = exponent - 1, (1 << 64) - 1
            else:
                significand -= 1
        else:
            if significand == (1 << 64) - 1:
                exponent, significand = exponent + 1, 1 << 63
            else:
                significand += 1
    assert 0 < exponent < 32767 and 1 << 63 <= significand < 1 << 64
    return exponent, significand


def orbits(raw):
    ys, ym, xs, xm = raw
    for swap in (False, True):
        a, b = ((xs, xm), (ys, ym)) if swap else ((ys, ym), (xs, xm))
        for sy in (0, 32768):
            for sx in (0, 32768):
                yield a[0] | sy, a[1], b[0] | sx, b[1]


def generate():
    report = json.loads((MINING / 'REPORT.json').read_text())
    assert report['status'] == 'SOFTWARE_CERTIFIED_NOT_FRESHNESS_CLEARED'
    assert digest(MINING / 'candidate-pool.tsv.gz') == report['pool_sha256']
    for witness in report['endpoint_visible']:
        ys, ym, xs, xm = (int(word, 16) for word in witness['raw'])
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                y = neighbor(ys, ym, dy)
                x = neighbor(xs, xm, dx)
                for pair in orbits((*y, *x)):
                    yield pair, f'exact-square-tie-visible-neighbor:{dy}:{dx}'
    for control in report['structural_controls']:
        family = f'exact-square-tie-cell{control["cell"]}:E{control["E"]}:sign{control["residual_sign"]}'
        variants = control['exact_same_z_variants'] or [dict(multiplier=1, raw=control['raw'])]
        for variant in variants:
            raw = tuple(int(word, 16) for word in variant['raw'])
            for pair in orbits(raw):
                yield pair, family + ':same-z-scale'
    rng = random.Random(SEED)
    for _ in range(512):
        pair = (rng.randrange(1, 32767) | (rng.getrandbits(1) << 15),
                rng.getrandbits(63) | (1 << 63),
                rng.randrange(1, 32767) | (rng.getrandbits(1) << 15),
                rng.getrandbits(63) | (1 << 63))
        yield pair, 'independent-full-exponent-control'


def freeze_square_control(job):
    """Pin every ties-away prediction before stage/dispatch or label opening."""
    assert not (job / 'DISPATCHED.json').exists()
    manifest = json.loads((job / 'MANIFEST.json').read_text())
    counts = Counter()
    output = job / 'square-ties-away-predictions.txt.gz'
    with gzip.open(job / 'inputs.txt.gz', 'rt') as inputs, gzip.open(job / 'predictions.txt.gz', 'rt') as fixed, gzip.open(output, 'xt') as target:
        for line, prediction in zip(inputs, fixed, strict=True):
            ident, rc, pc, ys, ym, xs, xm = line.split()
            y, x = audit.Raw80(int(ys, 16), int(ym, 16)), audit.Raw80(int(xs, 16), int(xm, 16))
            state = audit.reduction(audit.core_key(y, x))
            restoration = 2 * int(audit.normalized(y) > audit.normalized(x)) + int(bool(x.se & 32768))
            sign = -1 if y.se & 32768 else 1
            base_angle = sign * audit.angles(state)[restoration]
            other_angle = sign * audit.angles(state, 'ties-away')[restoration]
            base, bc1 = audit.SPEC['pack_angle'](base_angle, rc.upper())
            other, oc1 = audit.SPEC['pack_angle'](other_angle, rc.upper())
            flags = 32 | (16 if abs(base_angle) < audit.two(-16382) else 0)
            assert prediction == f'{ident} {base.se:04x} {base.sig:016x} {bc1} {flags:02x} 00\n'
            other_flags = 32 | (16 if abs(other_angle) < audit.two(-16382) else 0)
            target.write(f'{ident} {other.se:04x} {other.sig:016x} {oc1} {other_flags:02x} 00\n')
            counts['rows'] += 1
            counts['output_separators'] += base != other
            counts['C1_separators'] += bc1 != oc1
            counts['union_separators'] += base != other or bc1 != oc1 or flags != other_flags
    assert counts['rows'] == manifest['rows'] and counts['union_separators'] > 0
    save(job / 'STRUCTURAL-HYPOTHESIS.json', dict(status='FROZEN_ALTERNATIVE_BEFORE_DISPATCH',
        hypothesis='Only the asymmetric square RN64 tie rule is changed from ties-even to ties-away; every other node is V7.',
        control='Deliberately different numerical model; not promoted.', counts=counts,
        alternative_predictions_sha256=digest(output),
        manifest_sha256=digest(job / 'MANIFEST.json'),
        mining_report_sha256=digest(MINING / 'REPORT.json'),
        candidate_pool_sha256=digest(MINING / 'candidate-pool.tsv.gz'),
        census_sha256=digest(BASE / 'd0031-internal-rounding-coverage.json'),
        hardware_executed=False, hardware_labels_opened=False,
        full_pool='Software-only, retained for later expansion; not all pool pairs are in this bounded job.'))
    print('Frozen ties-away control:', dict(counts), flush=True)


if __name__ == '__main__':
    freeze('d0033', SEED, generate,
           ('prepare_d0033.py', 'd0032_square_tie_preimages.py',
            'd0031_internal_rounding_coverage.py', 'PSEUDOCODE.md',
            'graph_v5.py', 'graph_v6.py', 'graph_v7.py',
            'd0023_index_hypotheses.py', 'd0010_causal_intervals.py'),
           policy=replace(POLICY, numerical_graph='v7'),
           purpose='Exact asymmetric-square halfway cases, endpoint-visible ties-away discriminators, adjacent raw operands, all sign/octant/RC orbits, exact table preimages and same-z scale controls')
    freeze_square_control(BASE / 'd0033')
