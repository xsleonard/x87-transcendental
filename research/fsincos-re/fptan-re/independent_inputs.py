"""Model-blind FPTAN challenges: inverse mathematics, residue search, raw bits.

Mathematical atan(t)+k*pi selects sensitivity tests, not expected silicon
answers. Exact residue counts allow binary subdivision of a mathematical
condition; they never exclude an interval from hardware-miss testing.
"""
from collections import Counter
from fractions import Fraction as Q
import gzip
import json
import random
import subprocess
import sys
from pathlib import Path

from support import BASE, HERE, digest, save

SEED = 'fptan-t0001-independent-20260906'
TOP = 1 << 63


def two(e):
    return Q(1 << e) if e >= 0 else Q(1, 1 << -e)


def value(se, sig):
    return (-1 if se & 32768 else 1) * sig * two(max(se & 32767, 1) - 16446)


def floor_raw(v):
    assert v >= 0
    if not v:
        return 0, 0
    e = v.numerator.bit_length() - v.denominator.bit_length()
    e -= v < two(e)
    e = max(e, -16382)
    assert e < 16384
    q = v / two(e - 63)
    sig = q.numerator // q.denominator
    return (e + 16383 if sig >= TOP else 0), sig


def neighbor(raw, delta):
    se, sig = raw
    if delta > 0:
        return (se + 1, TOP) if sig == (1 << 64) - 1 else (1, TOP) if se == 0 and sig == TOP - 1 else (se, sig + 1)
    if delta < 0:
        return (se - 1, (1 << 64) - 1) if se > 1 and sig == TOP else (0, TOP - 1) if se == 1 and sig == TOP else (se, sig - 1)
    return raw


