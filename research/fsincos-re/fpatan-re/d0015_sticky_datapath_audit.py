"""Fixed round-to-odd (sticky-jammed) producer/read datapaths.

Round-to-odd retains a sticky indication in the low bit when discarded bits
are nonzero. Unlike CHOP or RN it may round upward below a halfway point.
All widths and roles are global. This tests a distinct representation, not a
predicate fitted to a list of failing operands.
"""
import functools
import itertools
import json
from d0010_causal_intervals import BASE, observation_interval, restore
from graph_v5 import prevalue
from model import F, ROM, cut, exponent, pow2
from prepare import save


def odd(v, bits):
    if not v:
        return v
    unit = pow2(exponent(v) - bits + 1)
    scaled = abs(v) / unit
    q, r = divmod(scaled.numerator, scaled.denominator)
    if r:
        q |= 1
    return (-1 if v < 0 else 1) * q * unit


def formatted(v, spec):
    for stage in spec.split('>'):
        v = odd(v, int(stage[3:])) if stage.startswith('odd') else cut(v, stage)
    return v


@functools.lru_cache(maxsize=60000)
def prefix(z, read, square, multiply, add):
    u = formatted(z * cut(z, read), square)
    h = ROM[123]
    for k in range(122, 117, -1):
        h = formatted(ROM[k] + formatted(u * h, multiply), add)
    return u, h


def kernel(z, read, square, multiply, add, first, last, zread, order):
    u, h = prefix(z, read, square, multiply, add)
    zr = cut(z, zread)
    if order == 0:
        tail = formatted(formatted(u * h, first) * zr, last)
    elif order == 1:
        tail = formatted(formatted(zr * h, first) * u, last)
    else:
        tail = formatted(formatted(zr * u, first) * h, last)
    return z + tail


def main():
    assert odd(F(17, 16), 4) == F(9, 8)
    assert odd(F(19, 16), 4) == F(9, 8)
    assert odd(F(5, 4), 4) == F(5, 4)
    data = []
    for pair in json.loads((BASE / 'd0009-kernel-frontier.json').read_text())['pairs']:
        t = {}
        prevalue(*pair['raw'], trace=t)
        if t['kind'] == 'direct':
            data.append((pair, t, observation_interval(pair['rows'])))
    data.sort(key=lambda item: item[2].lo != item[2].hi)
    results = []
    survivors = []
    sticky = ('chop67', 'odd67', 'odd68')
    recipes = itertools.product(('exact', 'chop64', 'rn64'), ('chop67', 'rn64', 'odd67', 'odd68'),
                                sticky, ('rn64', 'odd67>rn64'), sticky, sticky,
                                ('exact', 'chop64', 'rn64'), range(3))
    for number, args in enumerate(recipes, 1):
        failure = None
        for index, (pair, t, band) in enumerate(data):
            v = restore(kernel(t['z'], *args), t, pair['raw'])
            if not band.contains(abs(v)):
                failure = dict(input=pair['rows'][0]['input'], prevalue=str(v), interval=band.json())
                break
        recipe = dict(zip(('square_read', 'square', 'horner_multiply', 'horner_add', 'tail_first',
                           'tail_last', 'tail_z_read', 'tail_order'), args))
        report = dict(recipe=recipe, tested_groups=index + 1, counterexample=failure)
        results.append(report)
        if failure is None:
            survivors.append(report)
            print('DIRECT DISCOVERY SURVIVOR', recipe, flush=True)
        if number % 2000 == 0:
            print('tested', number, 'sticky programs;', len(survivors), 'survivors', flush=True)
    save(BASE / 'd0015-sticky-datapath-audit.json', dict(status='FIXED_STICKY_REPRESENTATION_DISCOVERY_AUDIT',
         programs=len(results), direct_raw_groups=len(data), results=results, survivors=survivors,
         hardware_executed=False, numerical_model_promoted=False))
    print('COMPLETE', len(results), 'programs;', len(survivors), 'direct survivors', flush=True)


if __name__ == '__main__':
    main()
