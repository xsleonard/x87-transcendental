"""Solver-free reconstruction and verification of the D0014 certificate.

Reads the original native observations and public ROM TSV. It does not import
the graph, SMT encoders, interval/preimage solvers or certificate generator.
Independent integer rounding and binary searches reconstruct every endpoint
constraint. Exact rational arithmetic then verifies the weighted contradiction.
"""
import argparse
import csv
from fractions import Fraction as F
import functools
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
from d0011_verify_role_certificate import rounded
from protocol import validate_output
from prepare import save

BASE = Path(__file__).resolve().parents[1] / 'tmp/fpatan-re'


def two(e):
    return F(2 ** e) if e >= 0 else F(1, 2 ** -e)


def binade(x):
    x = abs(x)
    e = x.numerator.bit_length() - x.denominator.bit_length()
    return e - (x < two(e))


def rom_constants():
    path = Path(__file__).resolve().parents[1] / 'data/pentium-rom/rom-constants.tsv'
    with path.open() as f:
        rows = list(csv.DictReader(f, delimiter='\t'))
    return {int(r['row']): (-1 if r['sign'] == '1' else 1) * int(r['sig68'], 16) *
            two(int(r['exp'], 16) - 65535 - 66) for r in rows if 118 <= int(r['row']) <= 123}


def angle_interval(rows):
    low, high, closed_low, closed_high = F(0), F(1), True, True

    def intersect(a, b, ac, bc):
        nonlocal low, high, closed_low, closed_high
        if a > low:
            low, closed_low = a, ac
        elif a == low:
            closed_low &= ac
        if b < high:
            high, closed_high = b, bc
        elif b == high:
            closed_high &= bc

    for row in rows:
        assert not row['se'] & 32768 and row['input'].split()[2] == '64'
        unit = two(row['se'] - 16383 - 63)
        y = row['sig'] * unit
        previous = y - (unit / 2 if row['sig'] == 1 << 63 else unit)
        following = y + unit
        rc = row['input'].split()[1]
        if rc == 'rn':
            intersect((previous + y) / 2, (y + following) / 2, not row['sig'] & 1, not row['sig'] & 1)
        elif rc == 'ru':
            intersect(previous, y, False, True)
        else:
            assert rc in ('rd', 'rz')
            intersect(y, following, True, False)
        if row['C1']:
            intersect(F(0), y, True, False)
        else:
            intersect(y, F(1), True, True)
    assert low < high or (low == high and closed_low and closed_high)
    return low, high, closed_low, closed_high


def inverse_endpoint(z, u, rows):
    low, high, lc, hc = angle_interval(rows)
    cube = rounded(z * u, 'chop67')
    unit = two(-65)

    def endpoint(q):
        return z - rounded(cube * q * unit, 'chop67')

    def lower_bound(predicate):
        a, b = 1 << 63, 1 << 64
        while a < b:
            mid = (a + b) // 2
            if predicate(endpoint(mid)):
                b = mid
            else:
                a = mid + 1
        return a

    first = lower_bound(lambda v: v < high or (hc and v == high))
    after = lower_bound(lambda v: v < low or (not lc and v == low))
    assert (1 << 63) <= first < after <= (1 << 64)
    return -(after - 1) * unit, -first * unit


