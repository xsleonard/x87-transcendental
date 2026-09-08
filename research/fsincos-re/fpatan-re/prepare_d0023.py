"""Fresh exact-midpoint / denominator discriminator with frozen alternatives.

All cells receive varied exactly represented ratios, power-of-two and full
significand denominators, signs/octants/scales, and one-sided neighbors.
Global lower/upper/parity tie rules compete with explicit reciprocal index
construction. Alternative model outputs remain LOCAL, never uploaded.
"""
import collections
from dataclasses import replace
import gzip
import hashlib
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

SEED = 'fpatan-d0023-exact-midpoints-denominator-and-parity-20260905'


def orbit(pair, rng):
    ys, ym, xs, xm = pair
    for swap in (False, True):
        for sy in (0, 32768):
            for sx in (0, 32768):
                shift = rng.randrange(-15000, 15001)
                y, x = (ys + shift, ym), (xs + shift, xm)
                if swap:
                    y, x = x, y
                assert 0 < y[0] < 32767 and 0 < x[0] < 32767
                yield y[0] | sy, y[1], x[0] | sx, x[1]


def generate():
    rng = random.Random(SEED)
    for n in range(1, 32):
        ratio = F(2*n+1, 64)
        denominators = [1 << 63, (1 << 63) + 64, (1 << 64) - 64, 0xaaaaaaaaaaaaaa80]
        denominators += [(rng.getrandbits(63) | (1 << 63)) & ~63 for _ in range(128)]
        for j, xm in enumerate(denominators):
            x = value(16383, xm)
            ys, ym = encode(x * ratio)
            assert value(ys, ym) == x * ratio
            for pair in orbit((ys, ym, 16383, xm), rng):
                yield pair, f'exact-midpoint-{2*n+1:02d}-' + ('power2-denominator' if j == 0 else 'varied-denominator')
            if j < 16:
                for delta in (-64, -1, 1, 64):
                    if not (1 << 63) <= ym + delta < (1 << 64):
                        continue
                    for pair in orbit((ys, ym + delta, 16383, xm), rng):
                        yield pair, f'midpoint-neighbor-{2*n+1:02d}-{delta:+d}'


def main():
    freeze('d0023', SEED, generate,
           ('prepare_d0023.py', 'graph_v5.py', 'graph_v6.py', 'graph_v7.py',
            'd0023_index_hypotheses.py', 'd0010_causal_intervals.py', 'fpatan_candidate_v7.c'),
           policy=replace(POLICY, numerical_graph='v7'),
           purpose='Prospective exact-midpoint and denominator discrimination: all cells, signs/octants, scale, neighboring ratios and frozen global index alternatives')
    root = BASE / 'd0023'
    destination = root / 'index-alternatives.jsonl.gz'
    count = 0
    signature_counts = collections.Counter()
    last, byrule = None, None
    with destination.open('xb') as rawout:
        with gzip.GzipFile(filename='', mode='wb', fileobj=rawout, mtime=0, compresslevel=6) as output:
            with gzip.open(root / 'inputs.txt.gz', 'rt') as inputs, gzip.open(root / 'predictions.txt.gz', 'rt') as predictions:
                for line, frozen in zip(inputs, predictions):
                    tokens = line.split()
                    raw = tuple(int(v, 16) for v in tokens[3:])
                    if raw != last:
                        last = raw
                        y, x = abs(value(*raw[:2])), abs(value(*raw[2:]))
                        if y > x:
                            y, x = x, y
                        byindex, byrule = {}, {}
                        for rule in HYPOTHESES:
                            selected = index(y, x, rule)
                            dispatch = 0 if selected < 2 else selected
                            if dispatch not in byindex:
                                byindex[dispatch] = prevalue(*raw, index_rule=rule)
                            byrule[rule] = (dispatch, byindex[dispatch])
                    expected = {}
                    for rule, (selected, v) in byrule.items():
                        se, sig = encode(v, tokens[1])
                        expected[rule] = [se, sig, int(abs(value(se, sig)) > abs(v)), 32, 0]
                    primary = [int(v, 16) for v in frozen.split()[1:]]
                    assert expected['lower'] == primary
                    signature = '|'.join(rule for rule in HYPOTHESES[1:] if expected[rule] != primary)
                    signature_counts[signature or 'all-agree'] += 1
                    record = dict(input=line.strip(), expected=expected,
                                  dispatched_index={r:n for r,(n,v) in byrule.items()})
                    output.write((json.dumps(record, separators=(',', ':')) + '\n').encode())
                    count += 1
            output.flush()
        rawout.flush(); os.fsync(rawout.fileno())
    manifest = json.loads((root / 'MANIFEST.json').read_text())
    assert count == manifest['rows']
    save(root / 'INDEX-HYPOTHESES.json', dict(status='FROZEN_ALTERNATIVES_UNOPENED',
         manifest_sha256=digest(root / 'MANIFEST.json'), alternatives_sha256=digest(destination),
         rows=count, hypotheses=HYPOTHESES, signature_counts=dict(signature_counts),
         primary='lower', hardware_executed=False, numerical_model_promoted=False,
         limitation='Alternative hypotheses are fixed arithmetic rules, not recovered hardware states; no labels have been opened.'))
    print('FROZEN seven index hypotheses', count, 'rows;', dict(signature_counts), flush=True)


if __name__ == '__main__':
    main()
