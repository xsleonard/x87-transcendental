"""Centered, integer-only solve for six globally shared FPATAN coefficients.

This is the same fixed MR-square/cubic-first graph as D0012. The final
product is eliminated by its exact inverse, and retained significands are
represented as small differences from the public-P5 trace. All inequalities
use integers: there are no Real variables, nonlinear products or per-input
coefficient choices. SAT still requires concrete forward replay. This is an
analysis query, not a replacement numerical algorithm or a hardware capture.
"""
import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time
import z3
from d0010_causal_intervals import BASE, observation_interval
from d0011_terminal_preimage import Recipe, solve
from d0011_verify_role_certificate import rounded
from graph_v5 import prevalue
from model import F, ROM, cut, exponent, pow2
from prepare import save


@dataclass
class Linear:
    constant: F
    terms: dict

    def plus(self, other):
        terms = dict(self.terms)
        for name, coefficient in other.terms.items():
            terms[name] = terms.get(name, F(0)) + coefficient
        return Linear(self.constant + other.constant, {k: v for k, v in terms.items() if v})

    def scale(self, factor):
        return Linear(self.constant * factor, {k: v * factor for k, v in self.terms.items()})

    def bounds(self, limits):
        lo = hi = self.constant
        for name, coefficient in self.terms.items():
            a, b = limits[name]
            lo += coefficient * (a if coefficient > 0 else b)
            hi += coefficient * (b if coefficient > 0 else a)
        return lo, hi

    def integer_numerator(self):
        denominator = math.lcm(self.constant.denominator, *(v.denominator for v in self.terms.values()))
        expr = z3.IntVal(int(self.constant * denominator))
        for name, coefficient in self.terms.items():
            expr += int(coefficient * denominator) * z3.Int(name)
        return expr, denominator


def data_points():
    data = []
    seen = set()
    for pair in json.loads((BASE / 'd0009-kernel-frontier.json').read_text())['pairs']:
        t = {}
        prevalue(*pair['raw'], trace=t)
        if t['kind'] != 'direct' or t['swap'] or pair['raw'][2] & 32768:
            continue
        band = observation_interval(pair['rows'])
        key = t['z'], band
        if key in seen:
            continue
        seen.add(key)
        data.append((pair, t, band))
    data.sort(key=lambda p: p[2].lo != p[2].hi)
    return data


def concrete(z, coefficients):
    # Independent integer rounder, not the symbolic quantizer.
    u = rounded(z * rounded(z, 'chop64'), 'rn64')
    cube = rounded(z * u, 'chop67')
    h = coefficients[123]
    nodes = {}
    for k in range(122, 117, -1):
        p = rounded(u * h, 'chop67')
        h = rounded(coefficients[k] + p, 'rn64')
        nodes[f'm{k}'] = p
        nodes[f'h{k}'] = h
    return z + rounded(cube * h, 'chop67'), nodes


