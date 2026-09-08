"""Sound affine enclosures for exact tie/carry searches on bounded U boxes.

This is a QF_LIA relaxation, not a replacement numerical model. Products of
varying integers use a proved interval remainder. An UNSAT box excludes a
changed correction in that box; SAT requires exact dyadic/Fraction replay.
Neither result identifies silicon's tie rule without endpoint evidence.
"""
import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
import time

from compressed_guard import digest
import d0031_internal_rounding_coverage as audit
from d0045_tie_observability import target_and_correction
from d0049_algebraic_tie_preimages import ROM, graph as exact_graph, fraction
from prepare import save


@dataclass
class Interval:
    value: object
    step: int
    low: int
    high: int


def rounded_integer(n, shift, nearest=False, opposite=False):
    sign = -1 if n < 0 else 1
    magnitude = abs(n)
    if shift <= 0:
        assert not opposite
        return n << (-shift)
    whole, remainder = divmod(magnitude, 1 << shift)
    half = 1 << (shift - 1)
    increment = nearest and (remainder > half or (remainder == half and whole & 1))
    if opposite:
        assert nearest and remainder == half
        increment = not (whole & 1)
    return sign * (whole + increment)


class AffineGraph:
    def __init__(self, z3, solver):
        self.z3, self.solver = z3, solver
        self.serial = 0
        self.products = []
        self.targets = []

    def variable(self, label):
        self.serial += 1
        return self.z3.Int(f'{label}_{self.serial}')

    def constant(self, index):
        n, step = ROM[index]
        return Interval(self.z3.IntVal(n), step, n, n)

    def add(self, a, b):
        step = min(a.step, b.step)
        ka, kb = 1 << (a.step - step), 1 << (b.step - step)
        return Interval(ka * a.value + kb * b.value, step,
                        ka * a.low + kb * b.low, ka * a.high + kb * b.high)

    def multiply(self, a, b):
        corners = [x * y for x in (a.low, a.high) for y in (b.low, b.high)]
        if a.low == a.high:
            value = a.low * b.value
        elif b.low == b.high:
            value = b.low * a.value
        else:
            # ab = a0*b + b0*a - a0*b0 + (a-a0)(b-b0).
            # Both offsets are nonnegative even when a0 or b0 is negative.
            value = self.variable('product')
            linear = a.low * b.value + b.low * a.value - a.low * b.low
            error = (a.high - a.low) * (b.high - b.low)
            self.solver.add(value >= linear, value <= linear + error)
            self.products.append(dict(name=str(value), remainder_bound=error))
        self.solver.add(value >= min(corners), value <= max(corners))
        return Interval(value, a.step + b.step, min(corners), max(corners))

    def round(self, a, bits=67, nearest=False, target=False, opposite=False):
        assert a.low > 0 or a.high < 0, 'box crosses zero; split it'
        sign = 1 if a.low > 0 else -1
        low, high = sorted((abs(a.low), abs(a.high)))
        assert low.bit_length() == high.bit_length(), 'box crosses a binade; split it'
        shift = high.bit_length() - bits
        scale = a.step + shift
        if shift <= 0:
            assert not target
            return Interval(a.value * (1 << (-shift)), scale,
                            a.low << (-shift), a.high << (-shift))
        magnitude = sign * a.value
        whole, remainder = self.variable('quotient'), self.variable('remainder')
        denominator, half = 1 << shift, 1 << (shift - 1)
        self.solver.add(magnitude == denominator * whole + remainder,
                        remainder >= 0, remainder < denominator)
        increment = self.z3.BoolVal(False)
        if nearest:
            increment = self.z3.Or(remainder > half,
                self.z3.And(remainder == half, whole % 2 == 1))
        if target:
            assert nearest
            self.solver.add(remainder == half)
            self.targets.append((a, whole))
            if opposite:
                increment = whole % 2 == 0
        value = sign * (whole + self.z3.If(increment, 1, 0))
        # A one-unit padding encloses either target tie decision. It is not
        # an extra allowed rounding choice in the equality above.
        lo = rounded_integer(a.low, shift, nearest)
        hi = rounded_integer(a.high, shift, nearest)
        padding = 1 if target else 0
        self.solver.add(value >= lo - padding, value <= hi + padding)
        return Interval(value, scale, lo - padding, hi + padding)

    def correction(self, u, node, opposite):
        c = self.constant
        product = lambda a, b: self.round(self.multiply(a, b))
        rn = lambda a, hit=False: self.round(a, 64, True, hit, opposite and hit)
        fourth = product(u, u)
        if node == 2:
            even = self.round(self.add(c(114), product(fourth, c(116))))
            odd = rn(self.add(c(115), product(fourth, c(117))), True)
        else:
            inner_odd = rn(self.add(c(121), product(fourth, c(123))), node == 0)
            inner_even = rn(self.add(c(120), product(fourth, c(122))), node == 1)
            odd = self.round(self.add(c(119), product(fourth, inner_odd)))
            even = self.round(self.add(c(118), product(fourth, inner_even)))
        return rn(self.add(product(u, odd), even))


