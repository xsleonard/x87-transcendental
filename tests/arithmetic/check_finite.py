"""Independent exact Fraction oracle for bounded finite arithmetic (no GMP).

The oracle quantizes a mathematical rational directly with integer divmod;
it does not implement the C accumulator, sticky window or quotient algorithm.
"""
from collections import Counter
from fractions import Fraction as F
import hashlib
import json
import random
import subprocess
import sys


def pow2(e):
    return F(1 << e) if e >= 0 else F(1, 1 << -e)


def exponent(x):
    x = abs(x)
    if not x:
        return -1
    e = x.numerator.bit_length() - x.denominator.bit_length()
    return e - (x < pow2(e))


def quantize(x, step, rc):
    unit = pow2(step)
    scaled = abs(x) / unit
    q, r = divmod(scaled.numerator, scaled.denominator)
    inc = bool(r) and (rc == 1 and x < 0 or rc == 2 and x > 0 or
                      rc == 0 and (2*r > scaled.denominator or
                                   2*r == scaled.denominator and q % 2))
    return (-1 if x < 0 else 1) * (q + inc) * unit, int(inc)


def rounded(x, bits, rc):
    return quantize(x, exponent(x) - bits + 1, rc)[0] if x else F(0)


def canonical(x):
    if not x:
        return ('V', 0, 0, 0)
    n, d = abs(x.numerator), x.denominator
    assert d & (d-1) == 0
    zeros = (n & -n).bit_length()-1
    return ('V', int(x < 0), zeros-(d.bit_length()-1), n >> zeros)


def encode(x, rc, tiny=0, adjust=False):
    if adjust and tiny:
        x *= pow2(24576)
    sign = int(x < 0)
    e = max(exponent(x), -16382) if x else -16382
    q, c1 = quantize(x, e-63, rc)
    if q and exponent(q) > 16383:
        inf = rc == 0 or rc == 1 and sign or rc == 2 and not sign
        return ('R', (sign << 15) | (0x7fff if inf else 0x7ffe),
                1 << 63 if inf else (1 << 64)-1, int(inf), tiny)
    e = max(exponent(q), -16382) if q else -16382
    sig = int(abs(q) / pow2(e-63))
    return ('R', (sign << 15) | (e+16383 if sig >= 1 << 63 else 0), sig, c1, tiny)


