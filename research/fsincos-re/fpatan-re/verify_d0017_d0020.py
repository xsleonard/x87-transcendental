"""Independent arithmetic replay of D0017/D0018/D0020 counterexamples.

No audited kernel, graph or model quantizer is imported. Reconstruct direct
quotients, role schedules, quadrant restoration and RC/C1 from raw operands,
public ROM data and an independent rational/integer rounder. Every retained
first counterexample is checked (not a random sample). Original captures are
authenticated using the existing source-only checker; no hardware executes.
"""
import collections
import functools
import hashlib
import json
from fractions import Fraction as F
from pathlib import Path
from verify_d0014_certificate import rom_constants, two
from verify_d0016_family import authenticate
from prepare import save

BASE = Path(__file__).resolve().parents[1] / 'tmp/fpatan-re'
COEFF = rom_constants()


def quantize(v, spec):
    if not v or spec == 'exact':
        return v
    mode = spec.rstrip('0123456789')
    bits = int(spec[len(mode):])
    n, d = abs(v).numerator, abs(v).denominator
    e = n.bit_length() - d.bit_length()
    if F(n, d) < two(e):
        e -= 1
    unit = two(e - bits + 1)
    scaled = abs(v) / unit
    whole, rem = divmod(scaled.numerator, scaled.denominator)
    if mode == 'rn':
        inc = 2 * rem > scaled.denominator or (2 * rem == scaled.denominator and whole % 2)
    elif mode == 'chop':
        inc = False
    elif mode in ('rd', 'ru', 'away'):
        inc = bool(rem) and (mode == 'away' or (mode == 'rd') == (v < 0))
    else:
        raise ValueError(spec)
    return (-1 if v < 0 else 1) * (whole + inc) * unit


def product(a, b, fmt, lowfmt, keep):
    ah, al = a
    bh, bl = b
    high = quantize(ah * bh, fmt)
    # Sum the full expansion, then remove the chosen represented main part.
    # If the local residual is dropped, remove that loss as well.
    low = (ah + al) * (bh + bl) - high
    if not keep:
        low -= ah * bh - high
    return high, quantize(low, lowfmt)


@functools.lru_cache(maxsize=120000)
def prefix(z, family, args):
    if family == 'residual':
        sf, lf, sr, mr, ar = args
        u = product((z, F(0)), (z, F(0)), sf, lf, sr)
        h = COEFF[123], F(0)
        for k in range(122, 117, -1):
            p, loss = product(u, h, 'chop67', lf, mr)
            high = quantize(COEFF[k] + p, 'rn64')
            low = loss + (COEFF[k] + p - high if ar else F(0))
            h = high, quantize(low, lf)
        return u, h
    if family == 'factored':
        square, mult, add = args
        read, scope = 'exact', 'all'
    else:
        read, square, mult, add, scope = args
    u = quantize(z * quantize(z, read), square)
    h = COEFF[123]
    for k in range(122, 117, -1):
        selected = scope == 'all' or (scope == 'last' and k == 118) or (scope == 'prefix' and k != 118)
        p = quantize(u * h, mult if selected else 'chop67')
        h = quantize(COEFF[k] + p, add if selected else 'rn64')
    return u, h


def kernel(z, family, recipe, rc='rn', negative=False):
    r = dict(recipe)
    if family == 'residual':
        lf = r['residual_format']
        args = tuple(r[k] for k in ('square_format', 'residual_format', 'square_residual', 'product_residual', 'add_residual'))
        u, h = prefix(z, family, args)
        zr = quantize(z, r['zread'])
        zz = zr, (z - zr if r['read_residual'] else F(0))
        a, b, c = ((u, h, zz), (zz, h, u), (zz, u, h))[r['tail_order']]
        p = product(a, b, 'chop67', lf, r['first_residual'])
        high, low = product(p, c, 'chop67', lf, r['last_residual'])
        return z + quantize(high + low, r['merge'])
    if family == 'factored':
        u, h = prefix(z, family, tuple(r[k] for k in ('square', 'multiply', 'add')))
        scale = quantize(1 + quantize(u * h, r['tail']), r['factor'])
        return quantize(quantize(z, r['zread']) * scale, r['last'])
    if family == 'internal-rc':
        if r['rc_source'] == 'sign-reflected' and negative:
            rc = {'rd': 'ru', 'ru': 'rd'}.get(rc, rc)
        for k, v in list(r.items()):
            if isinstance(v, str) and v.startswith('rc') and v[2:].isdigit():
                r[k] = ('chop' if rc == 'rz' else rc) + v[2:]
        r['horner_multiply'] = r['horner_product']
    args = tuple(r[k] for k in ('square_read', 'square', 'horner_multiply', 'horner_add', 'horner_scope'))
    u, h = prefix(z, family, args)
    zr = quantize(z, r['tail_z_read'])
    a, b, c = ((u, h, zr), (zr, h, u), (zr, u, h))[r['tail_order']]
    return z + quantize(quantize(a * b, r['tail_first']) * c, r['tail_last'])


