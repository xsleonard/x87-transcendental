"""Exact, template-scoped bit-vector search for a surviving tie carry.

The input is a relaxed RN64 square, not an external operand. A SAT model
still needs asymmetric-square and raw80 preimages. UNSAT excludes only the
explicit normalization template, never all inputs or all silicon rules.
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
from prepare import save

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'tmp/fpatan-re'


@dataclass
class Word:
    magnitude: object
    sign: int
    step: int
    reference: object


class Graph:
    def __init__(self, z3, solver):
        self.z3, self.solver = z3, solver
        self.records = []

    def remember(self, word):
        self.records.append(word)
        return word

    def widen(self, value, width):
        assert width >= value.size()
        return self.z3.ZeroExt(width - value.size(), value)

    def constant(self, value):
        step = -(value.denominator.bit_length() - 1)
        magnitude = abs(value.numerator)
        return Word(self.z3.BitVecVal(magnitude, magnitude.bit_length()),
                    -1 if value < 0 else 1, step, value)

    def mul(self, a, b):
        width = a.magnitude.size() + b.magnitude.size()
        magnitude = self.widen(a.magnitude, width) * self.widen(b.magnitude, width)
        return self.remember(Word(magnitude, a.sign * b.sign, a.step + b.step,
                                  a.reference * b.reference))

    def add(self, a, b):
        step = min(a.step, b.step)
        da, db = a.step - step, b.step - step
        width = max(a.magnitude.size() + da, b.magnitude.size() + db) + 1
        am = self.widen(a.magnitude, width) << da
        bm = self.widen(b.magnitude, width) << db
        reference = a.reference + b.reference
        assert reference
        sign = -1 if reference < 0 else 1
        if a.sign == b.sign:
            magnitude = am + bm
        elif sign == a.sign:
            self.solver.add(self.z3.UGT(am, bm))
            magnitude = am - bm
        else:
            self.solver.add(self.z3.UGT(bm, am))
            magnitude = bm - am
        return self.remember(Word(magnitude, sign, step, reference))

    def round(self, a, bits=67, nearest=False, target=False, opposite=False):
        z3 = self.z3
        step = audit.exponent(abs(a.reference)) - bits + 1
        shift = step - a.step
        magnitude = a.magnitude
        if shift < 0:
            magnitude = self.widen(magnitude, magnitude.size() - shift) << (-shift)
            shift = 0
        normal_bits = bits + shift
        self.solver.add(z3.UGE(magnitude, 1 << (normal_bits - 1)))
        if normal_bits < magnitude.size():
            self.solver.add(z3.ULT(magnitude, 1 << normal_bits))
        quotient = z3.LShR(magnitude, shift)
        increment = z3.BoolVal(False)
        if shift:
            remainder = z3.Extract(shift - 1, 0, magnitude)
            half = z3.BitVecVal(1 << (shift - 1), shift)
            parity = z3.Extract(0, 0, quotient) == 1
            if nearest:
                increment = z3.Or(z3.UGT(remainder, half), z3.And(remainder == half, parity))
            if target:
                assert nearest
                self.solver.add(remainder == half)
                if opposite:
                    increment = z3.Not(parity)
        else:
            assert not target
        rounded = quotient + z3.If(increment, z3.BitVecVal(1, quotient.size()),
                                  z3.BitVecVal(0, quotient.size()))
        self.solver.add(z3.UGE(rounded, 1 << (bits - 1)))
        if bits < rounded.size():
            self.solver.add(z3.ULT(rounded, 1 << bits))
        if opposite:
            scaled = abs(a.reference) / audit.two(step)
            whole = scaled.numerator // scaled.denominator
            assert scaled - whole == audit.Q(1, 2)
            reference = a.sign * (whole + int(not (whole & 1))) * audit.two(step)
        else:
            reference = audit.N64(a.reference) if nearest else audit.T(a.reference, bits)
        return self.remember(Word(z3.Extract(bits - 1, 0, rounded), a.sign, step, reference))

    def correction(self, u, node, opposite):
        c = lambda n: self.constant(audit.ROM[n])
        mul = lambda a, b: self.round(self.mul(a, b))
        rn = lambda a, hit=False: self.round(a, 64, True, hit, opposite and hit)
        v = mul(u, u)
        if node == 2:
            even = self.round(self.add(c(114), mul(v, c(116))))
            odd = rn(self.add(c(115), mul(v, c(117))), True)
        else:
            odd_inner = rn(self.add(c(121), mul(v, c(123))), node == 0)
            even_inner = rn(self.add(c(120), mul(v, c(122))), node == 1)
            odd = self.round(self.add(c(119), mul(v, odd_inner)))
            even = self.round(self.add(c(118), mul(v, even_inner)))
        return rn(self.add(mul(u, odd), even))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node', type=int, choices=(0, 1, 2), required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--solver-path', type=Path, default=Path('/private/tmp/fsincos-smt-deps'))
    parser.add_argument('--timeout-ms', type=int, default=30000)
    args = parser.parse_args()
    sys.path.insert(0, str(args.solver_path))
    import z3
    args.out.mkdir(exist_ok=False)
    source = BASE / f'd0045-node{args.node}-upper/miner.tsv'
    template = None
    with source.open() as stream:
        for line in stream:
            fields = line.split()
            if fields[0] == 'T' and (args.node != 2 or fields[6] == '1'):
                template = fields
                break
    assert template
    exponent, word = int(template[3]), int(template[4], 16)
    solver = z3.SolverFor('QF_BV')
    solver.set(timeout=args.timeout_ms)
    graph = Graph(z3, solver)
    variable = z3.BitVec('u_significand', 64)
    solver.add(z3.UGE(variable, 1 << 63))
    if args.node < 2:
        solver.add(z3.ULE(variable, 9 << 60))
    u = Word(variable, 1, exponent - 63, word * audit.two(exponent - 63))
    fixed = graph.correction(u, args.node, False)
    changed = graph.correction(u, args.node, True)
    assert fixed.step == changed.step and fixed.sign == changed.sign
    solver.push()
    solver.add(variable == word)
    assert solver.check() == z3.sat
    model = solver.model()
    for record in graph.records:
        value = model.eval(record.magnitude, model_completion=True).as_long()
        assert record.sign * value * audit.two(record.step) == record.reference
    solver.pop()
    solver.add(fixed.magnitude != changed.magnitude)
    query = args.out / 'query.smt2'
    with query.open('x') as target:
        target.write(solver.to_smt2())
    started = time.monotonic()
    result = solver.check()
    report = dict(status='TEMPLATE_SCOPED_TIE_CARRY_QUERY', result=str(result),
        node=args.node, square_exponent=exponent, template_u=f'{word:016x}',
        concrete_template_replay='PASS', timeout_ms=args.timeout_ms,
        elapsed_seconds=time.monotonic() - started, solver='Z3 ' + z3.get_version_string(),
        query_sha256=digest(query), source_sha256=digest(Path(__file__)),
        target_source_sha256=digest(source), hardware_executed=False, numerical_model_changed=False,
        limits='Relaxed square input and explicit reference-derived normalization/sign template only. SAT needs square and external preimages. UNSAT is not a global exclusion. UNKNOWN means only the bounded solver did not decide.')
    if result == z3.sat:
        found = solver.model().eval(variable).as_long()
        exact_u = found * audit.two(exponent - 63)
        target, h = target_and_correction(args.node, exact_u)
        same_target, other = target_and_correction(args.node, exact_u, True)
        assert target == same_target and h != other
        report.update(u_significand=f'{found:016x}', parity=audit.event(target, 64)['parity'],
                      independent_fraction_replay='PASS', external_preimage_status='NOT_YET_SEARCHED')
    elif result == z3.unknown:
        report['reason_unknown'] = solver.reason_unknown()
    save(args.out / 'REPORT.json', report)
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
