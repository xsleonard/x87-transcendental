"""Move the leading term inside the final FPATAN multiplication.

The exact identity z + z*u*H(u) = z*(1 + u*H(u)) changes where rounding
occurs. Prior tail-tree audits kept the leading z outside the product.
This family explicitly materializes a near-one factor and then multiplies
it by z. All formats are fixed operation roles, never input selectors.
"""
import functools
import itertools
import json
from d0010_causal_intervals import BASE, observation_interval, restore
from graph_v5 import prevalue
from model import F, ROM, cut
from prepare import save

FACTORS = tuple(f'{mode}{bits}' for bits in (64, 67, 69, 72, 80, 96, 128)
                for mode in ('chop', 'rn')) + ('exact',)
PRODUCTS = ('chop64', 'rn64', 'chop67', 'rn67', 'chop69', 'rn69', 'exact')


@functools.lru_cache(maxsize=40000)
def prefix(z, square, multiply, add):
    u = cut(z * z, square)
    h = ROM[123]
    for k in range(122, 117, -1):
        h = cut(ROM[k] + cut(u * h, multiply), add)
    return u, h


def kernel(z, square, multiply, add, tail, factor, zread, last):
    u, h = prefix(z, square, multiply, add)
    scale = cut(1 + cut(u * h, tail), factor)
    return cut(cut(z, zread) * scale, last)


def main():
    for z in (F(1, 73), F(3, 128), F(17, 512)):
        expected = z + sum(ROM[k] * z ** (2 * (k - 118) + 3) for k in range(118, 124))
        assert kernel(z, *(['exact'] * 7)) == expected
    data = []
    for pair in json.loads((BASE / 'd0009-kernel-frontier.json').read_text())['pairs']:
        t = {}
        prevalue(*pair['raw'], trace=t)
        if t['kind'] == 'direct':
            data.append((pair, t, observation_interval(pair['rows'])))
    data.sort(key=lambda p: p[2].lo != p[2].hi)
    recipes = itertools.product(('chop67', 'rn64', 'exact'), ('chop67', 'rn64', 'exact'),
                                ('rn64', 'chop67', 'rn67', 'exact'), PRODUCTS, FACTORS,
                                ('exact', 'chop64', 'rn64'), PRODUCTS)
    results, survivors = [], []
    for number, args in enumerate(recipes, 1):
        failure = None
        for index, (pair, trace, band) in enumerate(data):
            v = restore(kernel(trace['z'], *args), trace, pair['raw'])
            if not band.contains(abs(v)):
                failure = dict(input=pair['rows'][0]['input'], prevalue=str(v), interval=band.json())
                break
        recipe = dict(zip(('square', 'multiply', 'add', 'tail', 'factor', 'zread', 'last'), args))
        item = dict(recipe=recipe, tested_groups=index + 1, counterexample=failure)
        results.append(item)
        if failure is None:
            survivors.append(item)
            print('DIRECT DISCOVERY SURVIVOR', recipe, flush=True)
        if number % 20000 == 0:
            print(number, 'factored-lead programs;', len(survivors), 'survivors', flush=True)
    save(BASE / 'd0020-factored-lead-audit.json', dict(status='FIXED_FACTORED_LEAD_DISCOVERY_AUDIT',
         programs=len(results), direct_raw_groups=len(data), results=results, survivors=survivors,
         exact_polynomial_identity='PASS', hardware_executed=False, numerical_model_promoted=False))
    print('COMPLETE', len(results), 'programs;', len(survivors), 'direct survivors', flush=True)


if __name__ == '__main__':
    main()