def coordinate(raw):
    ys, ym, xs, xm = raw
    y = ym * two(max(ys & 32767, 1) - 16383 - 63)
    x = xm * two(max(xs & 32767, 1) - 16383 - 63)
    swap = y > x
    ratio = min(x, y) / max(x, y)
    assert two(-40) <= ratio < F(3, 64)
    return quantize(ratio, 'chop67'), swap


def restore(k, raw, swap):
    # These frontier groups are all direct, so there is no atan-table add.
    if swap or raw[2] & 32768:
        k = quantize(k, 'chop67')
        pi = F(0xc90fdaa22168c234c) * two(-66)
        if swap:
            k = pi / 2 + (k if raw[2] & 32768 else -k)
        else:
            k = pi - k
    return -k if raw[0] & 32768 else k


def outcome(v, row):
    q = quantize(v, ('chop' if row['rc'] == 'rz' else row['rc']) + '64')
    # All direct-frontier outputs are normal and nonzero; compare their
    # exact values instead of reusing the model's raw80 encoder.
    observed = row['sig'] * two((row['se'] & 32767) - 16383 - 63)
    if row['se'] & 32768:
        observed = -observed
    return q, int(abs(q) > abs(v)), observed


def main():
    frontier_path = BASE / 'd0009-kernel-frontier.json'
    frontier = json.loads(frontier_path.read_text())['pairs']
    sources, authenticated = authenticate(frontier)
    rows = {r['input']: (p, r) for p in frontier for r in p['rows']}
    coordinates = {}
    counts = collections.Counter()
    pins = {}

    def read(name):
        path = BASE / name
        raw = path.read_bytes()
        pins[name] = hashlib.sha256(raw).hexdigest()
        return json.loads(raw)

    def replay(family, recipe, failure):
        pair, row = rows[failure['input']]
        raw = tuple(pair['raw'])
        if raw not in coordinates:
            coordinates[raw] = coordinate(raw)
        z, swap = coordinates[raw]
        v = restore(kernel(z, family, recipe, row['rc'], bool(raw[0] & 32768)), raw, swap)
        q, c1, observed = outcome(v, row)
        if 'prevalue' in failure:
            assert str(v) == failure['prevalue']
            # The group may fail a mode other than its first row.
            assert any(outcome(v, r)[0] != outcome(v, r)[2] or outcome(v, r)[1] != r['C1']
                       for r in pair['rows'])
        else:
            assert failure['observed'] == [row['se'], row['sig'], row['C1']]
            se, sig, expected_c1 = failure['predicted']
            predicted = sig * two((se & 32767) - 16383 - 63) * (-1 if se & 32768 else 1)
            assert q == predicted and c1 == expected_c1
            assert q != observed or c1 != row['C1']
        counts[family] += 1

    for family, filename in (
        ('signed', 'd0017-signed-truncation-audit.json'),
        ('residual', 'd0017-residual-state-audit.json'),
        ('factored', 'd0020-factored-lead-audit.json'),
    ):
        report = read(filename)
        assert not report['survivors'] and report['programs'] == len(report['results'])
        for item in report['results']:
            assert item['counterexample'] is not None
            replay(family, item['recipe'], item['counterexample'])
        print('VERIFIED', family, counts[family], 'saved counterexamples', flush=True)
        prefix.cache_clear()
    for family, original in (('internal-rc', 'd0015-internal-rc-audit.json'),
                             ('signed', 'd0017-signed-truncation-audit.json'),
                             ('residual', 'd0017-residual-state-audit.json')):
        recipes = read(original)['results']
        report = read(f'd0018-rc-factorization-{family}.json')
        assert report['source_sha256'] == pins[original]
        assert report['programs'] == len(recipes) == len(report['results'])
        assert all(not v for v in report['survivors'].values())
        for index, item in enumerate(report['results']):
            assert index == item['program_index'] and set(item['modes']) == {'rn', 'rd', 'ru', 'rz'}
            for rc, result in item['modes'].items():
                failure = result['counterexample']
                assert failure is not None and failure['input'].split()[1] == rc
                replay(family, recipes[index]['recipe'], failure)
            if (index + 1) % 10000 == 0:
                print('RC REPLAY', family, index + 1, '/', len(recipes), flush=True)
        prefix.cache_clear()
        print('VERIFIED four-mode', family, len(recipes) * 4, 'counterexamples', flush=True)
    save(BASE / 'd0017-d0020-independent-replay.json', dict(status='ALL_SAVED_COUNTEREXAMPLES_INDEPENDENTLY_REPLAYED',
         counts=dict(counts), total=sum(counts.values()), sources=sources, authenticated_frontier_rows=authenticated,
         artifact_sha256=pins, hardware_executed=False, numerical_model_promoted=False))
    print('PASS', sum(counts.values()), 'independent counterexample replays', flush=True)


if __name__ == '__main__':
    main()
