"""Extract a rational infeasibility certificate for the continuous relaxation.

The final certificate is a nonnegative weighted sum of necessary inequalities
whose variable coefficients cancel and whose right side is negative. Its
verification needs only rational arithmetic, not an SMT solver. Each input
constraint and coefficient bound is retained, with its provenance.
"""
import argparse
import functools
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time
import z3
from d0010_causal_intervals import BASE
from d0014_coefficient_relaxation import real
from model import F, ROM, exponent, pow2
from prepare import save


def normalize(coefficients, bound):
    denominator = math.lcm(bound.denominator, *(v.denominator for v in coefficients))
    integers = [int(v * denominator) for v in coefficients] + [int(bound * denominator)]
    gcd = functools.reduce(math.gcd, integers)
    assert gcd > 0
    return [v // gcd for v in integers[:-1]], integers[-1] // gcd


def inequalities(report):
    rows = []
    for point in report['constraints']:
        weights = {int(k): F(v) for k, v in point['unrounded_polynomial_weights'].items()}
        constant = sum(weights[k] * ROM[k] for k in range(118, 124))
        coefficients = [weights[k] * pow2(exponent(ROM[k]) - 68) for k in range(118, 124)]
        for direction in ('lower', 'upper'):
            a, b = (coefficients, F(point['polynomial_hi']) - constant) if direction == 'upper' else (
                [-v for v in coefficients], constant - F(point['polynomial_lo']))
            a, b = normalize(a, b)
            rows.append(dict(name=f"point_{point['index']}_{direction}", coefficients=a, bound=b,
                             kind='observation', direction=direction, point=point))
    for k in range(118, 124):
        for sign in (-1, 1):
            coefficients = [0] * 6
            coefficients[k - 118] = sign
            rows.append(dict(name=f'coefficient_{k}_{sign}', coefficients=coefficients,
                             bound=report['bound_in_69bit_grid_ULPs'], kind='coefficient_bound',
                             coefficient=k, sign=sign))
    return rows


def fraction(expr):
    assert z3.is_rational_value(expr)
    return F(expr.numerator_as_long(), expr.denominator_as_long())


def worker(path, timeout):
    report = json.loads(path.read_text())
    rows = inequalities(report)
    variables = [z3.Real(f'delta_{k}') for k in range(118, 124)]
    solver = z3.SolverFor('QF_LRA')
    solver.set(timeout=timeout)
    for row in rows:
        condition = sum(a * v for a, v in zip(row['coefficients'], variables)) <= row['bound']
        solver.assert_and_track(condition, row['name'])
    result = solver.check()
    if result != z3.unsat:
        print(json.dumps(dict(result=str(result), reason=solver.reason_unknown())), flush=True)
        return
    names = {str(name) for name in solver.unsat_core()}
    core = [row for row in rows if row['name'] in names]
    # Solve the dual only to discover weights. The output is checked by
    # exact Fraction summation here and by the independent verifier later.
    dual = z3.SolverFor('QF_LRA')
    dual.set(timeout=timeout)
    weights = [z3.Real(f'weight_{i}') for i in range(len(core))]
    dual.add(*(w >= 0 for w in weights))
    for k in range(6):
        dual.add(sum(w * row['coefficients'][k] for w, row in zip(weights, core)) == 0)
    dual.add(sum(w * row['bound'] for w, row in zip(weights, core)) == -1)
    answer = dual.check()
    if answer != z3.sat:
        print(json.dumps(dict(result='unknown', reason='dual certificate ' + str(answer))), flush=True)
        return
    model = dual.model()
    active = []
    for weight, row in zip(weights, core):
        w = fraction(model.eval(weight))
        assert w >= 0
        if w:
            active.append(dict(**row, weight=str(w)))
    sums = [sum(F(row['weight']) * row['coefficients'][k] for row in active) for k in range(6)]
    right = sum(F(row['weight']) * row['bound'] for row in active)
    assert all(v == 0 for v in sums) and right == -1
    print(json.dumps(dict(result='unsat', status='EXACT_NONNEGATIVE_LINEAR_COMBINATION',
                          core_constraints=len(core), active_constraints=len(active),
                          coefficient_order=list(range(118, 124)), inequalities=active,
                          weighted_variable_coefficients=[str(v) for v in sums], weighted_bound=str(right),
                          conclusion='Necessary inequalities imply 0 <= -1.')), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('relaxation', type=Path)
    ap.add_argument('--out', type=Path)
    ap.add_argument('--timeout-ms', type=int, default=60000)
    ap.add_argument('--worker', action='store_true')
    args = ap.parse_args()
    if args.worker:
        worker(args.relaxation, args.timeout_ms)
        return
    assert args.out and not args.out.exists()
    start = time.monotonic()
    content = args.relaxation.read_bytes()
    child = subprocess.Popen([sys.executable, str(Path(__file__)), str(args.relaxation), '--worker',
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
        result = dict(result='unknown', reason='external deadline; child terminated')
    else:
        assert child.returncode == 0, (child.returncode, stdout, stderr)
        result = json.loads(stdout)
    out = dict(status='CONTINUOUS_COEFFICIENT_CERTIFICATE_EXTRACTION', certificate=result,
               relaxation=str(args.relaxation), relaxation_sha256=hashlib.sha256(content).hexdigest(),
               coefficient_centers={k: str(ROM[k]) for k in range(118, 124)},
               coefficient_units={k: str(pow2(exponent(ROM[k]) - 68)) for k in range(118, 124)},
               external_deadline=deadline, worker_returncode=child.returncode, worker_stderr=stderr,
               elapsed_seconds=time.monotonic() - start, hardware_executed=False)
    save(args.out, out)
    print(result.get('status', result['result']), 'active inequalities', result.get('active_constraints'), flush=True)


if __name__ == '__main__':
    main()
