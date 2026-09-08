"""Fresh frozen challenge for the source-guided V6 split polynomial.

Independent ratios, every atan cell/dispatch boundary, full sign/octant and
scale variation, and neighborhoods of the old failed inputs. No labels from
this campaign are consulted. The generic freeze enforces private/public and
all prior FPATAN tuple holds before any one-shot capture.
"""
import json
import random
from dataclasses import replace
from architecture import POLICY
from d0010_causal_intervals import BASE
from freeze_stream import freeze
from model import F, encode, pow2, value

SEED = 'fpatan-d0022-source-guided-interleaved-polynomial-20260905'


def scaled(pair, rng, orbit=False):
    ys, ym, xs, xm = pair
    choices = [(a, b, c) for a in (False, True) for b in (0, 32768) for c in (0, 32768)] if orbit else [
        (bool(rng.getrandbits(1)), rng.getrandbits(1) << 15, rng.getrandbits(1) << 15)]
    for swap, sy, sx in choices:
        shift = rng.randrange(-15000, 15001)
        a, b = (ys & 32767) + shift, (xs & 32767) + shift
        assert 0 < a < 32767 and 0 < b < 32767
        y, x = ((b, xm), (a, ym)) if swap else ((a, ym), (b, xm))
        yield y[0] | sy, y[1], x[0] | sx, x[1]


def generate():
    rng = random.Random(SEED)
    # These are explicitly discovery neighborhoods, not independent draws.
    centers = set()
    for point in json.loads((BASE / 'd0009-kernel-frontier.json').read_text())['pairs']:
        ys, ym, xs, xm = point['raw']
        shift = (xs & 32767) - 16383
        centers.add(((ys & 32767) - shift, ym, 16383, xm))
    for ys, ym, xs, xm in sorted(centers):
        for d in (-4095, -255, -15, -3, -1, 1, 3, 15, 255, 4095):
            for dy, dx in ((d, 0), (0, d), (d, d)):
                if not (1 << 63) <= ym + dy < (1 << 64) or not (1 << 63) <= xm + dx < (1 << 64):
                    continue
                for p in scaled((ys, ym + dy, xs, xm + dx), rng, True):
                    yield p, 'old-frontier-neighborhood'
    # All table centers and index midpoints, including the direct/table
    # transition at 3/64; adjacent raw80 encodings expose narrow intervals.
    boundaries = sorted({F(n, 32) for n in range(1, 33)} | {F(2*n-1, 64) for n in range(2, 33)})
    for ratio in boundaries:
        for _ in range(4):
            xm = rng.getrandbits(63) | (1 << 63)
            ys, ym = encode(value(16383, xm) * ratio)
            for d in (-1025, -65, -3, -1, 0, 1, 3, 65, 1025):
                if not (1 << 63) <= ym + d < (1 << 64):
                    continue
                for p in scaled((ys, ym + d, 16383, xm), rng, True):
                    yield p, 'all-cell-center-midpoint-neighborhood'
    for i in range(65536):
        xm = rng.getrandbits(63) | (1 << 63)
        x = value(16383, xm)
        fraction = F(rng.getrandbits(64) + 1, (1 << 64) + 1)
        family = i % 4
        if family == 0:
            ys, ym = encode(x * fraction * F(3, 64))
            kind = 'independent-direct'
        elif family == 1:
            n = 2 + (i // 4) % 31
            lo, hi = F(2*n-1, 64), min(F(1), F(2*n+1, 64))
            ys, ym = encode(x * (lo + (hi-lo)*fraction))
            kind = 'independent-table-cells'
        elif family == 2:
            n = rng.randrange(2, 33)
            ys, ym = encode(x * (F(n, 32) + rng.choice((-1, 1))*fraction*pow2(-rng.randrange(7, 73))))
            kind = 'independent-cancellation'
        else:
            ys = 16383 - rng.randrange(5, 56)
            ym = rng.getrandbits(63) | (1 << 63)
            kind = 'independent-small-and-bypass'
        for p in scaled((ys, ym, 16383, xm), rng):
            yield p, kind
    for _ in range(8192):
        ys, xs = rng.randrange(1, 32767), rng.randrange(1, 32767)
        ym, xm = rng.getrandbits(63) | (1 << 63), rng.getrandbits(63) | (1 << 63)
        yield (ys | rng.getrandbits(1) << 15, ym, xs | rng.getrandbits(1) << 15, xm), 'full-exponent-range'


if __name__ == '__main__':
    freeze('d0022', SEED, generate,
           ('prepare_d0022.py', 'graph_v5.py', 'graph_v6.py', 'd0010_causal_intervals.py',
            'fpatan_candidate_v6.c', 'd0021_goldmont_fpatan_audit.py'),
           policy=replace(POLICY, numerical_graph='v6'),
           purpose='Prospective source-guided V6 split-polynomial verification; old frontier neighborhoods, independent cells, boundaries and full-exponent controls')
