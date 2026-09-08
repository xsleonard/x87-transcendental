# Skylake FPATAN: programmer's pseudocode

This specifies the validated V7 numerical program, including raw80 classes,
all four x87 rounding modes, C1 and masked arithmetic exception flags. It is
not a call to mathematically correctly rounded `atan2`, a physical microcode
decode, or a claim of exhaustive agreement with every possible raw80 input.
The [paper](paper/skylake-fpatan.tex) uses these exact code blocks in its
appendix. The production implementation is [fpatan_candidate.c](fpatan_candidate.c).

The blocks are executable reference pseudocode using exact Python `Fraction`
arithmetic. No host floating-point operation is used. `ROM` is the dictionary
of exact constants printed in the paper's constant appendix: each entry is
`(-1)^sign * int(significand_hex, 16) * 2^scale`. These are the 44 unchanged
P5 literals in the C implementation; no data from failing inputs is included.
The C executable itself requires neither Python nor an external data file.

## 1. Raw80 values, classification and exact arithmetic

`Raw80(se, sig)` stores the sign/exponent word and the 64-bit significand.
The explicit integer bit is part of `sig`. `decode` is used only for finite
values; unsupported encodings are rejected before numerical evaluation.

```python
from fractions import Fraction as Q
from typing import NamedTuple

class Raw80(NamedTuple):
    se: int
    sig: int

def pow2(e):
    return Q(1 << e) if e >= 0 else Q(1, 1 << (-e))

def floor_log2(v):
    assert v > 0
    e = v.numerator.bit_length() - v.denominator.bit_length()
    return e - int(v < pow2(e))

def decode(raw):
    exponent = max(raw.se & 0x7fff, 1) - 16383 - 63
    magnitude = raw.sig * pow2(exponent)
    return -magnitude if raw.se & 0x8000 else magnitude

def classify(raw):
    exponent = raw.se & 0x7fff
    integer_bit = raw.sig >> 63
    if exponent == 0:
        if raw.sig == 0:
            return 'zero'
        return 'pseudo' if integer_bit else 'denormal'
    if not integer_bit:
        return 'unsupported'
    if exponent != 0x7fff:
        return 'normal'
    if raw.sig == (1 << 63):
        return 'infinity'
    return 'qnan' if raw.sig & (1 << 62) else 'snan'
```

## 2. Internal rounding and final raw80 encoding

RN is nearest/even; RD is toward negative infinity; RU is toward positive
infinity; RZ is toward zero. Internal `T` has no exponent-range limit.
`pack_angle` applies the architectural subnormal spacing and preserves the
sign when a negative nonzero angle rounds to zero. It is an angle encoder,
not a general overflow-handling floating-point conversion routine.

```python
def round_at_step(v, step, rc):
    scaled = abs(v) / step
    quotient, remainder = divmod(scaled.numerator, scaled.denominator)
    increment = False
    if remainder != 0:
        if rc == 'RN':
            twice = 2 * remainder
            increment = (twice > scaled.denominator or
                         (twice == scaled.denominator and quotient % 2 == 1))
        elif rc == 'RD':
            increment = v < 0
        elif rc == 'RU':
            increment = v > 0
        else:
            assert rc == 'RZ'
    magnitude = (quotient + int(increment)) * step
    return -magnitude if v < 0 else magnitude

def T(v, bits):
    if v == 0:
        return Q(0)
    step = pow2(floor_log2(abs(v)) - bits + 1)
    return round_at_step(v, step, 'RZ')

def N64(v):
    if v == 0:
        return Q(0)
    return round_at_step(v, pow2(floor_log2(abs(v)) - 63), 'RN')

def pack_angle(v, rc, zero_sign=0):
    sign = int(v < 0) if v != 0 else zero_sign
    exponent = max(floor_log2(abs(v)), -16382) if v != 0 else -16382
    rounded = round_at_step(v, pow2(exponent - 63), rc)
    c1 = int(abs(rounded) > abs(v))
    if rounded == 0:
        return Raw80(sign << 15, 0), c1
    exponent = max(floor_log2(abs(rounded)), -16382)
    significand = abs(rounded) / pow2(exponent - 63)
    assert significand.denominator == 1
    significand = int(significand)
    assert 0 < significand < (1 << 64)
    field = 0 if significand < (1 << 63) else exponent + 16383
    return Raw80((sign << 15) | field, significand), c1
```

## 3. Two interleaved polynomial chains

`M` and `W` retain 67 bits; `A` rounds to nearest/even at 64 bits. The square
has asymmetric operand widths. Every unmarked operation is exact. In
particular, the final `z + tail` is not automatically cut to 67 bits here.

