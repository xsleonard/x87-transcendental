"""Software-only index discriminators with unrestricted denominator low bits.

Unlike D0023, this scan does not force the denominator to a multiple of 64.
It covers each low-byte residue at fixed seeded high words and at the y-binade
transition in every midpoint cell. This is a bounded scan, not exhaustion of
the 64-bit denominator domain. No hardware labels are read or captured.
"""
import collections
import json
from pathlib import Path
import random

from compressed_guard import digest
from d0010_causal_intervals import BASE
from d0023_index_hypotheses import HYPOTHESES, index
from graph_v7 import prevalue
from model import F, ROM, cut, encode, value
from prepare import save

SEED = 'fpatan-d0024-unmasked-denominator-residues-20260905'


def generated():
    rng = random.Random(SEED)
    for n in range(1, 32):
        m = 2*n+1
        # y's normalization changes at m*S == 2**(64+floor(log2(m))).
        transition = ((1 << (64 + m.bit_length()-1)) + m-1) // m
        high = {1 << 63, 3 << 62, (1 << 64)-256,
                transition & ~255, (transition & ~255)-256}
        high |= {(rng.getrandbits(63) | (1 << 63)) & ~255 for _ in range(5)}
        for base in sorted(high):
            for low in range(256):
                xm = base + low
                if not (1 << 63) <= xm < (1 << 64):
                    continue
                ys, ym = encode(F(xm*m, 64*(1 << 63)))
                for delta in (-1, 0, 1):
                    if not (1 << 63) <= ym+delta < (1 << 64):
                        continue
                    yield n, (ys, ym+delta, 16383, xm)


def endpoints(v):
    # These are precisely the quadrant transforms after the unsigned kernel.
    # Cross-check them against the complete graph before keeping witnesses.
    chopped = cut(v, 'chop67')
    quadrants = (v, ROM[19]-chopped, ROM[20]-chopped, ROM[20]+chopped)
    result = []
    for positive in quadrants:
        for sign in (1, -1):
            for rc in ('rn', 'rd', 'ru', 'rz'):
                q = encode(sign*positive, rc)
                result.append((*q, int(abs(value(*q)) > abs(positive))))
    return tuple(result)


def main():
    counts = collections.Counter()
    per_cell = collections.defaultdict(collections.Counter)
    signatures = collections.Counter()
    witnesses = []
    seen = set()
    for n, raw in generated():
        if raw in seen:
            continue
        seen.add(raw)
        counts['pairs'] += 1
        y, x = value(*raw[:2]), value(*raw[2:])
        ratio = y/x
        side = 'exact' if ratio == F(2*n+1, 64) else 'below' if ratio < F(2*n+1, 64) else 'above'
        per_cell[n][side] += 1
        selected = {rule: index(y, x, rule) for rule in HYPOTHESES}
        dispatched = {rule: 0 if j < 2 else j for rule, j in selected.items()}
        if len(set(dispatched.values())) > 1:
            counts['index_disagreements'] += 1
            byindex = {}
            byrule = {}
            for rule, j in dispatched.items():
                if j not in byindex:
                    byindex[j] = endpoints(prevalue(*raw, index_rule=rule))
                byrule[rule] = byindex[j]
            different = tuple(rule for rule in HYPOTHESES[1:] if byrule[rule] != byrule['lower'])
            if different:
                counts['endpoint_disagreements'] += 1
                key = f'{n}:{side}:' + '|'.join(different)
                signatures[key] += 1
                if signatures[key] <= 8:
                    # An independent full-graph call in every sign/octant
                    # checks the shortcut used to compare the endpoint sets.
                    for rule in ('lower', *different):
                        expected = []
                        for swap, sx in ((False, 0), (False, 32768), (True, 0), (True, 32768)):
                            a, b = raw[:2], raw[2:]
                            if swap:
                                a, b = b, a
                            for sy in (0, 32768):
                                v = prevalue(a[0] | sy, a[1], b[0] | sx, b[1], index_rule=rule)
                                for rc in ('rn', 'rd', 'ru', 'rz'):
                                    q = encode(v, rc)
                                    expected.append((*q, int(abs(value(*q)) > abs(v))))
                        assert tuple(expected) == byrule[rule]
                    witnesses.append(dict(raw=raw, cell=n, side=side, signature=key,
                                          ratio=str(ratio), index=selected,
                                          differs_from_lower=different))
        if counts['pairs'] % 16384 == 0:
            print('Mined', counts['pairs'], 'pairs;', counts['endpoint_disagreements'],
                  'endpoint differences;', len(witnesses), 'selected witnesses', flush=True)
    save(BASE / 'd0024-index-residue-mining.json', dict(
        status='SOFTWARE_ONLY_DISCRIMINATORS_NOT_FROZEN_OR_CAPTURED', seed=SEED,
        counts=counts, per_cell=per_cell, signature_counts=signatures,
        witnesses=witnesses, hardware_labels_opened=False, hardware_executed=False,
        numerical_model_promoted=False,
        source_sha256={p.name: digest(p) for p in (Path(__file__),
            Path(__file__).with_name('d0023_index_hypotheses.py'),
            Path(__file__).with_name('graph_v7.py'))}))
    print(json.dumps(dict(counts)), flush=True)
    print('Selected', len(witnesses), 'witnesses;', len(signatures), 'signatures', flush=True)


if __name__ == '__main__':
    main()
