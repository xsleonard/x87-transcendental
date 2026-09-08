#!/usr/bin/env python3
"""Source-backed exact C reduction contract; no silicon equivalence claim.

Linear-integer quotient lemmas, bitvector limb/normalization/split lemmas,
explicit odd-divisor certificates and actual four-build C differential tests.
Translations are manual and pinned, not automatic C/LLVM/compiler proofs.
No hardware, private ledger, production/default change or paper promotion.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import random
import subprocess
from collections import Counter
from fractions import Fraction as F
from pathlib import Path
import cvc5
import z3
from h1640_remaining_scope_freshness import save
from h1665_small_denormal_provenance import digest

M = 0x3243f6a8885a308d3
H = M // 2
MAX_A = ((1 << 64) - 1) << 64
MASK64 = (1 << 64) - 1
LOCKS = {'src/fsincos_skylake.c': '0339a7d6161c29164232fadd46053a538b7163d5d4449889e3600e9245026f2b',
         'src/ia64_sf.h': 'a5e9d085f2607cbc43fecbadcce3cebf57620fb07d9509627ce2d27164d7758d'}


def bv(n, w): return z3.BitVecVal(n, w)
def flag(c, w): return z3.If(c, bv(1, w), bv(0, w))
def limbs(x): return [z3.Extract(64 * i + 63, 64 * i, x) for i in range(3)]


def queries():
    q, r, a, ref = z3.Ints('floor_q remainder dividend reference_q')
    premises = [q >= 0, r >= 0, r < M, a == q * M + r, a >= 0, a <= MAX_A]
    n = q + z3.If(2 * r > M, 1, 0); d = a - n * M
    yield 'nearest_quotient', 'QF_LIA', premises + [ref * M <= a + H, a + H < (ref + 1) * M], n != ref
    yield 'centered_bound', 'QF_LIA', premises, z3.Or(d < -H, d > H)
    yield 'quotient_signed64_bound', 'QF_LIA', premises, z3.Or(n < 0, n + 1 >= 1 << 63)
    yield 'remainder_double_width', 'QF_LIA', premises, 2 * r >= 1 << 128
    yield 'half_tie_impossible', 'QF_LIA', [r >= 0, r < M], 2 * r == M
    s = z3.BitVec('sig', 64)
    for k in range(1, 65):
        low = bv(0, 64) if k == 64 else s << k
        mid = s if k == 64 else z3.LShR(s, 64 - k)
        actual = z3.Concat(bv(0, 64), mid, low)
        yield f'dividend_{k:02d}', 'QF_BV', [], actual != z3.ZeroExt(128, s) << k
    # t=N*lo64 and u=3*N; the merge identity holds modulo192 even for
    # independent128-bit t/u. Actual product bounds lift it to exact arithmetic.
    t, u = z3.BitVecs('t u', 128)
    low = z3.Extract(63, 0, t)
    mid = z3.ZeroExt(64, z3.Extract(127, 64, t)) + z3.ZeroExt(64, z3.Extract(63, 0, u))
    high = z3.Extract(127, 64, u) + z3.Extract(127, 64, mid)
    actual = z3.Concat(high, z3.Extract(63, 0, mid), low)
    yield 'product_limb_merge', 'QF_BV', [], actual != z3.ZeroExt(64, t) + (z3.ZeroExt(64, u) << 64)
    x, y = z3.BitVecs('x y', 192); xx, yy = limbs(x), limbs(y)
    ge = z3.If(xx[2] != yy[2], z3.UGT(xx[2], yy[2]),
               z3.If(xx[1] != yy[1], z3.UGT(xx[1], yy[1]), z3.UGE(xx[0], yy[0])))
    yield 'limb_unsigned_compare', 'QF_BV', [], ge != z3.UGE(x, y)
    low = xx[0] - yy[0]; borrow = z3.ULT(xx[0], yy[0])
    mid = xx[1] - yy[1] - flag(borrow, 64)
    borrow = z3.Or(z3.ULT(xx[1], yy[1]), z3.And(xx[1] == yy[1], borrow))
    high = xx[2] - yy[2] - flag(borrow, 64)
    yield 'limb_subtract', 'QF_BV', [], z3.Concat(high, mid, low) != x - y
    v = z3.BitVec('nonzero_low64', 64)
    for b in range(64):
        normalized = v << (63 - b)
        constraints = [z3.UGE(v, bv(1 << b, 64)), z3.ULE(v, bv((1 << (b + 1)) - 1, 64))]
        yield f'exact_normalize_{b:02d}', 'QF_BV', constraints, z3.Or(
            z3.LShR(normalized, 63 - b) != v, z3.LShR(normalized, 63) != 1)
    d65 = z3.BitVec('magnitude65', 65); low = z3.Extract(63, 0, d65)
    domain = [z3.UGE(d65, bv(1 << 64, 65)), z3.ULE(d65, bv(H, 65))]
    kept = bv(1 << 63, 64) | z3.LShR(low, 1)
    g = (low & 1) != 0; inc = z3.And(g, (kept & 1) != 0)
    rounded = kept + flag(inc, 64)
    yield 'split_no_kept_overflow', 'QF_BV', domain, rounded == 0
    spec_floor = z3.LShR(d65, 1)
    spec_inc = z3.And((d65 & 1) != 0, (spec_floor & 1) != 0)
    yield 'split_RN64', 'QF_BV', domain, z3.ZeroExt(1, rounded) != spec_floor + flag(spec_inc, 65)
    # In units2^-65, rounded r equals2*kept. c is0,+1,-1. The fold is exact.
    carry = z3.If(inc, bv(-1, 67), flag(g, 67))
    reconstructed = (z3.ZeroExt(3, rounded) << 1) + carry
    yield 'split_and_fold_identity', 'QF_BV', domain, reconstructed != z3.ZeroExt(2, d65)
    # Whenever c is present, r.exp=-1; the overflow arm above is unreachable.
    yield 'nonzero_c_is_one_unit', 'QF_BV', domain, z3.And(g, z3.And(carry != bv(1, 67), carry != bv(-1, 67)))


def solve(name, logic, premises, error, out, timeout):
    solver = z3.SolverFor(logic); solver.set(timeout=timeout); solver.add(*premises, error)
    script = '(set-logic ' + logic + ')\n' + solver.to_smt2()
    path = out / (name + '.smt2')
    with path.open('x') as target: target.write(script)
    answer = solver.check()
    second = cvc5.Solver(); second.setOption('tlimit-per', str(timeout))
    parser = cvc5.InputParser(second); parser.setStringInput(cvc5.InputLanguage.SMT_LIB_2_6, script, name)
    symbols = parser.getSymbolManager(); replies = []
    while True:
        command = parser.nextCommand()
        if command.isNull(): break
        reply = command.invoke(second, symbols)
        if reply.strip(): replies.append(reply.strip().upper())
    assert len(replies) == 1
    row = dict(query=name, logic=logic, z3=str(answer).upper(), cvc5=replies[0], sha256=digest(path))
    if answer == z3.sat: row['counterexample'] = str(solver.model())
    if answer == z3.unknown: row['reason'] = solver.reason_unknown()
    save(out / (name + '.json'), row); return row


def arithmetic_certificate():
    assert M & 1 and M.bit_length() == 66 and M > MASK64
    assert MAX_A < 1 << 128 and 2 * (M - 1) < 1 << 67
    qmax = (MAX_A + H) // M
    assert qmax + 1 < 1 << 63 and qmax * M < 1 << 129
    assert qmax * (M & MASK64) < 1 << 128 and qmax * 3 < 1 << 65
    assert H < 1 << 65 and ((H + 1) >> 1) < 1 << 64
    inverses = []
    for k in range(1, 65):
        inverse = pow(1 << k, -1, M)
        multiple, rem = divmod(inverse * (1 << k) - 1, M)
        assert rem == 0 and 0 < inverse < M
        inverses.append(dict(shift=k, inverse=str(inverse), multiple=str(multiple)))
    return dict(M66=str(M), centered_magnitude_max=str(H), dividend_max=str(MAX_A), quotient_max=str(qmax),
        raw_shift_interval=[1, 64], low_normalization_shift_interval=[0, 63],
        quotient_phase_signed64_safe=True, product_B_bits_at_most=129,
        bezout_certificates=inverses,
        no_zero_argument='If M divides sig*2^k, the verified inverse implies M divides sig. But0<sig<2^64<M; contradiction. Therefore D!=0 for every normalized input in the reduction domain.',
        split_argument='0<|D|<=floor(M/2)<2^65. Below2^64, normalization is exact. At65bits, rounding drops just the low bit with ties-even; the kept word cannot overflow under this bound. c is0 or signed2^-65, and the fold reconstructs D exactly.',
        compiler_assumptions='Unsigned128 division/remainder follow C semantics; uint64/unsigned32 widths and normal integer code generation. Manual source-to-predicate correspondence, not automatic C proof.')


def p2(e): return F(1 << e) if e >= 0 else F(1, 1 << -e)


def encode_rational(value, zero_sign):
    if not value: return zero_sign, 0, 0
    sign = int(value < 0); value = abs(value)
    exponent = value.numerator.bit_length() - value.denominator.bit_length()
    sig = value / p2(exponent - 63)
    assert sig.denominator == 1 and 1 << 63 <= sig < 1 << 64
    return sign, exponent, sig.numerator


def oracle(sign, e, sig, phase):
    a = sig << (e + 2); quotient = (a + H) // M; delta = a - quotient * M
    assert delta and abs(delta) <= H
    value = (-1 if sign else 1) * delta * p2(-65)
    rs = int(value < 0); absolute = abs(value)
    exponent = absolute.numerator.bit_length() - absolute.denominator.bit_length()
    unit = p2(exponent - 63); scaled = absolute / unit
    floor, rem = divmod(scaled.numerator, scaled.denominator)
    inc = rem * 2 > scaled.denominator or (rem * 2 == scaled.denominator and floor & 1)
    rounded = (-1 if rs else 1) * (floor + inc) * unit
    rsign, rexp, rsig = encode_rational(rounded, rs)
    csign, cexp, csig = encode_rational(value - rounded, rs)
    assert rounded + (-1 if csign else 1) * csig * p2(cexp - 63) == value
    # The public wide carrier representation is selected by whether the split
    # needs c, but its numerical significand comes directly from exact delta.
    we, wsig = (-65, abs(delta)) if csig else (rexp - 63, rsig)
    assert (-1 if rs else 1) * wsig * p2(we) == value
    n = (-quotient if sign else quotient) + phase
    return f'{quotient} {rsign} {rexp} {rsig:016x} {csign} {cexp} {csig:016x} {rs} {we} {wsig:032x} {n} {n & 1} {(n >> 1) & 1}'


def bank():
    rng = random.Random(1700); values = set(); exact_target_rows = 0
    targets = {1, 2, 3, H, H - 1}
    for cut in (1 << 63, 1 << 64): targets.update(cut + d for d in range(-3, 4))
    targets |= {-v for v in tuple(targets)}
    for e in range(-1, 63):
        k = e + 2
        sigs = {1 << 63, (1 << 63) + 1, (1 << 63) + 2, MASK64, MASK64 - 1, MASK64 - 2}
        for _ in range(64):
            s = (1 << 63) | rng.getrandbits(63); sigs.add(s)
            q = ((s << k) + H) // M
            halfway = (M * (2 * q + 1)) // (1 << (k + 1))
            for d in range(-2, 3):
                if 1 << 63 <= halfway + d <= MASK64: sigs.add(halfway + d)
        for delta in targets:
            q = (-delta * pow(M, -1, 1 << k)) % (1 << k)
            a = q * M + delta
            assert a % (1 << k) == 0
            s = a >> k
            if 1 << 63 <= s <= MASK64:
                assert (s << k) - ((s << k) + H) // M * M == delta
                sigs.add(s); exact_target_rows += 1
        for s in sigs:
            for sign in (0, 1):
                for phase in (0, 1): values.add((sign, e, s, phase))
    rows = sorted(values)
    stream = ''.join(f'{sign} {e} {sig:016x} {phase}\n' for sign, e, sig, phase in rows)
    expected = [oracle(*row) for row in rows]
    return stream, expected, dict(rows=len(rows), unsigned_exponent_significand_pairs=len(rows) // 4,
        exact_residual_target_preimages=exact_target_rows, exponent_count=64,
        near_halfway_generation='software-only neighbors of exact quotient half boundaries; no hardware labels')


def compiled_check(root, out):
    stream, expected, counts = bank(); results = []
    for label, flags in (('O0', ['-O0']), ('O2', ['-O2']), ('O3', ['-O3']),
                         ('UBSan', ['-O2', '-fsanitize=undefined', '-fno-sanitize-recover=all'])):
        binary = out / ('reduction_' + label)
        build = subprocess.run(['cc', *flags, '-std=c11', '-DG_ROUND84=0',
            str(root / 'experiments/h1700_reduction_driver.c'), '-lm', '-o', str(binary)], capture_output=True, text=True)
        assert build.returncode == 0 and not build.stderr, build.stderr
        run = subprocess.run([str(binary)], input=stream, capture_output=True, text=True)
        actual = run.stdout.splitlines()
        misses = [dict(index=i, input=line, expected=e, actual=a) for i, (line, e, a) in
                  enumerate(zip(stream.splitlines(), expected, actual)) if e != a]
        result = dict(build=label, returncode=run.returncode, expected_rows=len(expected), actual_rows=len(actual),
            misses=misses, diagnostics=run.stderr, binary_sha256=digest(binary),
            output_sha256=hashlib.sha256(run.stdout.encode()).hexdigest())
        save(out / (label + '.json'), result); results.append(result)
        print(json.dumps(dict(build=label, rows=len(actual), misses=len(misses), returncode=run.returncode)), flush=True)
    return dict(counts=counts, input_sha256=hashlib.sha256(stream.encode()).hexdigest(),
        oracle_sha256=hashlib.sha256(('\n'.join(expected) + '\n').encode()).hexdigest(), builds=results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path); parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--timeout-ms', type=int, default=10000)
    args = parser.parse_args(); root, out = args.root.resolve(), args.output_dir.resolve(); assert not out.exists()
    for name, expected in LOCKS.items(): assert digest(root / name) == expected, name
    arithmetic = arithmetic_certificate(); out.mkdir(parents=True); query_dir = out / 'queries'; query_dir.mkdir()
    results = [solve(*query, query_dir, args.timeout_ms) for query in queries()]
    save(out / 'solver_results.json', results); compiled = compiled_check(root, out)
    proved = all(r['z3'] == r['cvc5'] == 'UNSAT' for r in results)
    tested = all(r['returncode'] == 0 and not r['diagnostics'] and not r['misses'] and r['actual_rows'] == r['expected_rows'] for r in compiled['builds'])
    report = dict(experiment='h1700_exact_reduction_certificate', status='PASS_REDUCTION_CONTRACT' if proved and tested else 'UNRESOLVED_OR_FAILED',
        queries=len(results), z3_counts=dict(Counter(r['z3'] for r in results)), cvc5_counts=dict(Counter(r['cvc5'] for r in results)),
        solvers=dict(z3=z3.get_version_string(), cvc5=cvc5.__version__), arithmetic_certificate=arithmetic, compiled=compiled,
        domain='Normalized finite significand2^63..2^64-1, unbiased exponent-1..62, either input sign and phase0/1. Includes some inputs below the real reduction cutoff as a safe mathematical superset.',
        scope='Exact quotient/limb arithmetic, numerical r/c split and wide reconstruction under pinned C semantics and manual predicate correspondence. No automatic C/compiler proof, silicon reducer identity, complete entry dispatch/conversion/state coverage or claim about uninitialized unused wv.rh metadata.',
        hardware_execution='none', labels_opened=False, private_ledger_access='none', production_default_or_paper_change=False,
        sha256=dict(script=digest(Path(__file__)), driver=digest(root / 'experiments/h1700_reduction_driver.c'), evidence=LOCKS,
                    solver_results=digest(out / 'solver_results.json')))
    save(out / 'report.json', report)
    print(json.dumps({k: report[k] for k in ('status', 'queries', 'z3_counts', 'cvc5_counts')}), flush=True)


if __name__ == '__main__': main()
