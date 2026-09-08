"""Freeze model-independent FPATAN challenges before any model evaluation.

Only MPFR mathematics, raw80 format arithmetic and integer constraints are
used for selection. The SMT queries describe representable operand ratios,
not the proposed microarchitecture. All solver outcomes are retained.
"""
import argparse
from collections import Counter
from fractions import Fraction
import gzip
import json
from pathlib import Path
import random
import subprocess
import sys
import time

from compressed_guard import digest, save

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'tmp/fpatan-re'
SEED = 'fpatan-d0065-independent-mathematics-20260906'
BIAS = 16383
INTEGER_BIT = 1 << 63


def two(exponent):
    return Fraction(1 << exponent) if exponent >= 0 else Fraction(1, 1 << -exponent)


def decode(raw):
    se, sig = raw
    return (-1 if se & 32768 else 1) * sig * two(max(se & 32767, 1) - BIAS - 63)


def floor_log2(value):
    exponent = value.numerator.bit_length() - value.denominator.bit_length()
    return exponent - (value < two(exponent))


def floor_raw(value):
    """Greatest nonnegative canonical finite raw80 value <= value."""
    assert value >= 0
    if not value:
        return 0, 0
    exponent = max(-16382, floor_log2(value))
    assert exponent <= 16383
    scaled = value / two(exponent - 63)
    sig = scaled.numerator // scaled.denominator
    return (exponent + BIAS if sig >= INTEGER_BIT else 0), sig


def neighbor(raw, delta):
    """Move in the canonical positive-value lattice, crossing binades."""
    se, sig = raw
    assert 0 <= se < 32767 and delta in (-1, 0, 1)
    if not delta:
        return raw
    if delta > 0:
        if sig == (1 << 64) - 1:
            return se + 1, INTEGER_BIT
        if se == 0 and sig == INTEGER_BIT - 1:
            return 1, INTEGER_BIT
        return se, sig + 1
    assert sig
    if se > 1 and sig == INTEGER_BIT:
        return se - 1, (1 << 64) - 1
    if se == 1 and sig == INTEGER_BIT:
        return 0, INTEGER_BIT - 1
    return se, sig - 1


def orbits(pair):
    for swap in (False, True):
        y, x = (pair[2:], pair[:2]) if swap else (pair[:2], pair[2:])
        for sy in (0, 32768):
            for sx in (0, 32768):
                yield y[0] | sy, y[1], x[0] | sx, x[1]


def exact_scale(pair, shift):
    values = [decode(pair[:2]) * two(shift), decode(pair[2:]) * two(shift)]
    if max(values) >= two(16384):
        return None
    raw = [floor_raw(v) for v in values]
    if any(not r[1] or decode(r) != v for r, v in zip(raw, values)):
        return None
    return *raw[0], *raw[1]


def targets():
    rng = random.Random(SEED + ':angles')
    result = []
    for exponent in (-16382, -8192, -1024, -128, -65, -64, -63,
                     -33, -32, -16, -8, -4, -3, -2, -1):
        for _ in range(4):
            sig = INTEGER_BIT | rng.getrandbits(63)
            for kind in ('RN-midpoint', 'directed-boundary'):
                numerator = 2 * sig + 1 if kind == 'RN-midpoint' else sig
                step = exponent - (64 if kind == 'RN-midpoint' else 63)
                result.append(dict(id=f'a{len(result):04d}', kind=kind,
                                   numerator=f'{numerator:x}', step=step))
    for sig in (1, 2, 3, (1 << 31) - 1, 1 << 31, (1 << 62) - 1,
                1 << 62, INTEGER_BIT - 2, INTEGER_BIT - 1):
        for kind in ('RN-midpoint', 'directed-boundary'):
            numerator = 2 * sig + 1 if kind == 'RN-midpoint' else sig
            result.append(dict(id=f'a{len(result):04d}', kind=kind,
                numerator=f'{numerator:x}', step=-16446 if kind == 'RN-midpoint' else -16445))
    return result


def bound_request(rows, precision):
    return ''.join(f'{r["id"]} {r["numerator"]} {r["step"]} {precision}\n' for r in rows)


def parse_bounds(text):
    result = {}
    for line in text.splitlines():
        ident, lm, le, hm, he = line.split()
        assert ident not in result
        result[ident] = int(lm, 16) * two(int(le)), int(hm, 16) * two(int(he))
    return result


def bounds(binary, request):
    run = subprocess.run([str(binary)], input=request, text=True,
                         capture_output=True, check=True)
    assert not run.stderr
    return run.stdout


