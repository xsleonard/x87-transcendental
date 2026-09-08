"""Fresh unmasked-denominator challenge; immutable local index predictions.

Includes software-selected mechanism separators, their immediate neighbors,
and independent near-midpoint ratios. Labels from this campaign are never
read by preparation, and the normal private/public/prior tuple holds apply.
"""
import collections
from dataclasses import replace
import gzip
import itertools
import json
import os
import random

from architecture import POLICY
from compressed_guard import digest
from d0010_causal_intervals import BASE
from d0023_index_hypotheses import HYPOTHESES, index
from freeze_stream import freeze
from graph_v7 import prevalue
from model import F, encode, value
from prepare import save

SEED = 'fpatan-d0024-low-bit-separators-and-neighbor-controls-20260905'


def orbit(raw, rng, full=True):
    choices = [(s, a, b) for s in (False, True) for a in (0, 32768) for b in (0, 32768)]
    if not full:
        choices = [rng.choice(choices)]
    for swap, sy, sx in choices:
        shift = rng.randrange(-15000, 15001)
        a, b = (raw[0]+shift, raw[1]), (raw[2]+shift, raw[3])
        if swap:
            a, b = b, a
        assert 0 < a[0] < 32767 and 0 < b[0] < 32767
        yield a[0] | sy, a[1], b[0] | sx, b[1]


def generate():
    rng = random.Random(SEED)
    mining = json.loads((BASE / 'd0024-index-residue-mining.json').read_text())
    for witness in mining['witnesses']:
        raw = witness['raw']
        for p in orbit(raw, rng):
            yield p, 'mined-' + witness['signature']
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            changed = raw[0], raw[1]+dy, raw[2], raw[3]+dx
            if not all((1 << 63) <= changed[i] < (1 << 64) for i in (1, 3)):
                continue
            for p in orbit(changed, rng, False):
                yield p, 'separator-adjacent-control'
    for i in range(8192):
        n = 1 + i % 31
        xm = rng.getrandbits(63) | (1 << 63)
        ys, ym = encode(F(xm*(2*n+1), 64*(1 << 63)))
        delta = rng.choice((-1, 0, 0, 0, 1))
        if not (1 << 63) <= ym+delta < (1 << 64):
            continue
        for p in orbit((ys, ym+delta, 16383, xm), rng, False):
            yield p, 'independent-unmasked-midpoint-neighborhood'


def freeze_alternatives(root):
    count = 0
    signatures = collections.Counter()
    last = None
    byrule = {}
    with (root / 'index-alternatives.jsonl.gz').open('xb') as rawout:
        with gzip.GzipFile(filename='', mode='wb', fileobj=rawout, mtime=0) as output, \
             gzip.open(root / 'inputs.txt.gz', 'rt') as inputs, \
             gzip.open(root / 'predictions.txt.gz', 'rt') as predictions:
            for line, frozen in itertools.zip_longest(inputs, predictions):
                assert line is not None and frozen is not None
                tokens = line.split()
                raw = tuple(int(v, 16) for v in tokens[3:])
                if raw != last:
                    last = raw
                    y, x = sorted((abs(value(*raw[:2])), abs(value(*raw[2:]))))
                    byindex, byrule = {}, {}
                    for rule in HYPOTHESES:
                        selected = index(y, x, rule)
                        dispatch = 0 if selected < 2 else selected
                        if dispatch not in byindex:
                            byindex[dispatch] = prevalue(*raw, index_rule=rule)
                        byrule[rule] = dispatch, byindex[dispatch]
                expected = {}
                for rule, (selected, v) in byrule.items():
                    se, sig = encode(v, tokens[1])
                    expected[rule] = [se, sig, int(abs(value(se, sig)) > abs(v)), 32, 0]
                assert frozen.split()[0] == tokens[0]
                primary = [int(v, 16) for v in frozen.split()[1:]]
                assert expected['lower'] == primary
                signature = '|'.join(r for r in HYPOTHESES[1:] if expected[r] != primary)
                signatures[signature or 'all-agree'] += 1
                output.write((json.dumps(dict(input=line.strip(), expected=expected,
                    dispatched_index={r: n for r, (n, v) in byrule.items()}), separators=(',', ':'))+'\n').encode())
                count += 1
        rawout.flush()
        os.fsync(rawout.fileno())
    manifest = json.loads((root / 'MANIFEST.json').read_text())
    assert count == manifest['rows']
    save(root / 'INDEX-HYPOTHESES.json', dict(status='FROZEN_ALTERNATIVES_UNOPENED',
        manifest_sha256=digest(root / 'MANIFEST.json'),
        alternatives_sha256=digest(root / 'index-alternatives.jsonl.gz'),
        mining_sha256=digest(BASE / 'd0024-index-residue-mining.json'),
        rows=count, hypotheses=HYPOTHESES, signature_counts=signatures, primary='lower',
        hardware_executed=False, numerical_model_promoted=False))
    print('FROZEN alternatives:', count, 'rows;', dict(signatures), flush=True)


if __name__ == '__main__':
    freeze('d0024', SEED, generate,
           ('prepare_d0024.py', 'd0024_index_residue_mining.py', 'graph_v5.py',
            'graph_v6.py', 'graph_v7.py', 'd0023_index_hypotheses.py',
            'd0010_causal_intervals.py', 'fpatan_candidate_v7.c',
            'd0023_score_index.py', 'd0024_score_index.py'),
           policy=replace(POLICY, numerical_graph='v7'),
           purpose='Prospective unmasked denominator/index-separator challenge, all cells, signs/octants, neighboring inputs and independently seeded near-midpoints')
    freeze_alternatives(BASE / 'd0024')