```python
def M(a, b):
    return T(a * b, 67)

def A(a, b):
    return N64(a + b)

def W(a, b):
    return T(a + b, 67)

def kernel(z, table):
    square = N64(z * T(z, 64))
    fourth = M(square, square)
    if table:
        even = W(ROM[114], M(fourth, ROM[116]))
        odd = A(ROM[115], M(fourth, ROM[117]))
    else:
        odd = W(ROM[119], M(fourth, A(ROM[121], M(fourth, ROM[123]))))
        even = W(ROM[118], M(fourth, A(ROM[120], M(fourth, ROM[122]))))
    correction = A(M(square, odd), even)
    tail = M(M(z, square), correction)
    return z + tail
```

## 4. Finite reduction, dispatch and quadrant restoration

The tiny branch is strict at `2^-40`; the direct branch includes `3/64`.
The exact integer ceiling implements nearest table selection with ties to
the lower cell. Small-integer products in the reduction are completed before
their sum or difference is cut. The table result and a result about to undergo
quadrant restoration have different intermediate-cut requirements.

```python
def finite_angle(y_raw, x_raw):
    a, b = abs(decode(y_raw)), abs(decode(x_raw))
    swapped = a > b
    if swapped:
        a, b = b, a
    ratio = a / b
    if ratio < pow2(-40):
        angle = T(ratio, 67)
    elif ratio <= Q(3, 64):
        angle = kernel(T(ratio, 67), table=False)
    else:
        shifted = 32 * ratio - Q(1, 2)
        n = -((-shifted.numerator) // shifted.denominator)
        assert 2 <= n <= 32
        center = Q(n, 32)
        numerator = T(a - center * b, 67)
        denominator = T(b + center * a, 67)
        z = T(numerator / denominator, 67)
        angle = T(kernel(z, table=True), 67) + ROM[124 + n]
    x_negative = bool(x_raw.se & 0x8000)
    if swapped or x_negative:
        angle = T(angle, 67)
    if swapped:
        angle = ROM[20] + angle if x_negative else ROM[20] - angle
    elif x_negative:
        angle = ROM[19] - angle
    return -angle if y_raw.se & 0x8000 else angle
```

## 5. Masked architectural wrapper

Input y is ST(1), x is ST(0); the architectural instruction pops once.
The returned tuple is `(raw_result, C1, exception_flags, pre_load_flags)`.
Flag masks are IE=1, DE=2, ZE=4, OE=8, UE=16 and PE=32. The last field is zero
under the tested `FNINIT; FLDCW; FLD80 y; FLD80 x` capture contract. This
wrapper does not emulate stack faults, unmasked traps or arbitrary prior FPU
state. Undefined C0/C2/C3 are not predicted.

```python
def fpatan(y, x, rc, pc=64):
    assert rc in ('RN', 'RD', 'RU', 'RZ')
    assert pc in (24, 53, 64)  # Accepted control, not a kernel selector.
    assert all(0 <= r.se <= 0xffff and 0 <= r.sig < (1 << 64)
               for r in (y, x))
    ky, kx = classify(y), classify(x)
    classes = (ky, kx)
    if 'unsupported' in classes:
        return Raw80(0xffff, 0xc000000000000000), 0, 1, 0
    nans = [(raw, kind) for raw, kind in ((y, ky), (x, kx))
            if kind in ('qnan', 'snan')]
    if nans:
        quiet = [raw for raw, kind in nans if kind == 'qnan']
        pool = quiet if quiet else [raw for raw, kind in nans]
        chosen = max(pool, key=lambda raw: (raw.sig, -raw.se))
        result = Raw80(chosen.se, chosen.sig | (1 << 62))
        return result, 0, int('snan' in classes), 0
    flags = 2 if any(k in ('denormal', 'pseudo') for k in classes) else 0
    sy, sx = y.se >> 15, x.se >> 15
    if ky == 'zero':
        angle = ROM[19] if sx else Q(0)
    elif kx == 'zero':
        angle = ROM[20]
    elif ky == 'infinity':
        if kx == 'infinity':
            angle = (3 if sx else 1) * ROM[20] / 2
        else:
            angle = ROM[20]
    elif kx == 'infinity':
        angle = ROM[19] if sx else Q(0)
    else:
        angle = finite_angle(y, x)
        result, c1 = pack_angle(angle, rc)
        flags |= 32
        if abs(angle) < pow2(-16382):
            flags |= 16  # Tininess before final rounding.
        return result, c1, flags, 0
    angle = -angle if sy else angle
    result, c1 = pack_angle(angle, rc, zero_sign=sy)
    if angle != 0:
        flags |= 32
    return result, c1, flags, 0
```

## Rounding-control example

For y=x=1 (`3fff:8000000000000000` for both operands), RN and RU return
`3ffe:c90fdaa22168c235` with C1=1; RD and RZ return
`3ffe:c90fdaa22168c234` with C1=0. PE is set and the other arithmetic
exception flags are clear. The result is the same for PC24, PC53 and PC64.

The internal RN64/CHOP67 operators are fixed parts of the reconstructed
program; they do not inherit the caller's RC or PC. See
[validation](../../docs/validation.md) for the test scope and data requirements.