def necessary_inequality(point, direction, rows, centers, units, bound):
    raw = [int(v, 16) for v in point['input'].split()[3:]]
    ys, ym, xs, xm = raw
    assert 0 < ys < 32767 and 0 < xs < 32767
    ratio = F(ym, xm) * two(ys - xs)
    assert two(-40) <= ratio < F(3, 64)
    z = rounded(ratio, 'chop67')
    u = rounded(z * rounded(z, 'chop64'), 'rn64')
    assert z == F(point['z']) and u == F(point['u'])
    target_lo, target_hi = inverse_endpoint(z, u, rows)
    assert (target_lo, target_hi) == (F(point['h118_target']['h118_lo']), F(point['h118_target']['h118_hi']))
    lo, hi = centers[123] - bound * units[123], centers[123] + bound * units[123]
    error_lo = error_hi = F(0)
    weights = {123: F(1)}
    for k in range(122, 117, -1):
        lo *= u
        hi *= u
        assert lo * hi > 0
        step = two(max(binade(lo), binade(hi)) - 66)
        error_lo *= u
        error_hi *= u
        if lo > 0:
            error_lo -= step
        else:
            error_hi += step
        lo = rounded(lo, 'chop67') + centers[k] - bound * units[k]
        hi = rounded(hi, 'chop67') + centers[k] + bound * units[k]
        assert lo * hi > 0
        step = two(max(binade(lo), binade(hi)) - 63)
        error_lo -= step / 2
        error_hi += step / 2
        lo, hi = rounded(lo, 'rn64'), rounded(hi, 'rn64')
        weights = {j: weight * u for j, weight in weights.items()}
        weights[k] = F(1)
    assert error_lo == F(point['accumulated_error_lo']) and error_hi == F(point['accumulated_error_hi'])
    poly_lo, poly_hi = target_lo - error_hi, target_hi - error_lo
    assert poly_lo == F(point['polynomial_lo']) and poly_hi == F(point['polynomial_hi'])
    coefficients = [weights[k] * units[k] for k in range(118, 124)]
    center = sum(weights[k] * centers[k] for k in range(118, 124))
    if direction == 'upper':
        right = poly_hi - center
    else:
        assert direction == 'lower'
        coefficients = [-v for v in coefficients]
        right = center - poly_lo
    denominator = math.lcm(*(v.denominator for v in coefficients + [right]))
    ints = [int(v * denominator) for v in coefficients + [right]]
    divisor = functools.reduce(math.gcd, ints)
    return [v // divisor for v in ints[:-1]], ints[-1] // divisor


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('certificate', type=Path)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    assert not args.out.exists()
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    report = json.loads(args.certificate.read_text())
    relaxation = Path(report['relaxation'])
    assert digest(relaxation) == report['relaxation_sha256']
    bound = json.loads(relaxation.read_text())['bound_in_69bit_grid_ULPs']
    certificate = report['certificate']
    centers = rom_constants()
    units = {k: two(binade(v) - 68) for k, v in centers.items()}
    assert {str(k): str(v) for k, v in centers.items()} == report['coefficient_centers']
    assert {str(k): str(v) for k, v in units.items()} == report['coefficient_units']
    points = {row['point']['input']: row['point'] for row in certificate['inequalities'] if row['kind'] == 'observation'}
    wanted_raw = {tuple(line.split()[3:]): line for line in points}
    found = {line: [] for line in points}
    job = BASE / 'd0009'
    receipt = json.loads((job / 'COMPLETE.json').read_text())
    manifest = json.loads((job / 'MANIFEST.json').read_text())
    assert digest(job / 'MANIFEST.json') == receipt['manifest_sha256']
    assert digest(job / 'inputs.txt.gz') == manifest['files']['inputs.txt.gz']
    assert digest(job / 'hardware.txt.gz') == receipt['hardware_gzip_sha256']
    sha = hashlib.sha256()
    total = 0
    with gzip.open(job / 'inputs.txt.gz', 'rt') as inputs, gzip.open(job / 'hardware.txt.gz', 'rt') as hardware:
        for inp, out in itertools.zip_longest(inputs, hardware):
            assert inp is not None and out is not None
            sha.update(out.encode())
            total += 1
            actual = validate_output(out, inp)
            tokens = inp.split()
            key = wanted_raw.get(tuple(tokens[3:]))
            if key and tokens[2] == '64':
                found[key].append(dict(input=inp.strip(), hardware=out.strip(), **actual))
    assert total == receipt['rows'] and sha.hexdigest() == receipt['hardware_sha256']
    assert all(len(rows) == 4 and {r['input'].split()[1] for r in rows} == {'rn', 'rd', 'ru', 'rz'} for rows in found.values())
    for row in certificate['inequalities']:
        assert F(row['weight']) > 0
        if row['kind'] == 'observation':
            a, b = necessary_inequality(row['point'], row['direction'], found[row['point']['input']], centers, units, bound)
        else:
            a = [0] * 6
            assert row['sign'] in (-1, 1)
            a[row['coefficient'] - 118] = row['sign']
            b = bound
        assert a == row['coefficients'] and b == row['bound']
    left = [sum(F(r['weight']) * r['coefficients'][k] for r in certificate['inequalities']) for k in range(6)]
    right = sum(F(r['weight']) * r['bound'] for r in certificate['inequalities'])
    assert left == [0] * 6 and right < 0
    save(args.out, dict(status='INDEPENDENT_SOLVER_FREE_CERTIFICATE_PASS', certificate_sha256=digest(args.certificate),
                       hardware_sha256=sha.hexdigest(), authenticated_capture_rows=total,
                       distinct_core_inputs=len(points), core_observations=sum(map(len, found.values())),
                       original_observations=found, weighted_left=[str(v) for v in left], weighted_right=str(right),
                       conclusion='Independently reconstructed necessary inequalities imply 0 <= -1.',
                       hardware_executed=False))
    print('PASS solver-free certificate;', len(points), 'inputs;', sum(map(len, found.values())), 'native observations;',
          len(certificate['inequalities']), 'inequalities; contradiction', right, flush=True)


if __name__ == '__main__':
    main()
