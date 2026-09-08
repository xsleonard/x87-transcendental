"""Two-part retained-rounding-state datapaths, without operand selectors.

A node carries (rounded main value, retained residual). Multiplication
propagates both cross terms and the residual product; addition carries its
incoming residual. Fixed role bits choose whether each producer retains or
discards its newly generated rounding residual. This is an arithmetic
representation audit, not a learned state machine or a claimed CPU circuit.
"""
import functools
import itertools
import json
from d0010_causal_intervals import BASE, observation_interval, restore
from graph_v5 import prevalue
from model import F, ROM, cut
from prepare import save


def multiply(a, b, main_format, residual_format, keep_local):
    ah, al = a
    bh, bl = b
    exact_main = ah * bh
    high = cut(exact_main, main_format)
    low = ah * bl + al * bh + al * bl
    if keep_local:
        low += exact_main - high
    return high, cut(low, residual_format)


def add_constant(constant, carrier, residual_format, keep_local):
    high, low = carrier
    exact_main = constant + high
    rounded = cut(exact_main, 'rn64')
    if keep_local:
        low += exact_main - rounded
    return rounded, cut(low, residual_format)


@functools.lru_cache(maxsize=40000)
def prefix(z, square_format, residual_format, square_residual, product_residual, add_residual):
    u = multiply((z, F(0)), (z, F(0)), square_format, residual_format, square_residual)
    h = ROM[123], F(0)
    for k in range(122, 117, -1):
        product = multiply(u, h, 'chop67', residual_format, product_residual)
        h = add_constant(ROM[k], product, residual_format, add_residual)
    return u, h


def kernel(z, square_format, residual_format, square_residual, product_residual, add_residual,
           first_residual, last_residual, zread, read_residual, order, merge):
    u, h = prefix(z, square_format, residual_format, square_residual, product_residual, add_residual)
    zr = cut(z, zread)
    zz = zr, (z - zr if read_residual else F(0))
    if order == 0:
        a, b, c = u, h, zz
    elif order == 1:
        a, b, c = zz, h, u
    else:
        a, b, c = zz, u, h
    product = multiply(a, b, 'chop67', residual_format, first_residual)
    high, low = multiply(product, c, 'chop67', residual_format, last_residual)
    return z + cut(high + low, merge)


def selftest():
    # Complete residual propagation reconstructs the exact polynomial,
    # independently of the chosen rounded main-value representation.
    for z in (F(1, 73), F(3, 128), F(17, 512)):
        exact = z + sum(ROM[k] * z ** (2 * (k - 118) + 3) for k in range(118, 124))
        for square, order, read in itertools.product(('chop67', 'rn64'), range(3), ('exact', 'chop64', 'rn64')):
            got = kernel(z, square, 'exact', True, True, True, True, True, read, True, order, 'exact')
            assert got == exact


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
    recipes = itertools.product(('chop67', 'rn64'), ('exact', 'rn64', 'chop67'),
                                (False, True), (False, True), (False, True), (False, True), (False, True),
                                ('exact', 'chop64', 'rn64'), (False, True), range(3),
                                ('exact', 'chop67', 'rn67', 'rn64'))
    for number, args in enumerate(recipes, 1):
        failure = None
        for index, (pair, t, band) in enumerate(data):
            v = restore(kernel(t['z'], *args), t, pair['raw'])
            if not band.contains(abs(v)):
                failure = dict(input=pair['rows'][0]['input'], prevalue=str(v), interval=band.json())
                break
        recipe = dict(zip(('square_format', 'residual_format', 'square_residual', 'product_residual', 'add_residual',
                           'first_residual', 'last_residual', 'zread', 'read_residual', 'tail_order', 'merge'), args))
        report = dict(recipe=recipe, tested_groups=index + 1, counterexample=failure)
        results.append(report)
        if failure is None:
            survivors.append(report)
            print('DIRECT DISCOVERY SURVIVOR', recipe, flush=True)
        if number % 2000 == 0:
            print('tested', number, 'two-part programs;', len(survivors), 'survivors', flush=True)
    save(BASE / 'd0017-residual-state-audit.json', dict(status='FIXED_TWO_PART_RESIDUAL_DISCOVERY_AUDIT',
         programs=len(results), direct_raw_groups=len(data), results=results, survivors=survivors,
         complete_residual_polynomial_identity='PASS', hardware_executed=False, numerical_model_promoted=False))
    print('COMPLETE', len(results), 'programs;', len(survivors), 'direct survivors', flush=True)


if __name__ == '__main__':
    main()