class Graph:
    def __init__(self, data, bound_bits, coefficient_bits=69):
        self.solver = z3.SolverFor('QF_LIA')
        self.data = data
        self.limits = {}
        self.nodes = []
        self.targets = []
        self.endpoint_conditions = []
        self.bound = 1 << bound_bits
        self.units = {k: pow2(exponent(ROM[k]) - coefficient_bits + 1) for k in range(118, 124)}
        for k in self.units:
            self.variable(f'delta_{k}', -self.bound, self.bound)
        for index, (_, t, band) in enumerate(data):
            self.point(index, t['z'], band)

    def variable(self, name, lo, hi):
        assert isinstance(lo, int) and isinstance(hi, int) and lo <= hi
        self.limits[name] = lo, hi
        q = z3.Int(name)
        self.solver.add(q >= lo, q <= hi)
        return q

    def coefficient(self, k):
        return Linear(ROM[k], {f'delta_{k}': self.units[k]})

    def quantize(self, expr, bits, mode, name):
        lo, hi = expr.bounds(self.limits)
        assert lo * hi > 0 and exponent(lo) == exponent(hi), (name, lo, hi)
        sign = 1 if lo > 0 else -1
        step = pow2(exponent(lo) - bits + 1)
        base = cut(expr.constant, mode + str(bits))
        q0 = abs(base) / step
        assert q0.denominator == 1
        q0 = int(q0)
        bounds = sorted(abs(cut(v, mode + str(bits))) / step for v in (lo, hi))
        assert all(v.denominator == 1 for v in bounds)
        q = self.variable(name, int(bounds[0]) - q0, int(bounds[1]) - q0)
        centered = expr.scale(sign / step).plus(Linear(F(-q0), {}))
        numerator, denominator = centered.integer_numerator()
        if mode == 'chop':
            self.solver.add(q * denominator <= numerator, numerator < (q + 1) * denominator)
        else:
            assert mode == 'rn'
            error = 2 * numerator - 2 * q * denominator
            self.solver.add(error >= -denominator, error <= denominator,
                            z3.Or((q + q0) % 2 == 0,
                                  z3.And(error > -denominator, error < denominator)))
        self.nodes.append(dict(name=name, base=base, step=step, sign=sign, bits=bits, mode=mode))
        return Linear(base, {name: sign * step})

    def point(self, index, z, band):
        u = cut(z * cut(z, 'chop64'), 'rn64')
        answer = solve(z, band, Recipe('MR-cubic', z_read='exact', order='square-z-h'), u)
        assert answer['feasible']
        # solve() returns positive magnitudes for the negative h118 carrier.
        hlo, hhi = -F(answer['h_last']), -F(answer['h_first'])
        h = self.coefficient(123)
        for k in range(122, 117, -1):
            p = self.quantize(h.scale(u), 67, 'chop', f'p{index}_m{k}')
            h = self.quantize(self.coefficient(k).plus(p), 64, 'rn', f'p{index}_h{k}')
        low, lowden = h.plus(Linear(-hlo, {})).integer_numerator()
        high, highden = h.plus(Linear(-hhi, {})).integer_numerator()
        assert lowden > 0 and highden > 0
        self.endpoint_conditions.append(z3.And(low >= 0, high <= 0))
        self.targets.append(dict(z=str(z), h118_lo=str(hlo), h118_hi=str(hhi)))

    def check_assignment(self, offsets):
        coefficients = {k: ROM[k] + offsets[k] * self.units[k] for k in self.units}
        bindings = [(z3.Int(f'delta_{k}'), z3.IntVal(d)) for k, d in offsets.items()]
        values = {}
        failed = 0
        for index, (_, t, band) in enumerate(self.data):
            endpoint, nodes = concrete(t['z'], coefficients)
            failed += not band.contains(endpoint)
            target = self.targets[index]
            assert band.contains(endpoint) == (F(target['h118_lo']) <= nodes['h118'] <= F(target['h118_hi']))
            values.update({f'p{index}_{name}': value for name, value in nodes.items()})
        for node in self.nodes:
            delta = (values[node['name']] - node['base']) / (node['sign'] * node['step'])
            assert delta.denominator == 1
            bindings.append((z3.Int(node['name']), z3.IntVal(int(delta))))
        assigned = z3.simplify(z3.substitute(z3.And(*self.solver.assertions()), *bindings))
        assert z3.is_true(assigned), 'Independent concrete trace violates integer encoding'
        return failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bound-bits', type=int, default=8)
    ap.add_argument('--timeout-ms', type=int, default=60000)
    ap.add_argument('--tag', required=True)
    args = ap.parse_args()
    assert 0 <= args.bound_bits <= 40 and 0 < args.timeout_ms <= 300000
    assert args.tag and all(c.isalnum() or c == '-' for c in args.tag)
    stem = BASE / f'd0014-integer-coefficients-{args.tag}'
    assert not stem.with_suffix('.smt2').exists() and not stem.with_suffix('.json').exists()
    started = time.monotonic()
    data = data_points()
    g = Graph(data, args.bound_bits)
    calibration = []
    for name, offsets in (
        ('P5', {k: 0 for k in range(118, 124)}),
        ('positive-bound', {k: g.bound for k in range(118, 124)}),
        ('negative-bound', {k: -g.bound for k in range(118, 124)}),
        ('alternating-bound', {k: (-1 if k % 2 else 1) * g.bound for k in range(118, 124)}),
    ):
        failures = g.check_assignment(offsets)
        calibration.append(dict(name=name, exact_assignment='PASS', endpoint_misses=failures))
        print('CALIBRATION', name, failures, 'endpoint misses', flush=True)
    for condition in g.endpoint_conditions:
        g.solver.add(condition)
    query = g.solver.to_smt2()
    assert 'Real' not in query
    with stem.with_suffix('.smt2').open('x') as f:
        f.write(query)
    print('SOLVING', len(data), 'points;', len(g.nodes), 'centered integer nodes;', len(query), 'bytes', flush=True)
    child = subprocess.Popen([sys.executable, str(Path(__file__).with_name('d0012_smt_worker.py')),
                              str(stem.with_suffix('.smt2')), '--timeout-ms', str(args.timeout_ms)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    external_deadline = False
    try:
        stdout, stderr = child.communicate(timeout=args.timeout_ms / 1000 + 2)
    except subprocess.TimeoutExpired:
        external_deadline = True
        child.terminate()
        stdout, stderr = child.communicate(timeout=10)
    if external_deadline:
        result = dict(result='unknown', reason_unknown='external deadline; child terminated')
    else:
        assert child.returncode == 0, (child.returncode, stdout, stderr)
        result = json.loads(stdout)
    candidate = None
    if result['result'] == 'sat':
        offsets = {int(k): d for k, d in result['offsets'].items()}
        coefficients = {k: ROM[k] + offsets[k] * g.units[k] for k in offsets}
        for _, t, band in data:
            assert band.contains(concrete(t['z'], coefficients)[0])
        candidate = dict(offsets=offsets, coefficients={k: str(v) for k, v in coefficients.items()},
                         independent_concrete_replay='PASS', promoted=False)
    report = dict(status='INTEGER_SHARED_COEFFICIENT_QUERY_' + result['result'].upper(),
                  graph='MR64 asymmetric square; cube-first CHOP67 tail; CHOP67 Horner products and RN64 adds',
                  solver=z3.get_version_string(), timeout_ms=args.timeout_ms,
                  reason_unknown=result['reason_unknown'], external_deadline=external_deadline,
                  worker_returncode=child.returncode, worker_stderr=stderr,
                  coefficient_bits=69, offset_bound_in_grid_ULPs=g.bound,
                  grid_units={k: str(v) for k, v in g.units.items()}, groups=len(data),
                  centered_integer_nodes=len(g.nodes), calibration=calibration,
                  query_sha256=hashlib.sha256(query.encode()).hexdigest(),
                  source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  frontier_sha256=hashlib.sha256((BASE / 'd0009-kernel-frontier.json').read_bytes()).hexdigest(),
                  endpoint_preimages=g.targets, candidate=candidate,
                  elapsed_seconds=time.monotonic() - started, hardware_executed=False)
    save(stem.with_suffix('.json'), report)
    print('COMPLETE', result['result'], result['reason_unknown'], flush=True)


if __name__ == '__main__':
    main()
