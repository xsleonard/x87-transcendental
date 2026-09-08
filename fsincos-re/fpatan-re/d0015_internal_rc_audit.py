"""Architectural RC-driven operation roles, without a common-prevalue assumption.

The caller's actual rounding control may feed internal operations. Test that
directly against each saved output/C1, not the intersection of modes. Each
recipe is one fixed program; sign-reflected RC is a fixed magnitude-domain
coordinate transform, never a selector based on error state.
"""
import functools
import itertools
import json
from d0010_causal_intervals import BASE, restore
from graph_v5 import prevalue
from model import ROM, cut, encode, value
from prepare import save

FORMATS = ('chop67', 'rn64', 'rc64', 'rc67')


def formatted(v, spec, rc):
    if spec.startswith('rc'):
        mode = 'chop' if rc == 'rz' else rc
        return cut(v, mode + spec[2:])
    return cut(v, spec)


@functools.lru_cache(maxsize=120000)
def prefix(z, rc, square_read, square, product, add, scope):
    u = formatted(z * cut(z, square_read), square, rc)
    h = ROM[123]
    for k in range(122, 117, -1):
        selected = scope == 'all' or (scope == 'last' and k == 118) or (scope == 'prefix' and k != 118)
        h = formatted(ROM[k] + formatted(u * h, product if selected else 'chop67', rc),
                      add if selected else 'rn64', rc)
    return u, h


def kernel(z, rc, square_read, square, product, add, scope, first, last, zread, order):
    u, h = prefix(z, rc, square_read, square, product, add, scope)
    zr = cut(z, zread)
    if order == 0:
        tail = formatted(formatted(u * h, first, rc) * zr, last, rc)
    elif order == 1:
        tail = formatted(formatted(zr * h, first, rc) * u, last, rc)
    else:
        tail = formatted(formatted(u * zr, first, rc) * h, last, rc)
    return z + tail


def main():
    data = []
    for pair in json.loads((BASE / 'd0009-kernel-frontier.json').read_text())['pairs']:
        t = {}
        prevalue(*pair['raw'], trace=t)
        if t['kind'] == 'direct':
            for row in pair['rows']:
                data.append((pair, t, row))
    # RN often prunes familiar graphs, so keep the native four-mode order.
    results = []
    survivors = []
    recipes = itertools.product(('raw', 'sign-reflected'), ('exact', 'chop64', 'rn64'), FORMATS,
                                ('chop67', 'rc67'), ('rn64', 'rc64'), ('all', 'last', 'prefix'),
                                ('chop67', 'rc67'), ('chop67', 'rc67', 'rc64'),
                                ('exact', 'chop64', 'rn64'), range(3))
    for number, args in enumerate(recipes, 1):
        rc_source, *arithmetic = args
        failure = None
        for index, (pair, t, row) in enumerate(data):
            rc = row['rc']
            if rc_source == 'sign-reflected' and pair['raw'][0] & 32768:
                rc = {'rd': 'ru', 'ru': 'rd'}.get(rc, rc)
            v = restore(kernel(t['z'], rc, *arithmetic), t, pair['raw'])
            se, sig = encode(v, row['rc'])
            c1 = int(abs(value(se, sig)) > abs(v))
            if (se, sig, c1) != (row['se'], row['sig'], row['C1']):
                failure = dict(input=row['input'], internal_rc=rc, prevalue=str(v),
                               observed=[row['se'], row['sig'], row['C1']], predicted=[se, sig, c1])
                break
        recipe = dict(zip(('rc_source', 'square_read', 'square', 'horner_product', 'horner_add', 'horner_scope',
                           'tail_first', 'tail_last', 'tail_z_read', 'tail_order'), args))
        report = dict(recipe=recipe, tested_observations=index + 1, counterexample=failure)
        results.append(report)
        if failure is None:
            survivors.append(report)
            print('DIRECT DISCOVERY SURVIVOR', recipe, flush=True)
        if number % 4000 == 0:
            print('tested', number, 'RC-driven programs;', len(survivors), 'survivors', flush=True)
    save(BASE / 'd0015-internal-rc-audit.json', dict(status='ARCHITECTURAL_RC_DIRECT_DISCOVERY_AUDIT',
         programs=len(results), direct_observations=len(data), results=results, survivors=survivors,
         common_prevalue_required=False, hardware_executed=False, numerical_model_promoted=False))
    print('COMPLETE', len(results), 'programs;', len(survivors), 'direct survivors', flush=True)


if __name__ == '__main__':
    main()
