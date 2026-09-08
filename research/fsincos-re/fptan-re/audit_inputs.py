"""Independent replay of mathematical certificates and exact query witnesses."""
import ast
from collections import Counter
from fractions import Fraction as Q
import json
import subprocess

from support import BASE, HERE, digest, lines, read, save


def dyadic(n, e):
    return Q(n << e) if e >= 0 else Q(n, 1 << -e)


def value(se, sig):
    return (-1 if se & 32768 else 1) * dyadic(sig, max(se & 32767, 1) - 16446)


def main():
    source = BASE / 't0001-inputs'
    receipt = read(source / 'INPUT-POOL-FROZEN.json')
    for name, sha in receipt['files'].items():
        assert digest(source / name) == sha
    recipe = read(source / 'RECIPE.json')
    for name, sha in recipe['source_sha256'].items():
        assert digest(HERE / name) == sha
    for filename in ('independent_inputs.py', 'support.py'):
        for node in ast.walk(ast.parse((HERE / filename).read_text())):
            modules = [node.module] if isinstance(node, ast.ImportFrom) else [n.name for n in node.names] if isinstance(node, ast.Import) else []
            for module in modules:
                if module and (HERE / (module + '.py')).exists():
                    assert module == 'support'
    request = 'pi pi 0 0 768\n' + ''.join(f'{t["id"]} atan {t["sig"]} {t["step"]} 768\n' for t in recipe['targets'])
    binary = '/private/tmp/fptan-t0001-bounds-sanitized'
    run = subprocess.run([binary], input=request, text=True, capture_output=True, check=True)
    assert not run.stderr and run.stdout == (source / 'bounds-768.txt').read_text()
    bounds = {}
    for line in run.stdout.splitlines():
        ident, lo, le, hi, he = line.split()
        bounds[ident] = dyadic(int(lo, 16), int(le)), dyadic(int(hi, 16), int(he))
    pi_lo, pi_hi = bounds['pi']
    brackets = read(source / 'BRACKETS.json')
    for certificate in brackets:
        if 'half_period' in certificate:
            lo, hi = certificate['half_period'] * pi_lo / 2, certificate['half_period'] * pi_hi / 2
        else:
            a, b = bounds[certificate['target']]
            lo, hi = a + certificate['period'] * pi_lo, b + certificate['period'] * pi_hi
        lower, upper = [tuple(int(v, 16) for v in certificate[key]) for key in ('below', 'above')]
        assert value(*lower) <= lo <= hi < value(*upper)
        assert lower[0] == upper[0] and lower[1] + 1 == upper[1]
        assert certificate['adjacent']
    query_counts = Counter()
    for path in sorted((source / 'queries').glob('*.json')):
        query = read(path)
        assert digest(path.with_suffix('.smt2')) == query['query_sha256']
        ident = query['id'].split('-')[0]
        a, b = bounds[ident]
        unit = dyadic(1, query['exponent'] - 63)
        for witness in query['exact_witnesses']:
            n, k = int(witness['n'], 16), witness['k']
            assert 1 << 63 <= n < 1 << 64
            assert query['begin'] <= k < query['begin'] + query['size']
            lo, hi = (a + k * pi_lo) / unit, (b + k * pi_hi) / unit
            assert max(abs(n - lo), abs(n - hi)) <= Q(1, 1 << 16)
            query_counts['exact_external_witnesses'] += 1
        query_counts['original:' + query['result']] += 1
        query_counts['constructive:' + query['constructive_status']] += 1
    pool, counts, exponent_fields = set(), Counter(), set()
    for line in lines(source / 'operand-pool.tsv.gz'):
        raw, kind = line.rstrip().split('\t')
        se, sig = (int(v, 16) for v in raw.split())
        assert (se, sig) not in pool
        pool.add((se, sig))
        assert 0 < se & 32767 < 32767 and 1 << 63 <= sig < 1 << 64
        counts['operands'] += 1
        counts['family:' + kind] += 1
        if kind == 'raw-exponent-stratum':
            exponent_fields.add(se & 32767)
    assert exponent_fields == set(range(1, 32767))
    for name, count in counts.items():
        assert receipt['counts'][name] == count
    windows = read(source / 'WINDOWS.json')
    for window in windows:
        for delta in range(-128, 129):
            for sign in (0, 32768):
                assert (window['se'] | sign, int(window['sig'], 16) + delta) in pool
    save(BASE / 'INPUT-CONSTRUCTION-AUDIT.json', dict(status='PASS_INDEPENDENT_INPUT_CONSTRUCTION',
        counts=counts, mathematical_brackets=len(brackets), query_counts=query_counts,
        complete_generated_windows=len(windows), candidates_use_model=False,
        source_sha256=digest(HERE / 'audit_inputs.py'), verified_mpfr_binary_sha256=digest(binary),
        pool_receipt_sha256=digest(source / 'INPUT-POOL-FROZEN.json'),
        limits='Generated windows are complete; any history-held members are not automatically captured or credited. Math is selection, not hardware truth.'))
    print('PASS independent input construction', dict(counts), dict(query_counts), flush=True)


if __name__ == '__main__':
    main()
