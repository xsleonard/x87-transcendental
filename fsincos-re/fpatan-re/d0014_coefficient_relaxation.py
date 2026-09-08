"""Necessary continuous-coefficient constraints for the fixed MR Horner graph.

Every quantization is replaced by a closed interval containing its error.
Errors may vary independently at every operation/input. Coefficients may be
arbitrary reals within the stated box, not just ROM-grid values. This is a
strict relaxation, so UNSAT excludes the exact graph in that coefficient
box. SAT proves only that this loose necessary condition is insufficient.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
import z3
from d0010_causal_intervals import BASE
from d0014_integer_coefficient_solve import Graph, data_points
from d0011_terminal_preimage import Recipe, solve
from model import F, ROM, cut, exponent, pow2
from prepare import save


def real(v):
    v = F(v)
    return z3.RealVal(f'{v.numerator}/{v.denominator}')


def wide_envelope(data, bound_bits):
    """Safe error bounds even when a product's coefficient box crosses a binade.

    Use the largest input ULP in the interval, and propagate monotonically
    rounded endpoint bounds. No fixed-significand-lattice assertion is made.
    """
    graph = SimpleNamespace(data=data, bound=1 << bound_bits, nodes=[], targets=[])
    graph.units = {k: pow2(exponent(ROM[k]) - 68) for k in range(118, 124)}
    coefficient = lambda k: (ROM[k] - graph.bound * graph.units[k], ROM[k] + graph.bound * graph.units[k])
    for i, (_, t, band) in enumerate(data):
        z = t['z']
        u = cut(z * cut(z, 'chop64'), 'rn64')
        target = solve(z, band, Recipe('MR-cubic', z_read='exact', order='square-z-h'), u)
        assert target['feasible']
        graph.targets.append(dict(z=str(z), h118_lo=str(-F(target['h_last'])), h118_hi=str(-F(target['h_first']))))
        lo, hi = coefficient(123)
        for k in range(122, 117, -1):
            lo *= u
            hi *= u
            assert lo * hi > 0
            graph.nodes.append(dict(name=f'p{i}_m{k}', sign=1 if lo > 0 else -1,
                                    step=pow2(max(exponent(lo), exponent(hi)) - 66)))
            lo, hi = cut(lo, 'chop67'), cut(hi, 'chop67')
            a, b = coefficient(k)
            lo += a
            hi += b
            assert lo * hi > 0
            graph.nodes.append(dict(name=f'p{i}_h{k}', sign=1 if lo > 0 else -1,
                                    step=pow2(max(exponent(lo), exponent(hi)) - 63)))
            lo, hi = cut(lo, 'rn64'), cut(hi, 'rn64')
    return graph


def constraints(graph):
    offsets = {k: z3.Real(f'coefficient_delta_{k}') for k in graph.units}
    limits = [condition for d in offsets.values() for condition in (d >= -graph.bound, d <= graph.bound)]
    by_name = {node['name']: node for node in graph.nodes}
    conditions = []
    evidence = []
    for i, (pair, t, _) in enumerate(graph.data):
        z = t['z']
        u = cut(z * cut(z, 'chop64'), 'rn64')
        h = real(ROM[123]) + real(graph.units[123]) * offsets[123]
        error_lo = error_hi = F(0)
        terms = {123: F(1)}
        for k in range(122, 117, -1):
            mul = by_name[f'p{i}_m{k}']
            add = by_name[f'p{i}_h{k}']
            # CHOP moves toward zero; close the strict error endpoint to
            # enlarge the feasible set. RN-even is enclosed by +/- half ULP.
            error_lo *= u
            error_hi *= u
            if mul['sign'] > 0:
                error_lo -= mul['step']
            else:
                error_hi += mul['step']
            error_lo -= add['step'] / 2
            error_hi += add['step'] / 2
            h = real(ROM[k]) + real(graph.units[k]) * offsets[k] + real(u) * h
            terms = {j: a * u for j, a in terms.items()}
            terms[k] = F(1)
        target = graph.targets[i]
        required_lo = F(target['h118_lo']) - error_hi
        required_hi = F(target['h118_hi']) - error_lo
        conditions.append(z3.And(h >= real(required_lo), h <= real(required_hi)))
        evidence.append(dict(index=i, input=pair['rows'][0]['input'], z=str(z), u=str(u),
                             unrounded_polynomial_weights={k: str(v) for k, v in terms.items()},
                             accumulated_error_lo=str(error_lo), accumulated_error_hi=str(error_hi),
                             h118_target=target, polynomial_lo=str(required_lo), polynomial_hi=str(required_hi)))
    return limits, conditions, evidence


def solve_worker(query, timeout):
    solver = z3.SolverFor('QF_LRA')
    solver.set(timeout=timeout)
    solver.from_file(str(query))
    result = solver.check()
    answer = dict(result=str(result), reason_unknown=solver.reason_unknown() if result == z3.unknown else None)
    if result == z3.sat:
        model = solver.model()
        answer['relaxed_offsets'] = {k: str(model.eval(z3.Real(f'coefficient_delta_{k}'), model_completion=True))
                                     for k in range(118, 124)}
        answer['warning'] = 'Necessary error-envelope feasibility only; not a concrete numerical candidate.'
    print(json.dumps(answer), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bound-bits', type=int, default=28)
    ap.add_argument('--timeout-ms', type=int, default=60000)
    ap.add_argument('--tag', required=True)
    ap.add_argument('--worker-query', type=Path)
    ap.add_argument('--wide-binades', action='store_true')
    args = ap.parse_args()
    if args.worker_query:
        solve_worker(args.worker_query, args.timeout_ms)
        return
    assert 0 <= args.bound_bits <= 60
    assert args.tag and all(c.isalnum() or c == '-' for c in args.tag)
    stem = BASE / f'd0014-continuous-coefficients-{args.tag}'
    assert not stem.with_suffix('.smt2').exists() and not stem.with_suffix('.json').exists()
    start = time.monotonic()
    graph = (wide_envelope(data_points(), args.bound_bits) if args.wide_binades
             else Graph(data_points(), args.bound_bits))
    limits, conditions, evidence = constraints(graph)
    solver = z3.SolverFor('QF_LRA')
    solver.add(*limits, *conditions)
    query = solver.to_smt2()
    with stem.with_suffix('.smt2').open('x') as f:
        f.write(query)
    print('SOLVING continuous relaxation;', len(conditions), 'points;', len(query), 'bytes', flush=True)
    child = subprocess.Popen([sys.executable, str(Path(__file__)), '--tag', args.tag,
                              '--worker-query', str(stem.with_suffix('.smt2')),
                              '--timeout-ms', str(args.timeout_ms)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    deadline = False
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
    save(stem.with_suffix('.json'), dict(status='CONTINUOUS_COEFFICIENT_RELAXATION_' + result['result'].upper(),
         graph='MR64 asymmetric square; cube-first CHOP67 tail; CHOP67 Horner products and RN64 adds',
         result=result, coefficient_grid='None: continuous real coefficients',
         bound_in_69bit_grid_ULPs=graph.bound, constraints=evidence, groups=len(conditions),
         wide_binade_error_envelope=args.wide_binades,
         quantization_errors='Independent closed intervals, including unattainable errors',
         query_sha256=hashlib.sha256(query.encode()).hexdigest(),
         source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
         external_deadline=deadline, worker_returncode=child.returncode, worker_stderr=stderr,
         elapsed_seconds=time.monotonic()-start, hardware_executed=False))
    print('COMPLETE', result, flush=True)


if __name__ == '__main__':
    main()
