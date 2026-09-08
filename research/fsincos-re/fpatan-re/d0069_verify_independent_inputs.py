"""Read-only mathematical/input audit, independent of candidate predictions."""
import ast
from collections import Counter
from fractions import Fraction
import gzip
import json
from pathlib import Path
import subprocess

from compressed_guard import digest, save

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'tmp/fpatan-re'


def dyadic(integer, step):
    return Fraction(integer << step) if step >= 0 else Fraction(integer, 1 << -step)


def value(se, sig):
    assert 0 <= se < 65536 and 0 <= sig < 1 << 64
    field = se & 32767
    assert field != 32767 and bool(sig >> 63) == bool(field)
    return (-1 if se >> 15 else 1) * dyadic(sig, max(field, 1) - 16446)


def main():
    initial = BASE / 'd0065-independent-inputs'
    combined = BASE / 'd0068-independent-lattice-v2'
    first = json.loads((initial / 'INPUT-POOL-FROZEN.json').read_text())
    second = json.loads((combined / 'INPUT-POOL-FROZEN.json').read_text())
    for directory, receipt in ((initial, first), (combined, second)):
        for name, sha in receipt['files'].items():
            assert digest(directory / name) == sha
        assert receipt['model_loaded'] is False and receipt['hardware_executed'] is False
    assert second['previous_pool_sha256'] == digest(initial / 'INPUT-POOL-FROZEN.json')
    assert second['source_sha256'] == digest(HERE / 'd0068_lattice_inputs.py')
    recipe = json.loads((initial / 'RECIPE.json').read_text())
    for name, sha in recipe['source_sha256'].items():
        assert digest(HERE / name) == sha
    local_dependencies = ('d0065_independent_inputs.py', 'd0068_lattice_inputs.py',
                          'compressed_guard.py', 'protocol.py')
    for name in local_dependencies:
        tree = ast.parse((HERE / name).read_text())
        for node in ast.walk(tree):
            names = ([node.module] if isinstance(node, ast.ImportFrom) else
                     [a.name for a in node.names] if isinstance(node, ast.Import) else [])
            for module in names:
                if module and (HERE / (module + '.py')).exists():
                    assert module + '.py' in local_dependencies, (name, module)

    intervals = {}
    for line in (initial / 'tan-bounds-384.txt').read_text().splitlines():
        ident, lm, le, hm, he = line.split()
        intervals[ident] = dyadic(int(lm, 16), int(le)), dyadic(int(hm, 16), int(he))
    request = ''.join(f'{row["id"]} {row["numerator"]} {row["step"]} 384\n'
                      for row in recipe['angle_targets'])
    binary = Path('/private/tmp/fpatan-d0065-bounds-sanitized')
    assert digest(binary) == first['sanitized_binary_sha256']
    run = subprocess.run([str(binary)], input=request, capture_output=True, text=True, check=True)
    assert not run.stderr and run.stdout == (initial / 'tan-bounds-384.txt').read_text()
    brackets = json.loads((initial / 'BRACKETS.json').read_text())
    for bracket in brackets:
        lo, hi = intervals[bracket['angle']]
        x = value(*(int(v, 16) for v in bracket['x']))
        y0 = value(*(int(v, 16) for v in bracket['below']))
        y1 = value(*(int(v, 16) for v in bracket['above']))
        assert y0 <= lo * x <= hi * x < y1
        se, sig = (int(v, 16) for v in bracket['below'])
        # All frozen bracket pairs are interior to their binade here.
        # Check adjacency from raw fields, separately from generator helpers.
        above = tuple(int(v, 16) for v in bracket['above'])
        if sig == (1 << 64) - 1:
            assert above == (se + 1, 1 << 63)
        elif se == 0 and sig == (1 << 63) - 1:
            assert above == (1, 1 << 63)
        else:
            assert above == (se, sig + 1)
    witnesses = json.loads((combined / 'WITNESSES.json').read_text())
    for witness in witnesses:
        ys, ym, xs, xm = (int(v, 16) for v in witness['pair'])
        ratio = value(ys, ym) / value(xs, xm)
        lo, hi = intervals[witness['angle']]
        assert ratio <= lo if witness['side'] == 'below' else ratio >= hi
        bound = max(abs(ratio - lo), abs(ratio - hi)) * xm / dyadic(1, witness['exponent'])
        saved = Fraction(*(int(v, 16) for v in witness['numerator_unit_error_bound']))
        assert bound == saved <= Fraction(1, 1 << 48)
        assert ys - xs == witness['exponent']
    checks = json.loads((combined / 'ORIGINAL-QUERY-WITNESS-CHECKS.json').read_text())
    for check in checks:
        path = initial / 'smt' / (check['id'] + '.smt2')
        assert digest(path) == check['original_query_sha256']
        assert digest(path.with_suffix('.json')) == check['original_report_sha256']
        if check['status'] != 'SAT_BY_EXACT_WITNESS':
            continue
        ys, ym, xs, xm = (int(v, 16) for v in check['pair'])
        ident, side = check['id'].split('-')
        lo, hi = intervals[ident]
        scale = dyadic(1, 192 - ys + xs)
        left, right = lo * scale, hi * scale
        left = left.numerator // left.denominator
        right = -(-right.numerator // right.denominator)
        residual = ((left * xm - (1 << 192) * ym, right * xm - (1 << 192) * ym)
                    if side == 'below' else
                    ((1 << 192) * ym - right * xm, (1 << 192) * ym - left * xm))
        assert 0 <= residual[0] <= residual[1] <= 1 << 144
        assert 1 << 63 <= ym < 1 << 64 and 1 << 63 <= xm < 1 << 64
    pool, counts, exponents = set(), Counter(), [set(), set()]
    with gzip.open(combined / 'pair-pool.tsv.gz', 'rt') as stream:
        for line in stream:
            raw, kind = line.rstrip().split('\t')
            pair = tuple(int(v, 16) for v in raw.split())
            assert pair not in pool
            pool.add(pair)
            value(*pair[:2])
            value(*pair[2:])
            counts['pairs'] += 1
            counts['family:' + kind.split(':')[0]] += 1
            if kind == 'raw-exponent-permutation':
                exponents[0].add(pair[0] & 32767)
                exponents[1].add(pair[2] & 32767)
    assert counts == second['counts']
    assert all(fields == set(range(32767)) for fields in exponents)
    windows = json.loads((initial / 'WINDOWS.json').read_text())
    for window in windows:
        ys, ym = (int(v, 16) for v in window['y'])
        xs, xm = (int(v, 16) for v in window['x'])
        for dy in range(-8, 9):
            for dx in range(-8, 9):
                for y, x in (((ys, ym + dy), (xs, xm + dx)), ((xs, xm + dx), (ys, ym + dy))):
                    for sy in (0, 32768):
                        for sx in (0, 32768):
                            assert (y[0] | sy, y[1], x[0] | sx, x[1]) in pool
    save(BASE / 'd0069-independent-input-audit.json', dict(status='PASS_INDEPENDENT_INPUT_CONSTRUCTION',
        counts=counts, brackets=len(brackets), exact_lattice_witnesses=len(witnesses),
        original_query_statuses=Counter(c['original_outcome'] for c in checks),
        constructive_query_statuses=Counter(c['status'] for c in checks),
        exhaustive_windows=len(windows), window_pairs_per_sign_swap=289,
        all_finite_exponent_fields_in_both_operands=True, model_import_dependency_audit='PASS',
        source_sha256=digest(Path(__file__)), hardware_executed=False,
        pool_receipt_sha256=digest(combined / 'INPUT-POOL-FROZEN.json'),
        limits='Independent finite-input generation audit, not silicon equivalence proof.'))
    print('PASS independent generator audit', json.dumps(counts), flush=True)


if __name__ == '__main__':
    main()