def smt_pairs(rows, intervals, out):
    """Find ratios within 2^-48 numerator units of a mathematical boundary.

    A and B are 64-bit canonical significands. Linear integer constraints
    avoid treating transcendental tan as an exact solver primitive. The
    384-bit MPFR enclosure is outward-rounded to a 192-bit fixed grid.
    """
    sys.path.insert(0, '/private/tmp/fsincos-smt-deps')
    import z3
    query_dir = out / 'smt'
    query_dir.mkdir()
    chosen = [r for r in rows if r['kind'] == 'RN-midpoint' and
              -70 <= r['step'] + 64 <= -1][::4]
    reports, witnesses = [], []
    for row in chosen:
        lower, upper = intervals[row['id']]
        exponent = floor_log2(lower)
        assert floor_log2(upper) == exponent
        denominator = 1 << 192
        low = lower * two(-exponent) * denominator
        high = upper * two(-exponent) * denominator
        low = low.numerator // low.denominator
        high = -(-high.numerator // high.denominator)
        for side in ('below', 'above'):
            ident = row['id'] + '-' + side
            solver = z3.SolverFor('QF_LIA')
            solver.set(timeout=2000)
            a, b = z3.Ints('y_significand x_significand')
            solver.add(a >= INTEGER_BIT, a < 2 * INTEGER_BIT,
                       b >= INTEGER_BIT, b < 2 * INTEGER_BIT)
            if side == 'below':
                solver.add(low * b - denominator * a >= 0,
                           high * b - denominator * a <= 1 << 144)
            else:
                solver.add(denominator * a - high * b >= 0,
                           denominator * a - low * b <= 1 << 144)
            query = query_dir / (ident + '.smt2')
            with query.open('x') as target:
                target.write(solver.to_smt2())
            started = time.monotonic()
            outcome = solver.check()
            report = dict(id=ident, result=str(outcome), seconds=time.monotonic() - started,
                          query_sha256=digest(query), exponent=exponent,
                          solver='Z3 ' + z3.get_version_string(), timeout_ms=2000)
            if outcome == z3.sat:
                model = solver.model()
                ym, xm = model[a].as_long(), model[b].as_long()
                residual = ((low * xm - denominator * ym, high * xm - denominator * ym)
                            if side == 'below' else
                            (denominator * ym - high * xm, denominator * ym - low * xm))
                assert 0 <= residual[0] <= residual[1] <= 1 << 144
                pair = exponent + BIAS, ym, BIAS, xm
                ratio = decode(pair[:2]) / decode(pair[2:])
                assert ratio <= lower if side == 'below' else ratio >= upper
                report['pair'] = [f'{v:x}' for v in pair]
                report['exact_integer_replay'] = True
                witnesses.append((pair, 'SMT-math-boundary:' + side))
            elif outcome == z3.unknown:
                report['reason'] = solver.reason_unknown()
            reports.append(report)
            save(query_dir / (ident + '.json'), report)
            print('SMT', ident, str(outcome), flush=True)
    return witnesses, reports


def construct(binary, sanitized, out):
    out.mkdir(parents=True, exist_ok=False)
    rows = targets()
    save(out / 'RECIPE.json', dict(status='MODEL_INDEPENDENT_RECIPE_BEFORE_SELECTION',
        seed=SEED, angle_targets=rows, raw_exponent_sweep=32767,
        balanced_random_pairs=4096, exhaustive_windows=16, window_shape=[17, 17],
        model_imports=[], hardware_executed=False, mathematical_reference_is_not_silicon=True,
        source_sha256={name: digest(HERE / name) for name in
                      ('d0065_independent_inputs.py', 'd0065_math_bounds.c')}))
    request = bound_request(rows, 192)
    original = bounds(binary, request)
    sanitized_result = bounds(sanitized, request)
    assert original == sanitized_result
    refined = bounds(binary, bound_request(rows, 384))
    low_precision, intervals = parse_bounds(original), parse_bounds(refined)
    for ident, (lo, hi) in intervals.items():
        old_lo, old_hi = low_precision[ident]
        assert 0 < old_lo <= lo <= hi <= old_hi
    for name, text in (('angles-192.txt', request), ('tan-bounds-192.txt', original),
                       ('tan-bounds-384.txt', refined)):
        with (out / name).open('x') as target:
            target.write(text)
    solved, queries = smt_pairs(rows, intervals, out)
    counts, seen, brackets = Counter(), set(), []
    rng = random.Random(SEED + ':denominators')
    with gzip.open(out / 'pair-pool.tsv.gz', 'xt') as pool:
        def emit(pair, family):
            if pair in seen:
                counts['duplicate_proposals'] += 1
                return
            assert 0 <= pair[0] <= 65535 and 0 <= pair[2] <= 65535
            assert 0 <= pair[1] < 1 << 64 and 0 <= pair[3] < 1 << 64
            seen.add(pair)
            counts['pairs'] += 1
            counts['family:' + family.split(':')[0]] += 1
            pool.write(f'{pair[0]:04x} {pair[1]:016x} {pair[2]:04x} {pair[3]:016x}\t{family}\n')

        for row in rows:
            lower, upper = intervals[row['id']]
            for _ in range(4):
                x = BIAS, INTEGER_BIT | rng.getrandbits(63)
                lo_y, hi_y = floor_raw(lower * decode(x)), floor_raw(upper * decode(x))
                if lo_y != hi_y:
                    counts['unresolved_mathematical_brackets'] += 1
                    continue
                next_y = neighbor(lo_y, 1)
                assert decode(lo_y) <= lower * decode(x)
                assert decode(next_y) > upper * decode(x)
                brackets.append(dict(angle=row['id'], x=[f'{v:x}' for v in x],
                    below=[f'{v:x}' for v in lo_y], above=[f'{v:x}' for v in next_y]))
                for y in (lo_y, next_y):
                    for scale in (-4096, 0, 4096):
                        pair = exact_scale((*y, *x), scale)
                        if pair is None:
                            counts['unrepresentable_scale_proposals'] += 1
                            continue
                        for orbit in orbits(pair):
                            emit(orbit, 'math-bracket:' + row['kind'])
        for pair, family in solved:
            for scale in (-4096, 0, 4096):
                scaled = exact_scale(pair, scale)
                if scaled:
                    for orbit in orbits(scaled):
                        emit(orbit, family)

        rng = random.Random(SEED + ':raw-bits')
        for index in range(32767):
            ye, xe = index, (13 * index + 1759) % 32767
            ym, xm = rng.getrandbits(63), rng.getrandbits(63)
            ym = (ym | INTEGER_BIT) if ye else max(ym, 1)
            xm = (xm | INTEGER_BIT) if xe else max(xm, 1)
            emit((ye | ((index & 1) << 15), ym,
                  xe | (((index >> 1) & 1) << 15), xm), 'raw-exponent-permutation')
        for index in range(4096):
            ye = rng.randrange(256, 32500)
            xe = ye + rng.randrange(-128, 129)
            ym, xm = INTEGER_BIT | rng.getrandbits(63), INTEGER_BIT | rng.getrandbits(63)
            emit((ye | ((index & 1) << 15), ym,
                  xe | (((index >> 1) & 1) << 15), xm), 'raw-balanced-ratios')
        windows = []
        for index in range(16):
            ye = (0, 1, 16318, 16382, 16383, 16384, 16447, 32766)[index % 8]
            xe = ye if index < 8 else 16383
            ym = rng.randrange(1024, INTEGER_BIT - 1024) if ye == 0 else INTEGER_BIT | rng.getrandbits(62)
            xm = rng.randrange(1024, INTEGER_BIT - 1024) if xe == 0 else INTEGER_BIT | rng.getrandbits(62)
            windows.append(dict(y=[f'{ye:04x}', f'{ym:016x}'],
                                x=[f'{xe:04x}', f'{xm:016x}'], offsets=[-8, 8]))
            for dy in range(-8, 9):
                for dx in range(-8, 9):
                    for orbit in orbits((ye, ym + dy, xe, xm + dx)):
                        emit(orbit, f'exhaustive-window:{index}')
    save(out / 'BRACKETS.json', brackets)
    save(out / 'WINDOWS.json', windows)
    assert counts['unresolved_mathematical_brackets'] == 0
    save(out / 'INPUT-POOL-FROZEN.json', dict(status='MODEL_INDEPENDENT_INPUT_POOL_FROZEN',
        counts=counts, mathematical_brackets=len(brackets),
        smt_results=Counter(r['result'] for r in queries),
        files={p.name: digest(p) for p in out.iterdir() if p.is_file()},
        binary_sha256=digest(binary), sanitized_binary_sha256=digest(sanitized),
        hardware_executed=False, model_loaded=False,
        limits='Finite independent challenge selection, not exhaustive input coverage; SMT outcomes concern only stated mathematical-ratio constraints.'))
    assert not any(name in sys.modules for name in ('model', 'architecture', 'graph_v7'))
    print('FROZEN', json.dumps(counts), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--sanitized', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=BASE / 'd0065-independent-inputs')
    args = parser.parse_args()
    construct(args.binary, args.sanitized, args.out)


if __name__ == '__main__':
    main()
