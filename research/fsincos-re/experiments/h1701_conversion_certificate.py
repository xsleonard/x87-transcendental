#!/usr/bin/env python3
"""Source-backed conversion/grid contract, not universal silicon proof.

Prove explicit manually transcribed normalization/store predicates and test
the actual C helpers plus the unchanged isolated tiny entry. Preserve both
positive proofs and SAT negative controls. No hardware or private data.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import random
import subprocess
from collections import Counter
from pathlib import Path
import cvc5
import z3
from h1700_exact_reduction_certificate import solve, bv
from h1640_remaining_scope_freshness import save
from h1665_small_denormal_provenance import digest

B = 1 << 63
MASK = (1 << 64) - 1
LOCKS = {
    'src/fsincos_skylake.c': '0339a7d6161c29164232fadd46053a538b7163d5d4449889e3600e9245026f2b',
    'src/ia64_sf.h': 'a5e9d085f2607cbc43fecbadcce3cebf57620fb07d9509627ce2d27164d7758d',
    'experiments/h1638_tiny_closed_form.h': '910cbb03c7310ad86b77bce4ae64fd611d96374c794df0048922b7dc2f199227',
    'experiments/h1700_exact_reduction_certificate.py': 'ac6ece113c44b2dc6d172a0eaacb9082c61e09c68d44dbef2b8e71902a9d0802',
}


def queries():
    s = z3.BitVec('significand', 64)
    step = z3.BitVec('normalization_step', 64)
    for top in range(64):
        shift = 63 - top
        domain = [z3.UGE(s, bv(1 << top, 64)), z3.ULE(s, bv((1 << (top + 1)) - 1, 64))]
        value = s << step
        # Inductive loop summary: each permitted shift is lossless; bit63 is
        # first set exactly at the final step, never at an earlier iteration.
        error = z3.Or(z3.LShR(value, step) != s,
            ((value & B) != 0) != (step == shift))
        yield f'normalize_loop_{top:02d}', 'QF_BV', domain + [z3.ULE(step, bv(shift, 64))], error, 'UNSAT'
        normalized = s << shift
        stored = z3.LShR(normalized, shift)
        yield f'zero_field_roundtrip_{top:02d}', 'QF_BV', domain, stored != s, 'UNSAT'
    for shift in range(1, 64):
        stored = z3.LShR(s, shift)
        rem = s & bv((1 << shift) - 1, 64)
        recovered = z3.ZeroExt(64, stored) << shift
        yield f'subnormal_store_grid_{shift:02d}', 'QF_BV', [], z3.Or(
            z3.ZeroExt(64, s) != recovered + z3.ZeroExt(64, rem),
            (recovered == z3.ZeroExt(64, s)) != (rem == 0)), 'UNSAT'
    # For every shift >=64 the mathematical unsigned quotient is zero.
    deep = z3.BitVec('deep_store_shift', 32)
    yield 'deep_store_zero', 'QF_BV', [z3.UGE(deep, bv(64, 32))], z3.LShR(s, z3.ZeroExt(32, deep)) != 0, 'UNSAT'
    exponent, k = z3.Ints('raw_exponent normalization_shift')
    effective = z3.If(exponent == 0, 1, exponent) - 16383
    yield 'decode_exponent_bounds', 'QF_LIA', [exponent >= 0, exponent <= 32766, k >= 0, k <= 63], z3.Or(
        effective - k < -16445, effective - k > 16383), 'UNSAT'
    yield 'zero_field_store_shift', 'QF_LIA', [k >= 0, k <= 63], 1 - ((-16382 - k) + 16383) != k, 'UNSAT'
    yield 'normal_exponent_roundtrip', 'QF_LIA', [exponent >= 1, exponent <= 32766], (exponent - 16383) + 16383 != exponent, 'UNSAT'
    raw = z3.BitVec('raw_sign_exponent', 16)
    gate = z3.And((raw & 0x7fff) != 0, z3.LShR(s, 63) == 0)
    valid = z3.Or((raw & 0x7fff) == 0, z3.UGE(s, bv(B, 64)))
    yield 'invalid_gate_partition', 'QF_BV', [], gate == valid, 'UNSAT'
    reconstructed = ((z3.ZeroExt(16, raw) >> 15) << 15) | (z3.ZeroExt(16, raw) & 0x7fff)
    yield 'sign_exponent_pack', 'QF_BV', [], reconstructed != z3.ZeroExt(16, raw), 'UNSAT'
    sign, phase = z3.BitVecs('sign phase', 32)
    cosine = phase & 1
    negative = (z3.LShR(phase, 1) & 1) ^ z3.If(cosine != 0, bv(0, 32), sign)
    yield 'bypass_result_sign', 'QF_BV', [z3.ULE(sign, bv(1, 32)), z3.ULE(phase, bv(1, 32))], negative != z3.If(phase == 0, sign, bv(0, 32)), 'UNSAT'
    # Negative control: an arbitrary normalized underflow input need not lie
    # on the exact bypass grid. Keep the SAT counterexample, not a false proof.
    quotient = z3.LShR(s, 1)
    inc = z3.And((s & 1) != 0, (quotient & 1) != 0)
    rn = quotient + z3.If(inc, bv(1, 64), bv(0, 64))
    yield 'NEGATIVE_generic_store_is_not_RN', 'QF_BV', [z3.UGE(s, bv(B, 64))], quotient != rn, 'SAT'
    # sf_from_parts returns zero first when sig=0. That is a helper behavior,
    # not the architectural answer for a nonzero-exponent unsupported operand.
    yield 'NEGATIVE_decode_without_raw_guard', 'QF_BV', [s == 0, (raw & 0x7fff) != 0], gate, 'SAT'


def decode(sign, ef, sig):
    if not sig:
        return 0, sign, 0, 0
    if ef == 0x7fff:
        return (1 if sig == B else 2), sign, 0, sig
    shift = 64 - sig.bit_length()
    return 0, sign, max(1, ef) - 16383 - shift, sig * (1 << shift)


def encode(cls, sign, exponent, sig):
    if cls:
        return (sign << 15) | 0x7fff, B if cls == 1 else sig
    if not sig:
        return sign << 15, 0
    if exponent >= -16382:
        return (sign << 15) | (exponent + 16383), sig
    # Direct mathematical quantization in units of the smallest subnormal.
    return sign << 15, sig // (1 << (-16382 - exponent))


def tiny_oracle(phase, rc, sign, ef, sig, row):
    if ef and sig < B:
        return 'B 0 0000 0000000000000000', None
    cls, _, exp, normal = decode(sign, ef, sig)
    if cls or not sig or exp >= -32:
        # This bank deliberately has no reduced-to-tiny operand. Inputs here
        # are direct non-tiny, special or out of range, independently checked.
        return 'B 0 0000 0000000000000000', None
    negative = 0 if phase else sign
    bypass = exp < -68
    toward = rc == 3 or (rc == 1 and not negative) or (rc == 2 and negative)
    osig, oe = (B, 0) if phase else (normal, exp)
    if not bypass and toward:
        if osig == B:
            osig, oe = MASK, oe - 1
        else:
            osig -= 1
    ose, osig = encode(0, negative, oe, osig)
    c1 = 0 if bypass else int(not toward)
    meta = f'HTINY {row} 0 {phase} {int(bypass)} {negative} {c1} {exp} {exp}'
    return f'B 1 {ose:04x} {osig:016x}', meta


def bank():
    rng = random.Random(1701)
    raw = set()
    # Every exponent, both signs and both integer-bit states, including zero.
    for ef in range(32768):
        for sign in (0, 1):
            for sig in (0, B - 1, B, MASK):
                raw.add((sign, ef, sig))
    small = {1, 2, 3, 5, B - 1, B, B + 1, MASK}
    for top in range(64):
        small.update((1 << top) + d for d in (-1, 0, 1) if 0 <= (1 << top) + d <= MASK)
        for _ in range(8):
            small.add((1 << top) | rng.getrandbits(top))
    for sig in small:
        for sign in (0, 1):
            for ef in (0, 1, 0x7ffe, 0x7fff):
                raw.add((sign, ef, sig))
    for _ in range(2048):
        raw.add((rng.randrange(2), rng.randrange(32768), rng.getrandbits(64)))
    lines, expected, metadata = [], [], []
    counts = Counter()
    for sign, ef, sig in sorted(raw):
        value = decode(sign, ef, sig); ose, osig = encode(*value)
        lines.append(f'D {sign} {ef:04x} {sig:016x}')
        gate = int(ef != 0 and sig < B)
        cls, vsign, exponent, normalized = value
        expected.append(f'D {gate} {cls} {vsign} {exponent} {normalized:016x} {ose:04x} {osig:016x}')
        counts['decode'] += 1
    stores = set()
    for sign in (0, 1):
        for exponent in (-20000, -16512, *range(-16447, -16379), -69, -68, -1, 0, 1, 16383):
            for sig in (0, B, B + 1, B + 2, B + 3, MASK):
                stores.add((0, sign, exponent, sig))
            for _ in range(8):
                stores.add((0, sign, exponent, B | rng.getrandbits(63)))
        for cls in (1, 2):
            for sig in (0, 1, B, B + 1, MASK):
                stores.add((cls, sign, 0, sig))
    for cls, sign, exponent, sig in sorted(stores):
        ose, osig = encode(cls, sign, exponent, sig)
        lines.append(f'S {cls} {sign} {exponent} {sig:016x}')
        expected.append(f'S {ose:04x} {osig:016x}')
        counts['store'] += 1
    tiny = {(sign, ef, B) for ef in range(1, 16315) for sign in (0, 1)}
    tiny.update((sign, 0, sig) for sig in small for sign in (0, 1))
    for sign in (0, 1):
        for ef in (1, 2, 16313, 16314, 16315, 16316, 16349, 16350, 16351, 0x3ffd, 0x3ffe, 0x403e, 0x7fff):
            for sig in (0, 1, B - 1, B, B + 1, (3 * B) // 2, MASK):
                tiny.add((sign, ef, sig))
    for sign, ef, sig in sorted(tiny):
        for phase in (0, 1):
            for rc in range(4):
                expected_row, meta = tiny_oracle(phase, rc, sign, ef, sig, len(lines))
                lines.append(f'B {phase} {rc} {sign} {ef:04x} {sig:016x}')
                expected.append(expected_row)
                counts['tiny_entry'] += 1
                if meta:
                    metadata.append(meta)
                    counts['tiny_hits'] += 1
                    counts['bypass_hits' if meta.split()[4] == '1' else 'nonbypass_hits'] += 1
                else:
                    counts['tiny_nonhits'] += 1
    assert len(lines) == len(expected)
    return '\n'.join(lines) + '\n', expected, '\n'.join(metadata) + '\n', dict(counts)


def compiled_checks(root, out):
    stream, expected, metadata, counts = bank()
    results = []
    for label, flags in (('O0', ['-O0']), ('O2', ['-O2']), ('O3', ['-O3']),
                         ('UBSan', ['-O2', '-fsanitize=undefined', '-fno-sanitize-recover=all'])):
        binary = out / ('conversion_' + label)
        build = subprocess.run(['cc', *flags, '-std=c11', '-DG_ROUND84=0',
            str(root / 'experiments/h1701_conversion_driver.c'), '-lm', '-o', str(binary)], text=True, capture_output=True)
        assert build.returncode == 0 and not build.stderr, build.stderr
        run = subprocess.run([str(binary)], input=stream, text=True, capture_output=True)
        actual = run.stdout.splitlines()
        misses = [dict(row=i, expected=x, actual=y) for i, (x, y) in enumerate(zip(expected, actual)) if x != y]
        metadata_matches = run.stderr == metadata
        result = dict(build=label, returncode=run.returncode, expected_rows=len(expected), actual_rows=len(actual),
            misses=misses, metadata_exact=metadata_matches,
            diagnostics=None if metadata_matches else run.stderr,
            binary_sha256=digest(binary), output_sha256=hashlib.sha256(run.stdout.encode()).hexdigest(),
            metadata_sha256=hashlib.sha256(run.stderr.encode()).hexdigest())
        save(out / (label + '.json'), result); results.append(result)
        print(json.dumps({k: result[k] for k in ('build', 'returncode', 'actual_rows', 'metadata_exact')} | dict(misses=len(misses))), flush=True)
    return dict(counts=counts, rows=len(expected), input_sha256=hashlib.sha256(stream.encode()).hexdigest(),
        oracle_sha256=hashlib.sha256(('\n'.join(expected) + '\n').encode()).hexdigest(),
        metadata_oracle_sha256=hashlib.sha256(metadata.encode()).hexdigest(), builds=results)


def certificate():
    cases = []
    for top in range(64):
        shift = 63 - top
        assert top - 16445 == -16382 - shift
        assert shift + (-16382 - shift) - 63 == -16445
        assert (1 << top) << shift == B and ((1 << (top + 1)) - 1) << shift <= MASK
        cases.append(dict(top=top, normalization_shift=shift, internal_exp=-16382 - shift,
            output_exponent=0 if shift else 1, discarded_bits=0))
    assert sum(1 << top for top in range(63)) == B - 1
    # Concrete store negative control: tie with odd truncated low word.
    stored = encode(0, 0, -16383, B + 3)
    rounded = ((B + 3) // 2) + 1
    assert stored == (0, (B + 3) // 2) and stored[1] != rounded
    return dict(zero_field_cases=cases, normalized_input_exp_bounds=[-16445, 16383],
        true_denormal_store_shifts=[1, 63], pseudo_denormal_canonical_exponent=1,
        bypass_argument='Every valid E=0 nonzero input and every normal E<16315 has normalized exp<-68. The unchanged direct tiny header selects the bypass, no predecessor step, sine sign/input magnitude or cosine+1, C1=0. Original raw E/J must remain separately available to the status layer.',
        exactness_argument='Normalization multiplies sig by2^shift while decreasing exp byshift. The subnormal store divides by exactly2^shift, so every discarded bit is zero. Pseudo-denormals have shift0 and store with E=1, preserving numerical value but not raw encoding/class.',
        negative_generic_RN=dict(internal_sign=0, internal_exp=-16383, internal_sig=f'{B+3:016x}',
            truncating_output=f'{stored[0]:04x}:{stored[1]:016x}', nearest_even_output=f'0000:{rounded:016x}'),
        exclusions='Generic correctly rounded underflow, arbitrary internal exponent overflow, unsupported raw architecture semantics without guard, original-class retention inside sf_t, all-input physical behavior, automatic C/compiler verification, whole dispatch and full-state composition.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--timeout-ms', type=int, default=10000)
    args = parser.parse_args(); root, out = args.root.resolve(), args.output_dir.resolve()
    assert not out.exists()
    for path, expected in LOCKS.items():
        assert digest(root / path) == expected, path
    out.mkdir(parents=True); query_dir = out / 'queries'; query_dir.mkdir()
    results = []
    for name, logic, premises, error, wanted in queries():
        row = solve(name, logic, premises, error, query_dir, args.timeout_ms)
        row['expected'] = wanted; results.append(row)
    save(out / 'solver_results.json', results)
    arithmetic = certificate(); compiled = compiled_checks(root, out)
    proved = all(r['z3'] == r['cvc5'] == r['expected'] for r in results)
    tested = all(r['returncode'] == 0 and not r['misses'] and r['metadata_exact'] and r['actual_rows'] == r['expected_rows'] for r in compiled['builds'])
    report = dict(experiment='h1701_conversion_certificate', status='PASS_CONDITIONAL_CONVERSION_CONTRACT' if proved and tested else 'UNRESOLVED_OR_FAILED',
        queries=len(results), z3_counts=dict(Counter(r['z3'] for r in results)), cvc5_counts=dict(Counter(r['cvc5'] for r in results)),
        solvers=dict(z3=z3.get_version_string(), cvc5=cvc5.__version__), arithmetic_certificate=arithmetic, compiled=compiled,
        scope='Pinned helper/header implementation boundary, manual source-to-predicate correspondence plus compiled differential checks; not automatic C/compiler or all-input silicon proof. Software repetitions are not hardware captures.',
        hardware_execution='none', private_ledger_access='none', labels_opened=False, production_default_or_paper_change=False,
        sha256=dict(script=digest(Path(__file__)), driver=digest(root / 'experiments/h1701_conversion_driver.c'), evidence=LOCKS,
            solver_results=digest(out / 'solver_results.json')))
    save(out / 'report.json', report)
    print(json.dumps({k: report[k] for k in ('status', 'queries', 'z3_counts', 'cvc5_counts')}), flush=True)


if __name__ == '__main__':
    main()
