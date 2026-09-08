"""Exact continued-fraction witnesses for the independent D0065 queries.

Original UNKNOWN solver artifacts remain unchanged. A concrete assignment
that satisfies an original query establishes SAT by witness, regardless of
the original bounded search outcome. No model arithmetic is imported.
"""
from collections import Counter, defaultdict
from fractions import Fraction
import gzip
import json
from pathlib import Path
import sys

from compressed_guard import digest, save
from d0065_independent_inputs import (BASE, BIAS, INTEGER_BIT, decode,
    exact_scale, floor_log2, orbits, parse_bounds, two)


def convergents(value):
    numerator, denominator = value.numerator, value.denominator
    old_p, p, old_q, q = 0, 1, 1, 0
    while denominator:
        quotient, numerator, denominator = (numerator // denominator,
                                             denominator, numerator % denominator)
        old_p, p = p, quotient * p + old_p
        old_q, q = q, quotient * q + old_q
        yield p, q


def construct():
    source = BASE / 'd0065-independent-inputs'
    out = BASE / 'd0068-independent-lattice-v2'
    original_receipt = digest(source / 'INPUT-POOL-FROZEN.json')
    receipt = json.loads((source / 'INPUT-POOL-FROZEN.json').read_text())
    for name, sha in receipt['files'].items():
        assert digest(source / name) == sha
    out.mkdir(exist_ok=False)
    recipe = json.loads((source / 'RECIPE.json').read_text())
    intervals = parse_bounds((source / 'tan-bounds-384.txt').read_text())
    by_target, witnesses = defaultdict(list), []
    for target in recipe['angle_targets']:
        lower, upper = intervals[target['id']]
        exponent = floor_log2(lower)
        assert floor_log2(upper) == exponent
        center = (lower + upper) * two(-exponent) / 2
        for numerator, denominator in convergents(center):
            if max(numerator, denominator) >= 1 << 64:
                break
            scale = (INTEGER_BIT + min(numerator, denominator) - 1) // min(numerator, denominator)
            ym, xm = scale * numerator, scale * denominator
            if max(ym, xm) >= 1 << 64:
                continue
            ratio = Fraction(ym, xm) * two(exponent)
            error_bound = max(abs(ratio - lower), abs(ratio - upper)) * xm * two(-exponent)
            if error_bound > two(-48) or lower < ratio < upper:
                continue
            side = 'below' if ratio <= lower else 'above'
            # A ratio can be smaller than the minimum normal while both
            # operands are normal. Lift their common scale, not their ratio.
            common_scale = max(0, -16382 - exponent)
            pair = exponent + BIAS + common_scale, ym, BIAS + common_scale, xm
            assert INTEGER_BIT <= ym < 1 << 64 and INTEGER_BIT <= xm < 1 << 64
            assert decode(pair[:2]) / decode(pair[2:]) == ratio
            witness = dict(angle=target['id'], side=side,
                pair=[f'{v:x}' for v in pair], exponent=exponent,
                numerator_unit_error_bound=[f'{error_bound.numerator:x}', f'{error_bound.denominator:x}'])
            witnesses.append(witness)
            by_target[target['id'], side].append(pair)
    assert witnesses
    save(out / 'WITNESSES.json', witnesses)

    sys.path.insert(0, '/private/tmp/fsincos-smt-deps')
    import z3
    query_checks = []
    for old in sorted((source / 'smt').glob('*.json')):
        report = json.loads(old.read_text())
        ident, side = report['id'].split('-')
        query = old.with_suffix('.smt2')
        assert digest(query) == report['query_sha256']
        answer = dict(id=report['id'], original_outcome=report['result'],
                      original_query_sha256=digest(query), original_report_sha256=digest(old))
        candidates = by_target[ident, side]
        for pair in candidates:
            lower, upper = intervals[ident]
            factor = two(192 - (pair[0] - pair[2]))
            low, high = lower * factor, upper * factor
            low = low.numerator // low.denominator
            high = -(-high.numerator // high.denominator)
            ym, xm = pair[1], pair[3]
            residual = ((low * xm - (1 << 192) * ym, high * xm - (1 << 192) * ym)
                        if side == 'below' else
                        ((1 << 192) * ym - high * xm, (1 << 192) * ym - low * xm))
            if not 0 <= residual[0] <= residual[1] <= 1 << 144:
                continue
            check = z3.Solver()
            check.set(timeout=2000)
            check.add(z3.parse_smt2_file(str(query)))
            check.add(z3.Int('y_significand') == ym, z3.Int('x_significand') == xm)
            result = check.check()
            answer.update(status='SAT_BY_EXACT_WITNESS', pair=[f'{v:x}' for v in pair],
                          exact_integer_constraints=True, pinned_assignment_solver_result=str(result))
            assert result == z3.sat
            break
        else:
            answer['status'] = 'NO_CONSTRUCTED_WITNESS_NOT_EXCLUSION'
        query_checks.append(answer)
    save(out / 'ORIGINAL-QUERY-WITNESS-CHECKS.json', query_checks)

    counts, seen = Counter(), set()
    with gzip.open(out / 'pair-pool.tsv.gz', 'xt') as target:
        def emit(pair, family):
            if pair in seen:
                counts['duplicate_proposals'] += 1
                return
            seen.add(pair)
            target.write(f'{pair[0]:04x} {pair[1]:016x} {pair[2]:04x} {pair[3]:016x}\t{family}\n')
            counts['pairs'] += 1
            counts['family:' + family.split(':')[0]] += 1
        with gzip.open(source / 'pair-pool.tsv.gz', 'rt') as old_pool:
            for line in old_pool:
                raw, family = line.rstrip().split('\t')
                emit(tuple(int(word, 16) for word in raw.split()), family)
        for witness in witnesses:
            pair = tuple(int(word, 16) for word in witness['pair'])
            for scale in (-4096, 0, 4096):
                scaled = exact_scale(pair, scale)
                if scaled:
                    for orbit in orbits(scaled):
                        emit(orbit, 'lattice-math-boundary:' + witness['side'])
    assert digest(source / 'INPUT-POOL-FROZEN.json') == original_receipt
    assert not any(n in sys.modules for n in ('model', 'architecture', 'graph_v7'))
    save(out / 'INPUT-POOL-FROZEN.json', dict(status='MODEL_INDEPENDENT_INPUT_POOL_FROZEN',
        previous_pool_sha256=original_receipt, source_sha256=digest(Path(__file__)),
        counts=counts, exact_base_witnesses=len(witnesses),
        query_results=Counter(r['status'] for r in query_checks),
        files={p.name: digest(p) for p in out.iterdir() if p.is_file()},
        model_loaded=False, hardware_executed=False,
        limits='Original UNKNOWN reports preserved. Constructive SAT applies only to these mathematical-ratio queries, not a silicon model or absence of errors.'))
    print('FROZEN', json.dumps(counts), 'query checks', Counter(r['status'] for r in query_checks), flush=True)


if __name__ == '__main__':
    construct()
