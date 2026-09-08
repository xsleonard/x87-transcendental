"""Fixed compensated high/low quotient datapaths, saved observations only.

Write z=a+b, evaluate the long polynomial at a, and propagate b with either
the polynomial derivative, the atan derivative, or the exact polynomial
difference. These are algebraic arithmetic mechanisms, not error predicates.
Every recipe is fixed across inputs. Passing this frontier would be discovery
only and would require all ten saved jobs plus a fresh frozen challenge.
"""
import functools
import itertools
import json
import math
from d0010_causal_intervals import BASE, observation_interval, restore
from graph_v5 import prevalue
from model import F, ROM, cut
from prepare import save

HIGHS = tuple(f'{mode}{bits}' for bits in (64, 65, 66) for mode in ('chop', 'rn'))
CORRECTIONS = ('none-control', 'atan-derivative', 'polynomial-derivative',
               'retained-polynomial-derivative', 'exact-polynomial-increment')
FORMATS = ('exact', 'chop67', 'rn64')


def polynomial_tail(z):
    return sum(ROM[k] * z ** (2 * (k - 118) + 3) for k in range(118, 124))


@functools.lru_cache(maxsize=20000)
def prefix(z, high, square, first, order):
    a = cut(z, high)
    b = z - a
    u = cut(a * a, square)
    h = ROM[123]
    for k in range(122, 117, -1):
        h = cut(ROM[k] + cut(u * h, 'chop67'), 'rn64')
    if order == 0:
        tail = cut(cut(u * h, first) * a, 'chop67')
    elif order == 1:
        tail = cut(cut(a * h, first) * u, 'chop67')
    else:
        tail = cut(cut(a * u, first) * h, 'chop67')
    return a, b, u, tail


@functools.lru_cache(maxsize=20000)
def correction(a, b, u, kind):
    # Each returned correction excludes the trivial leading b term.
    if kind == 'none-control':
        return F(0)
    if kind == 'atan-derivative':
        return -b * a * a / (1 + a * a)
    if kind == 'polynomial-derivative':
        return b * sum((2 * (k - 118) + 3) * ROM[k] * a ** (2 * (k - 118) + 2)
                       for k in range(118, 124))
    if kind == 'retained-polynomial-derivative':
        h = 13 * ROM[123]
        for k in range(122, 117, -1):
            h = cut((2 * (k - 118) + 3) * ROM[k] + cut(u * h, 'chop67'), 'rn64')
        return cut(b * cut(u * h, 'chop67'), 'chop67')
    assert kind == 'exact-polynomial-increment'
    return polynomial_tail(a + b) - polynomial_tail(a)


def kernel(z, high, square, first, order, kind, correction_format, merge_format, layout):
    a, b, u, tail = prefix(z, high, square, first, order)
    delta = cut(correction(a, b, u, kind), correction_format)
    if layout == 0:
        return z + cut(tail + delta, merge_format)
    if layout == 1:
        return a + cut(tail + (b + delta), merge_format)
    assert layout == 2
    return a + cut(tail + cut(b + delta, merge_format), merge_format)


def selftest():
    # Exact split-polynomial identity, independently expanded by the binomial
    # theorem. No retained-width schedule is asserted to share this identity.
    for a, b in ((F(3, 128), F(1, 1 << 70)), (F(5, 256), -F(3, 1 << 72))):
        expanded = sum(ROM[k] * sum(F(math.comb(n, j)) * a ** (n - j) * b ** j for j in range(1, n + 1))
                       for k in range(118, 124) for n in (2 * (k - 118) + 3,))
        delta = correction(a, b, a * a, 'exact-polynomial-increment')
        assert delta == expanded
        assert a + polynomial_tail(a) + b + delta == a + b + polynomial_tail(a + b)
    for high in HIGHS:
        for z in (F(17, 1024), F(123456789012345678901, 1 << 73)):
            a = cut(z, high)
            assert a + (z - a) == z


def main():
    selftest()
    data = []
    for pair in json.loads((BASE / 'd0009-kernel-frontier.json').read_text())['pairs']:
        t = {}
        prevalue(*pair['raw'], trace=t)
        if t['kind'] == 'direct':
            data.append((pair, t, observation_interval(pair['rows'])))
    data.sort(key=lambda item: item[2].lo != item[2].hi)
    results = []
    survivors = []
    recipes = itertools.product(HIGHS, ('chop67', 'rn64'), ('chop67', 'rn64'), range(3),
                                CORRECTIONS, FORMATS, FORMATS, range(3))
    for number, args in enumerate(recipes, 1):
        failure = None
        for index, (pair, t, band) in enumerate(data):
            v = restore(kernel(t['z'], *args), t, pair['raw'])
            if not band.contains(abs(v)):
                failure = dict(input=pair['rows'][0]['input'], prevalue=str(v), interval=band.json())
                break
        recipe = dict(zip(('high', 'square', 'tail_first', 'tail_order', 'correction',
                           'correction_format', 'merge_format', 'layout'), args))
        report = dict(recipe=recipe, tested_groups=index + 1, counterexample=failure)
        results.append(report)
        if failure is None:
            survivors.append(report)
            print('DIRECT FRONTIER SURVIVOR', recipe, flush=True)
        if number % 2000 == 0:
            print('tested', number, 'split programs;', len(survivors), 'survivors', flush=True)
    save(BASE / 'd0015-split-quotient-audit.json', dict(status='FIXED_COMPENSATED_QUOTIENT_DISCOVERY_AUDIT',
         programs=len(results), direct_raw_groups=len(data), exact_split_identity='PASS',
         results=results, survivors=survivors, hardware_executed=False, numerical_model_promoted=False))
    print('COMPLETE', len(results), 'fixed programs;', len(survivors), 'direct survivors', flush=True)


if __name__ == '__main__':
    main()