def floor_sum(n, m, a, b):
    """Exact sum floor((a*i+b)/m), 0<=i<n, including signed a,b."""
    qa, a = divmod(a, m)
    qb, b = divmod(b, m)
    result = qa * n * (n - 1) // 2 + qb * n
    while True:
        if a >= m:
            result += (n - 1) * n * (a // m) // 2
            a %= m
        if b >= m:
            result += n * (b // m)
            b %= m
        maximum = a * n + b
        if maximum < m:
            return result
        n, b = divmod(maximum, m)
        m, a = a, m


def count_low(n, m, a, b, limit):
    return n - (floor_sum(n, m, a, b + m - limit) - floor_sum(n, m, a, b))


def near_count(start, size, m, a, b, margin):
    shifted = a * start + b
    return count_low(size, m, a, shifted, margin) + size - count_low(size, m, a, shifted, m - margin)


def near_indices(start, size, m, a, b, margin, limit=4):
    result = []
    def visit(begin, length):
        if not length or len(result) >= limit or not near_count(begin, length, m, a, b, margin):
            return
        if length == 1:
            result.append(begin)
            return
        half = length // 2
        visit(begin, half)
        visit(begin + half, length - half)
    visit(start, size)
    return result


def parse_bounds(text):
    result = {}
    for line in text.splitlines():
        name, lo, le, hi, he = line.split()
        result[name] = int(lo, 16) * two(int(le)), int(hi, 16) * two(int(he))
    return result


def main():
    out = BASE / 't0001-inputs'
    out.mkdir(parents=True, exist_ok=False)
    rng = random.Random(SEED)
    targets = []
    for exponent in (-128, -64, -32, -8, -1, 0, 1, 8, 32, 64, 128):
        for index in range(8):
            sig = TOP | rng.getrandbits(63)
            for midpoint in (False, True):
                targets.append(dict(id=f'a{len(targets):04d}', exponent=exponent,
                    kind='RN-midpoint' if midpoint else 'directed-boundary', sample=index,
                    sig=f'{2 * sig + 1 if midpoint else sig:x}', step=exponent - (64 if midpoint else 63)))
    save(out / 'RECIPE.json', dict(seed=SEED, targets=targets, model_loaded=False,
        raw_exponent_fields=32766, active_raw_inputs=16384, windows=32, window_offsets=[-128, 128],
        source_sha256={n: digest(HERE / n) for n in ('independent_inputs.py', 'math_bounds.c', 'support.py')}))
    def request(precision):
        return f'pi pi 0 0 {precision}\n' + ''.join(f'{t["id"]} atan {t["sig"]} {t["step"]} {precision}\n' for t in targets)
    outputs = []
    for binary, precision in (('/private/tmp/fptan-t0001-bounds', 384),
                              ('/private/tmp/fptan-t0001-bounds', 768),
                              ('/private/tmp/fptan-t0001-bounds-sanitized', 768)):
        run = subprocess.run([binary], input=request(precision), text=True, capture_output=True, check=True)
        assert not run.stderr
        outputs.append(run.stdout)
    assert outputs[1] == outputs[2]
    coarse, bounds = map(parse_bounds, outputs[:2])
    for ident, (lo, hi) in bounds.items():
        assert coarse[ident][0] <= lo <= hi <= coarse[ident][1]
    for name, text in (('bounds-384.txt', outputs[0]), ('bounds-768.txt', outputs[1])):
        with (out / name).open('x') as stream:
            stream.write(text)
    pi_lo, pi_hi = bounds['pi']
    counts, pool, certificates = Counter(), {}, []
    def emit(raw, kind):
        se, sig = raw
        if not sig or se >= 32767:
            return
        for sign in (0, 32768):
            key = se | sign, sig
            if key in pool:
                counts['duplicate_proposals'] += 1
            else:
                pool[key] = kind
    def bracket(lo, hi, kind, metadata):
        lower, upper_floor = floor_raw(lo), floor_raw(hi)
        upper = neighbor(upper_floor, 1)
        assert value(*lower) <= lo <= hi < value(*upper)
        cert = dict(kind=kind, below=[f'{v:x}' for v in lower], above=[f'{v:x}' for v in upper],
                    adjacent=neighbor(lower, 1) == upper, **metadata)
        certificates.append(cert)
        for center in (lower, upper):
            current = center
            for _ in range(2):
                current = neighbor(current, -1)
            for _ in range(5):
                emit(current, kind)
                current = neighbor(current, 1)
    periods = (0, 1, 2, 17, 257, 65537, (1 << 20) + 37, (1 << 40) + 73, (1 << 60) + 151, (1 << 61) + 181)
    for target in targets:
        lo, hi = bounds[target['id']]
        for k in periods:
            bracket(lo + k * pi_lo, hi + k * pi_hi, 'inverse-output-boundary', dict(target=target['id'], period=k))
    for bit in range(63):
        for offset in (-1, 0, 1):
            multiple = (1 << bit) + offset
            if multiple <= 0:
                continue
            bracket(multiple * pi_lo / 2, multiple * pi_hi / 2,
                    'mathematical-pole' if multiple & 1 else 'mathematical-zero', dict(half_period=multiple))

    # A 256-bit affine residue is a search filter only. Exact MPFR bounds
    # independently confirm every retained full-width external witness.
    sys.path.insert(0, '/private/tmp/fsincos-smt-deps')
    import z3
    query_dir = out / 'queries'
    query_dir.mkdir()
    queries = []
    selected = [t for t in targets if t['kind'] == 'RN-midpoint' and t['exponent'] in (-8, 0, 8) and t['sample'] < 2]
    for target in selected:
        alpha_lo, alpha_hi = bounds[target['id']]
        for exponent in (16, 32, 48, 60, 62):
            unit = two(exponent - 63)
            lower_k = (two(exponent) - alpha_lo) / pi_lo
            upper_k = (two(exponent + 1) - alpha_hi) / pi_hi
            lower_k = -(-lower_k.numerator // lower_k.denominator)
            upper_k = upper_k.numerator // upper_k.denominator
            size = min(1 << 20, upper_k - lower_k)
            begin = rng.randrange(lower_k, upper_k - size + 1) if upper_k - lower_k > size else lower_k
            modulus = 1 << 256
            aa = (pi_lo + pi_hi) / 2 / unit * modulus
            bb = (alpha_lo + alpha_hi) / 2 / unit * modulus
            a, b = aa.numerator // aa.denominator, bb.numerator // bb.denominator
            candidates = near_indices(begin, size, modulus, a, b, 1 << 241, limit=8)
            accepted = []
            for k in candidates:
                lo, hi = (alpha_lo + k * pi_lo) / unit, (alpha_hi + k * pi_hi) / unit
                center = (lo + hi) / 2 + Q(1, 2)
                n = center.numerator // center.denominator
                if not TOP <= n < 1 << 64 or max(abs(n - lo), abs(n - hi)) > two(-16):
                    continue
                accepted.append(dict(k=k, n=f'{n:x}'))
                bracket(lo * unit, hi * unit, 'exact-residue-boundary', dict(target=target['id'], period=k))
            ident = f'{target["id"]}-e{exponent}'
            solver = z3.SolverFor('QF_LIA')
            solver.set(timeout=500)
            k_var, n_var = z3.Ints('period significand')
            denominator = 1 << 768
            def floor(v):
                return v.numerator // v.denominator
            al = floor(alpha_lo / unit * denominator)
            ah = -floor(-alpha_hi / unit * denominator)
            pl = floor(pi_lo / unit * denominator)
            ph = -floor(-pi_hi / unit * denominator)
            margin = denominator >> 16
            solver.add(k_var >= begin, k_var < begin + size, n_var >= TOP, n_var < 1 << 64,
                       n_var * denominator - (al + pl * k_var) <= margin,
                       (ah + ph * k_var) - n_var * denominator <= margin)
            query_path = query_dir / (ident + '.smt2')
            with query_path.open('x') as stream:
                stream.write(solver.to_smt2())
            outcome = solver.check()
            report = dict(id=ident, result=str(outcome), timeout_ms=500,
                reason=solver.reason_unknown() if outcome == z3.unknown else None,
                begin=begin, size=size, exponent=exponent, exact_witnesses=accepted,
                filter_candidate_count=near_count(begin, size, modulus, a, b, 1 << 241),
                query_sha256=digest(query_path))
            if accepted:
                witness = accepted[0]
                n, k = int(witness['n'], 16), witness['k']
                assert n * denominator - (al + pl * k) <= margin
                assert (ah + ph * k) - n * denominator <= margin
                solver.push()
                solver.add(k_var == k, n_var == n)
                assert solver.check() == z3.sat
                solver.pop()
                report['constructive_status'] = 'SAT_BY_EXACT_WITNESS'
                assert outcome != z3.unsat
            else:
                report['constructive_status'] = 'NO_CONSTRUCTED_WITNESS_NOT_EXCLUSION'
            save(query_dir / (ident + '.json'), report)
            queries.append(report)
            print('Query', ident, outcome, 'exact witnesses', len(accepted), flush=True)
    for field in range(1, 32767):
        emit((field, TOP | rng.getrandbits(63)), 'raw-exponent-stratum')
    for index in range(8192):
        emit((16383 + rng.randrange(-128, 63), TOP | rng.getrandbits(63)), 'raw-active-range')
        emit((16383 + rng.randrange(0, 63), TOP | rng.getrandbits(63)), 'raw-large-reduction')
    windows = []
    exponents = (-16382, -128, -69, -32, -3, -1, 0, 1, 16, 32, 48, 62, 63, 16383)
    for index in range(32):
        exponent = exponents[index % len(exponents)]
        sig = TOP + (1 << 61) + rng.getrandbits(60)
        windows.append(dict(se=exponent + 16383, sig=f'{sig:x}', offsets=[-128, 128]))
        for delta in range(-128, 129):
            emit((exponent + 16383, sig + delta), 'exhaustive-window')
    with gzip.open(out / 'operand-pool.tsv.gz', 'xt') as stream:
        for (se, sig), kind in pool.items():
            stream.write(f'{se:04x} {sig:016x}\t{kind}\n')
            counts['operands'] += 1
            counts['family:' + kind] += 1
    save(out / 'BRACKETS.json', certificates)
    save(out / 'WINDOWS.json', windows)
    save(out / 'INPUT-POOL-FROZEN.json', dict(status='MODEL_INDEPENDENT_INPUT_POOL_FROZEN', counts=counts,
        queries=Counter(q['result'] for q in queries), constructive=Counter(q['constructive_status'] for q in queries),
        files={p.name: digest(p) for p in out.iterdir() if p.is_file()}, model_loaded=False,
        limits='Finite model-blind challenge. Mathematical targets select inputs, not silicon outputs. Residue enumeration is bounded and keeps at most eight candidates per query.'))
    print('FROZEN', json.dumps(counts), flush=True)


if __name__ == '__main__':
    main()
