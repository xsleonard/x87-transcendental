"""Shared-coefficient relaxation for wider Horner/terminal representations.

D0014 excludes a particular MR-square/h64 graph, not every ROM bank for
other graphs. Here the square is CHOP67(z*z), Horner products are CHOP67,
and Horner adds are RN at the terminal carrier width (64, 67 or 69). Test
every D0011 terminal recipe admitting any carrier on that width's lattice.
Coefficients are six global real values, never operand-indexed choices.
Every query is frozen and externally bounded. Relaxation SAT is not closure.
"""
import argparse
import functools
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import z3
from d0010_causal_intervals import BASE
from d0011_terminal_preimage import Recipe, solve, tail
from d0014_integer_coefficient_solve import data_points
from model import F, ROM, cut, exponent, pow2
from prepare import save


def real(v):
    v = F(v)
    return z3.RealVal(f'{v.numerator}/{v.denominator}')


@functools.lru_cache(maxsize=None)
def envelope(z, hbits, bound_bits, square_read='exact'):
    units = {k: pow2(exponent(ROM[k]) - 68) for k in range(118, 124)}
    bound = 1 << bound_bits
    u = cut(cut(z * z, 'chop67'), square_read)
    lo, hi = ROM[123] - bound * units[123], ROM[123] + bound * units[123]
    elo = ehi = F(0)
    weights = {123: F(1)}
    for k in range(122, 117, -1):
        lo *= u
        hi *= u
        assert lo * hi > 0
        step = pow2(max(exponent(lo), exponent(hi)) - 66)
        elo *= u
        ehi *= u
        if lo > 0:
            elo -= step
        else:
            ehi += step
        lo, hi = cut(lo, 'chop67'), cut(hi, 'chop67')
        lo += ROM[k] - bound * units[k]
        hi += ROM[k] + bound * units[k]
        assert lo * hi > 0
        step = pow2(max(exponent(lo), exponent(hi)) - hbits + 1)
        elo -= step / 2
        ehi += step / 2
        lo, hi = cut(lo, 'rn' + str(hbits)), cut(hi, 'rn' + str(hbits))
        weights = {j: w * u for j, w in weights.items()}
        weights[k] = F(1)
    return u, weights, elo, ehi, units


def concrete(z, recipe, coefficients, square_read='exact'):
    u = cut(z * z, 'chop67')
    uh = cut(u, square_read)
    h = coefficients[123]
    for k in range(122, 117, -1):
        h = cut(coefficients[k] + cut(uh * h, 'chop67'), 'rn' + str(recipe.h_bits))
    return z + tail(z, h, recipe, u)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bound-bits', type=int, default=60)
    ap.add_argument('--timeout-ms', type=int, default=3000)
    ap.add_argument('--tag', required=True)
    ap.add_argument('--horner-square-read', choices=('exact', 'chop64', 'rn64'), default='exact')
    args = ap.parse_args()
    assert 0 <= args.bound_bits <= 60
    assert args.tag and all(c.isalnum() or c == '-' for c in args.tag)
    dest = BASE / f'd0016-wide-coefficient-family-{args.tag}'
    dest.mkdir(exist_ok=False)
    historical = json.loads((BASE / 'd0011-terminal-preimage-expanded.json').read_text())
    recipes = [Recipe(**r['recipe']) for r in historical['reports'] if r['impossible'] == 0]
    data = data_points()
    results = []
    started = time.monotonic()
    for number, recipe in enumerate(recipes):
        solver = z3.SolverFor('QF_LRA')
        variables = {k: z3.Real(f'coefficient_delta_{k}') for k in range(118, 124)}
        for d in variables.values():
            solver.add(d >= -(1 << args.bound_bits), d <= 1 << args.bound_bits)
        constraints = []
        for pair, t, band in data:
            z = t['z']
            uh, weights, elo, ehi, units = envelope(z, recipe.h_bits, args.bound_bits, args.horner_square_read)
            u = cut(z * z, 'chop67')
            inverse = solve(z, band, recipe, u)
            assert inverse['feasible']
            hlo, hhi = -F(inverse['h_last']), -F(inverse['h_first'])
            polynomial = sum(real(w) * (real(ROM[k]) + real(units[k]) * variables[k]) for k, w in weights.items())
            solver.add(polynomial >= real(hlo - ehi), polynomial <= real(hhi - elo))
            constraints.append(dict(input=pair['rows'][0]['input'], z=str(z), u=str(u), horner_u=str(uh),
                                    h_lo=str(hlo), h_hi=str(hhi), error_lo=str(elo), error_hi=str(ehi)))
        stem = dest / f't{number:03d}'
        query = solver.to_smt2()
        with stem.with_suffix('.smt2').open('x') as f:
            f.write(query)
        child = subprocess.Popen([sys.executable, str(Path(__file__).with_name('d0014_coefficient_relaxation.py')),
                                  '--tag', args.tag, '--worker-query', str(stem.with_suffix('.smt2')),
                                  '--timeout-ms', str(args.timeout_ms)],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        deadline = False
        query_started = time.monotonic()
        try:
            stdout, stderr = child.communicate(timeout=args.timeout_ms / 1000 + 2)
        except subprocess.TimeoutExpired:
            deadline = True
            child.terminate()
            stdout, stderr = child.communicate(timeout=10)
        if deadline:
            result = dict(result='unknown', reason_unknown='external deadline; child terminated')
        else:
            assert child.returncode == 0, (child.returncode, stdout, stderr)
            result = json.loads(stdout)
        replays = []
        if result['result'] == 'sat':
            coefficients = {k: ROM[k] + F(result['relaxed_offsets'][str(k)]) * units[k] for k in units}
            for fmt in ('rn67', 'rn69'):
                bank = {k: cut(v, fmt) for k, v in coefficients.items()}
                misses = [pair['rows'][0]['input'] for pair, t, band in data
                          if not band.contains(concrete(t['z'], recipe, bank, args.horner_square_read))]
                replays.append(dict(format=fmt, coefficients={k: str(v) for k, v in bank.items()},
                                    failed_groups=len(misses), failing_inputs=misses))
        report = dict(status='SHARED_COEFFICIENT_RELAXATION_' + result['result'].upper(),
                      recipe=vars(recipe), result=result, rounded_constant_bank_replays=replays,
                      coefficient_half_width_in_69bit_ULPs=1 << args.bound_bits, constraints=constraints,
                      graph='square CHOP67(z*z); Horner multiply CHOP67; Horner add RN(h_bits)',
                      horner_square_read=args.horner_square_read,
                      query_sha256=hashlib.sha256(query.encode()).hexdigest(),
                      source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      external_deadline=deadline, worker_returncode=child.returncode, worker_stderr=stderr,
                      elapsed_seconds=time.monotonic() - query_started, hardware_executed=False)
        save(stem.with_suffix('.json'), report)
        results.append(dict(index=number, recipe=vars(recipe), result=result['result'],
                            concrete_misses=[r['failed_groups'] for r in replays]))
        print(number + 1, '/', len(recipes), recipe.name, result['result'], results[-1]['concrete_misses'], flush=True)
    counts = {status: sum(r['result'] == status for r in results) for status in ('sat', 'unsat', 'unknown')}
    save(dest / 'SUMMARY.json', dict(status='WIDE_ACCUMULATOR_SHARED_COEFFICIENT_FAMILY', counts=counts,
         programs=len(results), groups=len(data), results=results, elapsed_seconds=time.monotonic() - started,
         horner_square_read=args.horner_square_read,
         hardware_executed=False, numerical_model_promoted=False))
    print('COMPLETE', counts, flush=True)


if __name__ == '__main__':
    main()
