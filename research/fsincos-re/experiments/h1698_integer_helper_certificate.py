#!/usr/bin/env python3
"""Source-backed integer-helper lemmas, independently solved and C-tested.

SMT predicates are explicit manual translations of the pinned helpers, not
an automatic C/LLVM formal verifier. Save every SAT/UNSAT/UNKNOWN query and
compare the actual compiled helpers with a separate Python integer oracle.
Whole-graph carrier-range obligations and silicon fidelity remain separate.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import random
import re
import subprocess
from collections import Counter
from pathlib import Path
import cvc5
import z3
from h1640_remaining_scope_freshness import save
from h1665_small_denormal_provenance import digest

MASK128, MASK256 = (1 << 128) - 1, (1 << 256) - 1
LOCKS = {'src/fsincos_skylake.c': '0339a7d6161c29164232fadd46053a538b7163d5d4449889e3600e9245026f2b',
         'src/ia64_sf.h': 'a5e9d085f2607cbc43fecbadcce3cebf57620fb07d9509627ce2d27164d7758d'}


def bv(n, width): return z3.BitVecVal(n, width)
def flag(c, width=128): return z3.If(c, bv(1, width), bv(0, width))
def join(hi, lo): return z3.Concat(hi, lo)
def limbs(word): return z3.Extract(255, 128, word), z3.Extract(127, 0, word)


def arithmetic_queries():
    p = [z3.BitVec('p' + str(i), 128) for i in range(4)]
    lo, hi = p[0], p[3]
    for cross in (p[1], p[2]):
        old = lo; lo = lo + (cross << 64)
        hi = hi + z3.LShR(cross, 64) + flag(z3.ULT(lo, old))
    exact = z3.ZeroExt(128, p[0]) + (z3.ZeroExt(128, p[1]) << 64) + (z3.ZeroExt(128, p[2]) << 64) + (z3.ZeroExt(128, p[3]) << 128)
    yield 'product_reassembly_mod256', [], join(hi, lo) != exact
    a, b = z3.BitVecs('a b', 256); ah, al = limbs(a); bh, bl = limbs(b)
    lo = al + bl; hi = ah + bh + flag(z3.ULT(lo, al))
    yield 'acc_add_mod256', [], join(hi, lo) != a + b
    lo = al - bl; hi = ah - bh - flag(z3.ULT(al, bl))
    yield 'acc_sub_mod256', [], join(hi, lo) != a - b
    lo = ~al + 1; hi = ~ah + flag(lo == 0)
    yield 'negate_mod256', [], join(hi, lo) != -a
    for shift in range(-255, 256):
        if shift == 0: hi, lo = ah, al
        elif shift < 0:
            s = -shift
            if s < 128: hi, lo = z3.LShR(ah, s), z3.LShR(al, s) | (ah << (128 - s))
            else: hi, lo = bv(0, 128), z3.LShR(ah, s - 128)
        elif shift < 128: hi, lo = (ah << shift) | z3.LShR(al, 128 - shift), al << shift
        else: hi, lo = al << (shift - 128), bv(0, 128)
        exact = z3.LShR(a, -shift) if shift < 0 else a << shift
        yield f'align_{shift:+04d}', [], join(hi, lo) != exact


def round_query(msb, bits, terminal):
    mag = z3.BitVec('magnitude', 256); hi, lo = limbs(mag)
    negative = z3.Bool('negative'); mode = z3.BitVec('mode', 3)
    assumptions = [z3.UGE(mag, bv(1 << msb, 256)), z3.ULE(mag, bv((1 << (msb + 1)) - 1, 256)),
                   z3.ULE(mode, bv(3 if terminal else 5, 3))]
    sh = msb - bits + 1
    guard, below = z3.BoolVal(False), bv(0, 128)
    if sh <= 0: top = lo << -sh
    elif sh < 128:
        top = (hi << (128 - sh)) | z3.LShR(lo, sh)
        guard = (z3.LShR(lo, sh - 1) & 1) != 0
        below = lo & bv((1 << (sh - 1)) - 1, 128)
    else:
        hsh = sh - 128; top = z3.LShR(hi, hsh)
        if hsh == 0:
            guard = z3.LShR(lo, 127) != 0; below = lo & bv((1 << 127) - 1, 128)
        else:
            guard = (z3.LShR(hi, hsh - 1) & 1) != 0
            below = (hi & bv((1 << (hsh - 1)) - 1, 128)) | flag(lo != 0)
    discarded = z3.Or(guard, below != 0)
    if terminal:
        narrow = z3.Extract(63, 0, top)
        inc = z3.Or(z3.And(mode == 0, guard, z3.Or(below != 0, (narrow & 1) != 0)),
                    z3.And(mode == 2, z3.Not(negative), discarded), z3.And(mode == 1, negative, discarded))
        advanced = narrow + flag(inc, 64); overflow = z3.And(inc, advanced == 0)
        c_sig = z3.If(overflow, bv(1 << 63, 64), advanced)
    else:
        inc = z3.Or(z3.And(mode == 3, discarded, (top & 1) == 0),
                    z3.And(mode == 2, discarded), z3.And(mode == 4, z3.Not(negative), discarded),
                    z3.And(mode == 5, negative, discarded),
                    z3.And(mode == 0, guard, z3.Or(below != 0, (top & 1) != 0)))
        advanced = z3.If(mode == 3, top | flag(discarded), top + flag(inc))
        overflow = z3.And(mode != 3, inc, advanced == bv(1 << bits, 128))
        c_sig = z3.If(overflow, z3.LShR(advanced, 1), advanced)
    c_shift = bv(sh, 16) + flag(overflow, 16)
    # Independent quotient/remainder definition, no guard/sticky extraction.
    q = mag << -sh if sh <= 0 else z3.LShR(mag, sh)
    rem = bv(0, 256) if sh <= 0 else mag & bv((1 << sh) - 1, 256)
    nonexact = rem != 0
    rn = z3.BoolVal(False) if sh <= 0 else z3.Or(z3.UGT(rem, bv(1 << (sh - 1), 256)),
                z3.And(rem == bv(1 << (sh - 1), 256), (q & 1) != 0))
    if terminal:
        expected_inc = z3.Or(z3.And(mode == 0, rn), z3.And(mode == 1, negative, nonexact),
                             z3.And(mode == 2, z3.Not(negative), nonexact))
    else:
        expected_inc = z3.Or(z3.And(mode == 0, rn), z3.And(mode == 2, nonexact),
            z3.And(mode == 3, nonexact, (q & 1) == 0),
            z3.And(mode == 4, z3.Not(negative), nonexact), z3.And(mode == 5, negative, nonexact))
    expected_top = q + flag(expected_inc, 256)
    expected_overflow = z3.UGE(expected_top, bv(1 << bits, 256))
    expected_sig = z3.If(expected_overflow, z3.LShR(expected_top, 1), expected_top)
    errors = [z3.ZeroExt(256 - c_sig.size(), c_sig) != expected_sig,
              c_shift != bv(sh, 16) + flag(expected_overflow, 16), inc != expected_inc]
    if not terminal:
        c_rh = z3.If(discarded, z3.If(inc, bv(1, 3), bv(-1, 3)), bv(0, 3))
        expected_rh = z3.If(nonexact, z3.If(expected_inc, bv(1, 3), bv(-1, 3)), bv(0, 3))
        errors.append(z3.If(negative, -c_rh, c_rh) != z3.If(negative, -expected_rh, expected_rh))
    return assumptions, z3.Or(*errors)


def solve(name, assumptions, error, out, timeout):
    solver = z3.SolverFor('QF_BV'); solver.set(timeout=timeout)
    solver.add(*assumptions, error)
    script = '(set-logic QF_BV)\n' + solver.to_smt2()
    path = out / (name + '.smt2')
    with path.open('x') as target: target.write(script)
    answer = solver.check(); first = str(answer).upper()
    second_solver = cvc5.Solver(); second_solver.setOption('tlimit-per', str(timeout))
    parser = cvc5.InputParser(second_solver)
    parser.setStringInput(cvc5.InputLanguage.SMT_LIB_2_6, script, name)
    symbols = parser.getSymbolManager(); replies = []
    while True:
        command = parser.nextCommand()
        if command.isNull(): break
        reply = command.invoke(second_solver, symbols)
        if reply.strip(): replies.append(reply.strip().upper())
    assert len(replies) == 1, replies
    row = dict(query=name, z3=first, cvc5=replies[0], sha256=digest(path))
    if answer == z3.sat: row['z3_counterexample'] = str(solver.model())
    if answer == z3.unknown: row['z3_reason'] = solver.reason_unknown()
    save(out / (name + '.json'), row)
    return row


def rounded_oracle(word, bits, mode, scale, terminal=False, negative_out=0):
    negative = int(word >> 255); mag = (-word & MASK256) if negative else word
    if terminal: negative ^= negative_out
    if not mag: return f'{negative} {0 if terminal else 0} {0:016x}' if terminal else f'{negative} 0 {0:032x} 0'
    shift = mag.bit_length() - bits
    q, rem = (mag << -shift, 0) if shift <= 0 else divmod(mag, 1 << shift)
    rn = bool(rem and (rem * 2 > 1 << shift or (rem * 2 == 1 << shift and q & 1)))
    if terminal: inc = rn if mode == 0 else bool(rem and ((mode == 1 and negative) or (mode == 2 and not negative)))
    else: inc = rn if mode == 0 else bool(rem and (mode == 2 or (mode == 3 and not q & 1) or (mode == 4 and not negative) or (mode == 5 and negative)))
    q += inc
    if q >= 1 << bits: q >>= 1; shift += 1
    if terminal: return f'{negative} {scale + shift + 63} {q:016x}'
    rh = (1 if inc else -1) * (-1 if negative else 1) if rem else 0
    return f'{negative} {scale + shift} {q:032x} {rh}'


def c_bank():
    rng = random.Random(1698); rows = []; expected = []; counts = Counter()
    def add(op, a=0, b=0, neg=0, bits=64, mode=0, shift=0):
        words = [f'{(v >> s) & ((1 << 64) - 1):016x}' for v in (a, b) for s in (192, 128, 64, 0)]
        rows.append(' '.join([op, str(neg), str(bits), str(mode), str(shift), *words]) + '\n')
        if op == 'M': answer = f'{(a & MASK128) * (b & MASK128):064x}'
        elif op == 'A': answer = f'{(a + (-b if neg else b)) & MASK256:064x}'
        elif op == 'S':
            product = (b >> 128) * (b & MASK128)
            shifted = product << shift if shift >= 0 else product >> -shift
            answer = f'{(a + (-shifted if neg else shifted)) & MASK256:064x}'
        else: answer = rounded_oracle(a, bits, mode, shift, op == 'F', neg)
        expected.append(answer); counts[op] += 1
    special = [0, 1, (1 << 64) - 1, 1 << 64, MASK128, 1 << 127]
    for a in special:
        for b in special: add('M', a, b)
    for _ in range(4096): add('M', rng.getrandbits(128), rng.getrandbits(128))
    for _ in range(4096):
        a, b = rng.getrandbits(256), rng.getrandbits(256)
        for neg in (0, 1): add('A', a, b, neg)
    for shift in range(-255, 256):
        for _ in range(4):
            for neg in (0, 1): add('S', rng.getrandbits(256), rng.getrandbits(256), neg, shift=shift)
    for bits in (64, 67):
        for msb in range(255):
            sh = msb - bits + 1
            values = {1 << msb, (1 << (msb + 1)) - 1, (1 << msb) | rng.getrandbits(msb)}
            if sh > 0:
                for parity in (0, 1):
                    kept = (1 << (bits - 1)) | parity
                    for tail in (0, 1, (1 << (sh - 1)) - 1, 1 << (sh - 1), (1 << (sh - 1)) + 1, (1 << sh) - 1):
                        v = (kept << sh) + tail
                        if v.bit_length() == msb + 1: values.add(v)
            for mag in values:
                for sign in (0, 1):
                    word = -mag & MASK256 if sign else mag
                    for mode in range(6): add('R', word, bits=bits, mode=mode, shift=-317)
                    if bits == 64:
                        for mode in range(4):
                            for neg in (0, 1): add('F', word, neg=neg, mode=mode, shift=-317)
        for word in (0, 1 << 255):
            for mode in range(6): add('R', word, bits=bits, mode=mode)
            if bits == 64:
                for mode in range(4):
                    for neg in (0, 1): add('F', word, neg=neg, mode=mode)
    return ''.join(rows), expected, dict(counts)


def compiled_check(root, out):
    stream, expected, counts = c_bank(); results = []
    for name, flags in (('O0', ['-O0']), ('O2', ['-O2']), ('O3', ['-O3']),
                        ('UBSan', ['-O2', '-fsanitize=undefined', '-fno-sanitize-recover=all'])):
        binary = out / ('helpers_' + name)
        build = subprocess.run(['cc', *flags, '-std=c11', '-DG_ROUND84=0',
            str(root / 'experiments/h1698_integer_helper_driver.c'), '-lm', '-o', str(binary)], capture_output=True, text=True)
        assert build.returncode == 0 and not build.stderr, build.stderr
        run = subprocess.run([str(binary)], input=stream, capture_output=True, text=True)
        actual = run.stdout.splitlines()
        misses = [dict(index=i, input=line.rstrip(), expected=e, actual=a)
                  for i, (line, e, a) in enumerate(zip(stream.splitlines(), expected, actual)) if e != a]
        result = dict(build=name, returncode=run.returncode, expected_rows=len(expected), actual_rows=len(actual),
                      misses=misses, diagnostics=run.stderr, binary_sha256=digest(binary),
                      output_sha256=hashlib.sha256(run.stdout.encode()).hexdigest())
        save(out / (name + '.json'), result); results.append(result)
        print(json.dumps(dict(build=name, rows=len(actual), misses=len(misses), returncode=run.returncode)), flush=True)
    return dict(cases=len(expected), case_kinds=counts, input_sha256=hashlib.sha256(stream.encode()).hexdigest(),
        oracle_sha256=hashlib.sha256(('\n'.join(expected) + '\n').encode()).hexdigest(), builds=results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path); parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--timeout-ms', type=int, default=10000)
    args = parser.parse_args(); root, out = args.root.resolve(), args.output_dir.resolve(); assert not out.exists()
    for name, expected in LOCKS.items(): assert digest(root / name) == expected, name
    out.mkdir(parents=True); queries = out / 'queries'; queries.mkdir()
    rows = []
    for name, assumptions, error in arithmetic_queries():
        rows.append(solve(name, assumptions, error, queries, args.timeout_ms))
    for terminal, bits in ((False, 64), (False, 67), (True, 64)):
        for msb in range(256):
            assumptions, error = round_query(msb, bits, terminal)
            name = f'{"terminal" if terminal else "internal"}_{bits}_{msb:03d}'
            rows.append(solve(name, assumptions, error, queries, args.timeout_ms))
        print(json.dumps(dict(lemmas_completed=len(rows), current_family=name)), flush=True)
    compiled = compiled_check(root, out)
    proved = all(r['z3'] == r['cvc5'] == 'UNSAT' for r in rows)
    tested = all(r['returncode'] == 0 and r['actual_rows'] == r['expected_rows'] and not r['misses'] and not r['diagnostics'] for r in compiled['builds'])
    save(out / 'solver_results.json', rows)
    report = dict(experiment='h1698_integer_helper_certificate', status='PASS_HELPER_LEMMAS_AND_C_TESTS' if proved and tested else 'UNRESOLVED_OR_FAILED',
        queries=len(rows), z3_counts=dict(Counter(r['z3'] for r in rows)), cvc5_counts=dict(Counter(r['cvc5'] for r in rows)),
        solvers=dict(z3=z3.get_version_string(), cvc5=cvc5.__version__), timeout_ms_per_query=args.timeout_ms,
        compiled=compiled, algebra='Exact64x64 products fit128 bits. Expanding (a0+2^64*a1)*(b0+2^64*b1) yields the four proved partial-product terms; the true128x128 product fits256 bits. Add/sub/align are modulo256; exact signed interpretation requires no overflow. Right shifts mean floor, requiring divisibility when a caller claims exact alignment.',
        scope='Explicit source-backed bitvector translations, not automatic C formal verification or compiler proof. All magnitude MSB positions, signs and listed modes; scale addition assumes int32 range. Actual C helper tests cover boundary/tie/carry/random cases on four builds. Whole-program callsite range/dispatch/overflow, special-state and all-input silicon fidelity remain open.',
        hardware_execution='none', labels_opened=False, private_ledger_access='none', production_default_or_paper_change=False,
        sha256=dict(script=digest(Path(__file__)), driver=digest(root / 'experiments/h1698_integer_helper_driver.c'),
                    evidence=LOCKS, solver_results=digest(out / 'solver_results.json')))
    save(out / 'report.json', report)
    print(json.dumps({k: report[k] for k in ('status', 'queries', 'z3_counts', 'cvc5_counts')}), flush=True)


if __name__ == '__main__': main()
