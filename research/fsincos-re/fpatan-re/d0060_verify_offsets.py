"""Compare the bounded C enumerator with exact Python and sanitizer builds."""
import argparse
from collections import Counter
import json
from pathlib import Path
import random
import subprocess
import time

from compressed_guard import digest
from d0049_algebraic_tie_preimages import domains
from d0056_outer_boundary_lattice import parameters, candidate_offsets
from d0060_fast_offsets import FastOffsets
from prepare import save

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--optimized', type=Path, required=True)
    parser.add_argument('--sanitized', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(exist_ok=False)
    pins = {str(p): digest(p) for p in (args.library, args.optimized, args.sanitized)}
    for name in ('d0060_verify_offsets.py', 'd0060_boundary_offsets.c', 'd0060_fast_offsets.py',
                 'd0056_outer_boundary_lattice.py'):
        pins[str(HERE / name)] = digest(HERE / name)
    fast = FastOffsets(args.library.resolve())
    rng = random.Random('d0060-exact-unsigned-enumeration')
    cases = []
    for i in range(2500):
        n = rng.randrange(300)
        modulus = rng.randrange(1, 1 << rng.randrange(1, 109))
        slope, intercept = rng.randrange(modulus), rng.randrange(modulus)
        low, high = rng.randrange(modulus + 1), rng.randrange(modulus + 1)
        cases.append((n, modulus, slope, intercept, low, high))
    for modulus in (1, 2, 1 << 64, (1 << 107) + 1, (1 << 108) - 1):
        for n in (0, 1, 31, 32, 33, (1 << 20) - 1):
            cases.extend((n, modulus, slope, modulus - 1, 0, 0) for slope in (0, 1, modulus - 1))
    for node in (0, 1):
        d = domains(node, -9)[0]
        p = parameters(node, d)
        for _ in range(100):
            n = 1 << 20
            start = rng.randrange(d['count'] - n)
            slope = (2 * p['alpha'] * start + p['beta']) % p['modulus']
            intercept = (p['alpha'] * start * start + p['beta'] * start + p['gamma']) % p['modulus']
            high = p['error_high'] + p['alpha'] * (n - 1) ** 2
            cases.append((n, p['modulus'], slope, intercept, p['error_low'], high))
    inputs, expected = args.out / 'inputs.txt', args.out / 'expected.txt'
    counts = Counter()
    started = time.monotonic()
    with inputs.open('x') as source, expected.open('x') as target:
        for case in cases:
            result = list(candidate_offsets(*case))
            actual = fast.offsets(*case)
            assert actual == result
            source.write(str(case[0]) + ' ' + ' '.join(f'{value:x}' for value in case[1:]) + '\n')
            target.write(' '.join(map(str, [len(result)] + result)) + '\n')
            counts['cases'] += 1
            counts['selected_indices'] += len(result)
    comparison_seconds = time.monotonic() - started
    for label, binary in (('optimized', args.optimized), ('sanitized', args.sanitized)):
        output, errors = args.out / f'{label}.txt', args.out / f'{label}.stderr'
        with inputs.open() as source, output.open('x') as target, errors.open('x') as error:
            run = subprocess.run([str(binary.resolve())], stdin=source, stdout=target, stderr=error)
        assert run.returncode == 0 and errors.stat().st_size == 0
        assert digest(output) == digest(expected)
        pins[str(output)] = digest(output)
        pins[str(errors)] = digest(errors)
    for path in (inputs, expected):
        pins[str(path)] = digest(path)
    assert all(digest(Path(path)) == sha for path, sha in pins.items())
    save(args.out / 'REPORT.json', dict(status='PASS_EXACT_OFFSETS_PYTHON_C_SANITIZER',
        counts=counts, comparison_seconds=comparison_seconds, evidence_sha256=pins,
        arithmetic_bounds='n<=2^20; 0<modulus<2^108; modulus*(n+1)<2^128; coefficients reduced modulo modulus; margins clamped to modulus.',
        hardware_executed=False, numerical_model_changed=False, goal_complete=False))
    print('PASS', json.dumps(counts), comparison_seconds, flush=True)


if __name__ == '__main__':
    main()