def build(z3, node, exponent, low, high, timeout):
    solver = z3.SolverFor('QF_LIA')
    solver.set(timeout=timeout)
    builder = AffineGraph(z3, solver)
    variable = z3.Int('u_significand')
    solver.add(variable >= low, variable <= high)
    u = Interval(variable, exponent - 63, low, high)
    baseline = builder.correction(u, node, False)
    alternative = builder.correction(u, node, True)
    assert baseline.step == alternative.step
    solver.add(baseline.value != alternative.value)
    return solver, variable, builder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node', type=int, choices=(0, 1, 2), required=True)
    parser.add_argument('--center', type=lambda x: int(x, 16), required=True)
    parser.add_argument('--radius-bits', type=int, required=True)
    parser.add_argument('--exponent', type=int, required=True)
    parser.add_argument('--timeout-ms', type=int, default=30000)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert 0 <= args.radius_bits <= 60
    sys.path.insert(0, '/private/tmp/fsincos-smt-deps')
    import z3
    radius = (1 << args.radius_bits) - 1
    low = max(1 << 63, args.center - radius)
    high = min(9 << 60 if args.exponent == -9 else (1 << 64) - 1,
               args.center + radius)
    assert low <= high
    args.out.mkdir(exist_ok=False)
    source = Path(__file__).resolve()
    pins = {str(p): digest(p) for p in (source, source.with_name('d0049_algebraic_tie_preimages.py'),
        source.with_name('d0045_tie_observability.py'), source.with_name('PSEUDOCODE.md'),
        source.with_name('fpatan_candidate.c'))}
    solver, variable, builder = build(z3, args.node, args.exponent, low, high, args.timeout_ms)
    query = args.out / 'query.smt2'
    with query.open('x') as stream:
        stream.write(solver.to_smt2())
    save(args.out / 'STARTED.json', dict(status='BOUNDED_AFFINE_RELAXATION',
        node=args.node, exponent=args.exponent, low=f'{low:016x}', high=f'{high:016x}',
        source_sha256=pins, query_sha256=digest(query), timeout_ms=args.timeout_ms,
        hardware_executed=False))
    started = time.monotonic()
    answer = solver.check()
    report = dict(status='BOUNDED_AFFINE_RELAXATION_RESULT', result=str(answer),
        node=args.node, exponent=args.exponent, low=f'{low:016x}', high=f'{high:016x}',
        elapsed_seconds=time.monotonic() - started, timeout_ms=args.timeout_ms,
        query_sha256=digest(query), source_sha256=pins, solver='Z3 ' + z3.get_version_string(),
        product_enclosures=builder.products, hardware_executed=False,
        numerical_model_changed=False, goal_complete=False,
        limits='Sound interval relaxation restricted to the explicit U box. UNSAT excludes a changed correction only in that box. Relaxed SAT is not an exact witness or a hardware tie identification.')
    if answer == z3.sat:
        um = solver.model().eval(variable).as_long()
        t, h, _ = exact_graph(args.node, (um, args.exponent - 63))
        event = audit.event(fraction(t), 64)
        exact = event['relation'] == 'tie'
        report.update(u_significand=f'{um:016x}', exact_target_tie=exact)
        if exact:
            _, other, _ = exact_graph(args.node, (um, args.exponent - 63), True)
            target, fh = target_and_correction(args.node, um * audit.two(args.exponent - 63))
            _, fo = target_and_correction(args.node, um * audit.two(args.exponent - 63), True)
            assert (fraction(t), fraction(h), fraction(other)) == (target, fh, fo)
            report.update(exact_changed_H=h != other, parity=event['parity'],
                          independent_fraction_replay='PASS')
    elif answer == z3.unknown:
        report['reason_unknown'] = solver.reason_unknown()
    assert all(digest(Path(p)) == sha for p, sha in pins.items())
    save(args.out / 'REPORT.json', report)
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
