"""Fixed signed truncation/ceiling roles in the direct FPATAN datapath.

Discarding low bits of a signed two's-complement value gives floor, not
magnitude CHOP. Test that arithmetic distinction, its dual ceiling, and
away-from-zero truncation with fixed operation roles. No rule examines an
operand identity, observed error or fitted boundary. Discovery only.
"""
import functools
import itertools
import json
from d0010_causal_intervals import BASE, observation_interval, restore
from graph_v5 import prevalue
from model import ROM, cut
from prepare import save

PRODUCTS = ('chop67', 'rd67', 'ru67', 'away67')
ADDS = ('rn64', 'rd64', 'ru64', 'chop64', 'away64')


@functools.lru_cache(maxsize=100000)
def prefix(z, read, square, multiply, add, scope):
    u = cut(z * cut(z, read), square)
    h = ROM[123]
    for k in range(122, 117, -1):
        selected = scope == 'all' or (scope == 'last' and k == 118) or (scope == 'prefix' and k != 118)
        h = cut(ROM[k] + cut(u * h, multiply if selected else 'chop67'), add if selected else 'rn64')
    return u, h


def kernel(z, read, square, multiply, add, scope, first, last, zread, order):
    u, h = prefix(z, read, square, multiply, add, scope)
    zr = cut(z, zread)
    if order == 0:
        result = cut(cut(u * h, first) * zr, last)
    elif order == 1:
        result = cut(cut(zr * h, first) * u, last)
    else:
        result = cut(cut(zr * u, first) * h, last)
    return z + result


def main():
    data = []
    for pair in json.loads((BASE / 'd0009-kernel-frontier.json').read_text())['pairs']:
        t = {}
        prevalue(*pair['raw'], trace=t)
        if t['kind'] == 'direct':
            data.append((pair, t, observation_interval(pair['rows'])))
    data.sort(key=lambda item: item[2].lo != item[2].hi)
    results = []
    survivors = []
    recipes = itertools.product(('exact', 'chop64', 'rn64'), ('chop67', 'rn64', 'away67'),
                                PRODUCTS, ADDS, ('all', 'last', 'prefix'), PRODUCTS, PRODUCTS,
                                ('exact', 'chop64', 'rn64'), range(3))
    for number, args in enumerate(recipes, 1):
        failure = None
        for index, (pair, t, band) in enumerate(data):
            v = restore(kernel(t['z'], *args), t, pair['raw'])
            if not band.contains(abs(v)):
                failure = dict(input=pair['rows'][0]['input'], prevalue=str(v), interval=band.json())
                break
        recipe = dict(zip(('square_read', 'square', 'horner_multiply', 'horner_add', 'horner_scope',
                           'tail_first', 'tail_last', 'tail_z_read', 'tail_order'), args))
        report = dict(recipe=recipe, tested_groups=index + 1, counterexample=failure)
        results.append(report)
        if failure is None:
            survivors.append(report)
            print('DIRECT DISCOVERY SURVIVOR', recipe, flush=True)
        if number % 10000 == 0:
            print('tested', number, 'signed programs;', len(survivors), 'survivors', flush=True)
    save(BASE / 'd0017-signed-truncation-audit.json', dict(status='FIXED_SIGNED_TRUNCATION_DISCOVERY_AUDIT',
         programs=len(results), direct_raw_groups=len(data), results=results, survivors=survivors,
         hardware_executed=False, numerical_model_promoted=False))
    print('COMPLETE', len(results), 'programs;', len(survivors), 'direct survivors', flush=True)


if __name__ == '__main__':
    main()