def main():
    rng = random.Random(0xF1872026)
    rows, expected = [], []
    counts = Counter()

    def check(op, a, b=(0, 0), bits=67, rc=0):
        # Operand tuples hold signed integer magnitude and binary exponent.
        n, e = a
        m, f = b
        x, y = n*pow2(e), m*pow2(f)
        rows.append(f'{op} {bits} {rc} {int(n<0)} {e} {abs(n):x} {int(m<0)} {f} {abs(m):x}')
        if op == 'add': want = canonical(rounded(x+y, bits, rc))
        elif op == 'mul': want = canonical(x*y)
        elif op == 'div': want = canonical(rounded(x/y, bits, rc))
        elif op == 'round': want = canonical(rounded(x, bits, rc))
        elif op == 'cmp': want = ('I', (x > y)-(x < y))
        elif op == 'ratio': want = ('I', exponent(x/y))
        elif op == 'floor': want = ('I', int(x))
        elif op == 'scale': want = canonical(x*pow2(f))
        elif op == 'decode':
            want = canonical((-1 if e & 0x8000 else 1)*n*pow2((e & 0x7fff or 1)-16383-63))
        elif op == 'encode': want = encode(x, rc)
        elif op == 'sum':
            tiny = int(bool(x+y) and exponent(x+y) < -16382)
            want = encode(x+y, rc, tiny, not bits & 16)
        else: raise AssertionError(op)
        expected.append(want)
        counts[op] += 1

    # Word-boundary widths, exact cancellation, carry, both signs and a tail
    # falling exactly at or on either side of the 320-bit window boundary.
    for width in (1, 63, 64, 65, 67, 127, 128, 129, 191, 192, 255, 256):
        n = (1 << width)-1
        for gap in (0, 1, 63, 64, 65, 127, 128, 191, 192, 255, 256, 318, 319, 320, 321, 32768):
            for sign in (-1, 1):
                a, b = (n, -width), (sign*n, -width-gap)
                check('cmp', a, b)
                for bits in (1, 53, 64, 67, 128):
                    for rc in range(5):
                        check('add', a, b, bits, rc)
                        check('add', (-n, -width), (-sign*n, -width-gap), bits, rc)
        for rc in range(5):
            check('add', (n, 0), (-n+1, 0), 128, rc)
            check('round', (n, -width), bits=64, rc=rc)

    # Exactly halfway and immediate dyadic neighbors, for even/odd quotients.
    for e in (0, 1, 2, 0x3fff, 0x7ffe, 0x8000, 0x8001, 0xbfff, 0xfffe):
        for n in (0, 1, 2, (1 << 63)-1, 1 << 63, (1 << 64)-1):
            check('decode', (n, e))
    for n in (0, 1, 3, (1 << 64)-1):
        for e in (0, -1, -63, -64, -128):
            check('floor', (n, e))
    for bits in (1, 24, 53, 64, 67, 128):
        for odd in (0, 1):
            for delta in (-1, 0, 1):
                n = ((1 << (bits-1)) + odd)*8 + 4 + delta
                for sign in (-1, 1):
                    for rc in range(5):
                        check('round', (sign*n, -3), bits=bits, rc=rc)
                        if n.bit_length() <= 128:
                            check('div', (sign*n, 0), (8, 0), bits, rc)

    # Cancellation exposes low bits of full 256-bit inputs; unrelated bounded
    # random operands exercise multiplication and exact division remainders.
    for i in range(4000):
        wa, wb = rng.choice((1, 64, 67, 127, 128)), rng.choice((1, 64, 67, 127, 128))
        n = (rng.getrandbits(wa) | 1) * rng.choice((-1, 1))
        m = (rng.getrandbits(wb) | 1) * rng.choice((-1, 1))
        e, f = rng.randint(-33000, 33000), rng.randint(-33000, 33000)
        bits, rc = rng.choice((1, 24, 53, 64, 67, 128)), rng.randrange(5)
        a, b = (n, e), (m, f)
        for op in ('mul', 'div', 'ratio', 'cmp', 'add'):
            check(op, a, b, bits, rc)
        check('scale', a, (0, f))
        check('floor', (abs(n), -wa-1))
        if i < 500:
            n = rng.getrandbits(256) | (1 << 255)
            check('add', (n, e), (-n+rng.randrange(-8, 9), e), bits, rc)

    # Final subnormal grid, normal/overflow boundaries and unmasked scaling.
    for e in (-33000, -16447, -16446, -16445, -16383, -16382, 16382, 16383, 16384, 16400):
        for n in (1, 3, (1 << 64)-1, (1 << 64)+1, (1 << 67)-1, (1 << 131)-1):
            for sign in (-1, 1):
                for rc in range(4):
                    a = (sign*n, e-n.bit_length()+1)
                    check('encode', a, rc=rc)
                    for masks in (0, 63):
                        for tail in (-1, 1):
                            check('sum', a, (tail, e-33000), masks, rc)
    # A leading retained bit can disappear across a borrow (1 - tiny).
    for e in (-16382, 0, 16384):
        for sign in (-1, 1):
            for rc in range(4):
                for masks in (0, 63):
                    check('sum', (sign, e), (-sign, e-32768), masks, rc)

    request = '\n'.join(rows)+'\n'
    p = subprocess.run([sys.argv[1]], input=request, text=True, capture_output=True)
    if p.returncode:
        raise AssertionError(('driver failed', p.returncode, p.stderr, len(p.stdout.splitlines())))
    lines = p.stdout.splitlines()
    assert len(lines) == len(expected), (len(lines), len(expected))
    for row, line, want in zip(rows, lines, expected):
        fields = line.split()
        if fields[0] == 'V': got = ('V', int(fields[1]), int(fields[2]), int(fields[3], 16))
        elif fields[0] == 'R': got = ('R', int(fields[1], 16), int(fields[2], 16), int(fields[3]), int(fields[4]))
        else: got = ('I', int(fields[1]))
        assert got == want, (row, got, want)
    print(json.dumps(dict(status='PASS', comparisons=len(rows), counts=counts,
                          input_sha256=hashlib.sha256(request.encode()).hexdigest(), seed='0xF1872026')))


if __name__ == '__main__':
    main()
