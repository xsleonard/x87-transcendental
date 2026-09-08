"""Freeze quadrant-boundary neighborhoods and nonzero discarded-history groups.

Every nine-point D0034 window is crossed with three denominator neighbors,
both y signs and all RC. D0035 groups receive all sign/octant orbits. The
two pre-restoration controls are frozen locally before any hardware dispatch;
the main numerical program is unchanged and never uploaded.
"""
from collections import Counter
from dataclasses import replace
from functools import lru_cache
import gzip
import json
from pathlib import Path
import random

from architecture import POLICY
from compressed_guard import digest
import d0031_internal_rounding_coverage as audit
from d0034_quadrant_boundary_mining import ordered_raw
from freeze_stream import freeze
from prepare import save
from prepare_d0033 import neighbor, orbits

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'tmp/fpatan-re'
BOUNDARIES = BASE / 'd0034-quadrant-boundaries'
HISTORIES = BASE / 'd0035-cut-history-groups'
SEED = 'fpatan-d0036-restored-boundaries-nonzero-cut-history-20260906'
CONTROLS = ('pre-restore-chop64', 'omit-pre-restore-cut')


def generate():
    boundary = json.loads((BOUNDARIES / 'REPORT.json').read_text())
    assert digest(BOUNDARIES / 'seeds.tsv') == boundary['seeds_sha256']
    history = json.loads((HISTORIES / 'REPORT.json').read_text())
    assert digest(HISTORIES / 'candidate-pool.tsv') == history['pool_sha256']
    for line in (BOUNDARIES / 'seeds.tsv').read_text().splitlines():
        ident, family, quadrant, rc, offset, ase, am, bse, bm, _, _, _ = line.split()
        a, b = (int(ase, 16), int(am, 16)), (int(bse, 16), int(bm, 16))
        for dx in (-1, 0, 1):
            for sign in (False, True):
                raw = ordered_raw(a, neighbor(*b, dx), int(quadrant), sign)
                label = f'quadrant-boundary:q{quadrant}:{rc}:a{offset}:b{dx}:seed{ident}'
                yield raw, label
    for group in history['groups']:
        for member in group['members']:
            raw = tuple(int(word, 16) for word in member['raw'])
            for pair in orbits(raw):
                yield pair, f'nonzero-cut-history:group{group["id"]}:cell{group["cell"]}'
    rng = random.Random(SEED)
    for _ in range(2048):
        pair = (rng.randrange(1, 32767) | (rng.getrandbits(1) << 15),
                rng.getrandbits(63) | (1 << 63),
                rng.randrange(1, 32767) | (rng.getrandbits(1) << 15),
                rng.getrandbits(63) | (1 << 63))
        yield pair, 'independent-full-exponent-control'


@lru_cache(maxsize=8192)
def positive_values(key):
    state = audit.reduction(key)
    fixed = audit.angles(state)
    angle = fixed[0]
    c64 = audit.T(angle, 64)
    return dict(fixed=fixed,
        **{'pre-restore-chop64': (angle, audit.ROM[19] - c64,
                                audit.ROM[20] - c64, audit.ROM[20] + c64),
           'omit-pre-restore-cut': (angle, audit.ROM[19] - angle,
                                   audit.ROM[20] - angle, audit.ROM[20] + angle)})


def prediction(angle, rc):
    value, c1 = audit.SPEC['pack_angle'](angle, rc.upper())
    flags = 32 | (16 if abs(angle) < audit.two(-16382) else 0)
    return value.se, value.sig, c1, flags, 0


def freeze_controls(job):
    assert not (job / 'DISPATCHED.json').exists()
    counts = {name: Counter() for name in CONTROLS}
    targets = {name: gzip.open(job / (name + '.txt.gz'), 'xt') for name in CONTROLS}
    total = 0
    try:
        with gzip.open(job / 'inputs.txt.gz', 'rt') as inputs, gzip.open(job / 'predictions.txt.gz', 'rt') as fixed:
            for line, reference in zip(inputs, fixed, strict=True):
                ident, rc, pc, ys, ym, xs, xm = line.split()
                y, x = audit.Raw80(int(ys, 16), int(ym, 16)), audit.Raw80(int(xs, 16), int(xm, 16))
                q = 2 * int(audit.normalized(y) > audit.normalized(x)) + int(bool(x.se & 32768))
                sign = -1 if y.se & 32768 else 1
                values = positive_values(audit.core_key(y, x))
                baseline = prediction(sign * values['fixed'][q], rc)
                expected = tuple(int(word, 16) for word in reference.split()[1:])
                assert reference.split()[0] == ident and baseline == expected
                for name in CONTROLS:
                    other = prediction(sign * values[name][q], rc)
                    counts[name]['rows'] += 1
                    counts[name]['output_separators'] += baseline[:2] != other[:2]
                    counts[name]['C1_separators'] += baseline[2] != other[2]
                    counts[name]['union_separators'] += baseline != other
                    se, sig, c1, flags, before = other
                    targets[name].write(f'{ident} {se:04x} {sig:016x} {c1} {flags:02x} {before:02x}\n')
                total += 1
                if total % 100000 == 0:
                    print('Frozen restoration controls', total, flush=True)
    finally:
        for stream in targets.values():
            stream.close()
    manifest = json.loads((job / 'MANIFEST.json').read_text())
    assert total == manifest['rows']
    assert all(count['union_separators'] for count in counts.values())
    save(job / 'STRUCTURAL-HYPOTHESIS.json', dict(status='FROZEN_RESTORATION_CONTROLS_BEFORE_DISPATCH',
        controls='Change only the pre-quadrant CHOP67 cut: CHOP64, or omit it. Both controls are analysis-only.',
        counts=counts, prediction_sha256={name: digest(job / (name + '.txt.gz')) for name in CONTROLS},
        manifest_sha256=digest(job / 'MANIFEST.json'),
        boundary_report_sha256=digest(BOUNDARIES / 'REPORT.json'),
        history_report_sha256=digest(HISTORIES / 'REPORT.json'),
        history_group_definition='Same nonzero path/cell/z, signed quadrant and RC/PC, with different nonzero CHOP67 denominator remainders.',
        hardware_executed=False, hardware_labels_opened=False, numerical_model_changed=False))
    print('PASS frozen restoration controls', json.dumps(counts), flush=True)


if __name__ == '__main__':
    freeze('d0036', SEED, generate,
        ('prepare_d0036.py', 'd0034_quadrant_boundary_miner.c',
         'd0034_quadrant_boundary_mining.py', 'd0035_cut_history_groups.py',
         'd0031_internal_rounding_coverage.py', 'prepare_d0033.py', 'PSEUDOCODE.md',
         'graph_v5.py', 'graph_v6.py', 'graph_v7.py', 'd0023_index_hypotheses.py',
         'd0010_causal_intervals.py'), policy=replace(POLICY, numerical_graph='v7'),
        purpose='Independently mined restored-quadrant result/C1 boundary windows, both-operand neighbors, exact nonzero discarded-history collision groups, and independent full-exponent controls')
    freeze_controls(BASE / 'd0036')
