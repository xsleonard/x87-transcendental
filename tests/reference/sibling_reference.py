"""Executable specification of the fixed F2XM1 and FPTAN numerical programs.

All arithmetic is exact Fraction arithmetic except at the named quantizers.
Constants are supplied as exact dyadics by the public ROM loader. This module
does not call the production C implementation, a host transcendental library,
or the historical search models. Unsupported raw encodings are outside this
reference's input contract, rather than assigned invented hardware behavior.
"""
from fractions import Fraction as F
from functools import lru_cache


@lru_cache(maxsize=None)
def power2(exponent):
    return F(1 << exponent) if exponent >= 0 else F(1, 1 << -exponent)


def exponent(value):
    """floor(log2(value)) for a strictly positive rational, without libm."""
    n, d = value.numerator, value.denominator
    e = n.bit_length() - d.bit_length()
    return e - int(n < d << e) if e >= 0 else e - int(n << -e < d)


def quantize(value, bits, mode="rz"):
    """One rounding at an unbounded exponent; mode is rn, rd, ru or rz."""
    value = F(value)
    if not value:
        return value
    negative = value < 0
    step = power2(exponent(abs(value)) - bits + 1)
    scaled = abs(value) / step
    kept, remainder = divmod(scaled.numerator, scaled.denominator)
    denominator = scaled.denominator
    increment = (mode == "rn" and
                 (2 * remainder > denominator or
                  (2 * remainder == denominator and kept % 2 == 1)))
    increment |= bool(remainder) and ((mode == "rd" and negative) or
                                     (mode == "ru" and not negative))
    result = (kept + int(increment)) * step
    return -result if negative else result


def T67(v): return quantize(v, 67)
def N64(v): return quantize(v, 64, "rn")
def M(a, b): return T67(a * b)
def A(a, b): return N64(a + b)
def W(a, b): return T67(a - b)


def decode(se, sig):
    """Finite raw80 value; exponent zero uses effective exponent one."""
    e = max(se & 0x7fff, 1) - 16383 - 63
    return (-1 if se >> 15 else 1) * sig * power2(e)


# The description below records the historical conversion behavior.
# F2XM1 now rounds directly with finish_raw80 before this storage step.
def store(value, zero_sign=0):
    """Encode a rounded carrier, matching the current C storage helper.

    The helper truncates on a subnormal store after significand rounding.
    This is a specification of the current implementation's conversion,
    not a claim of fully validated F2XM1 subnormal hardware rounding.
    """
    if not value:
        return zero_sign << 15, 0
    sign, mag = int(value < 0), abs(value)
    e = exponent(mag)
    if e < -16382:
        return sign << 15, int(mag / power2(-16445))
    if e > 16383:
        return (sign << 15) | 0x7fff, 1 << 63
    return (sign << 15) | (e + 16383), int(mag / power2(e - 63))


def finish(value, mode, zero_sign=0):
    rounded = quantize(value, 64, mode)
    return store(rounded, zero_sign), int(abs(rounded) > abs(value))


def finish_raw80(value, mode, zero_sign=0):
    """Round once at the destination spacing, including native subnormals."""
    if not value:
        return (zero_sign << 15, 0), 0
    sign = int(value < 0)
    step = power2(max(-16445, exponent(abs(value)) - 63))
    scaled = abs(value) / step
    kept, remainder = divmod(scaled.numerator, scaled.denominator)
    denominator = scaled.denominator
    increment = (mode == "rn" and
                 (2 * remainder > denominator or
                  (2 * remainder == denominator and kept % 2 == 1)))
    increment |= bool(remainder) and ((mode == "rd" and sign) or
                                     (mode == "ru" and not sign))
    rounded = (-1 if sign else 1) * (kept + int(increment)) * step
    return store(rounded, sign), int(increment)


def f2xm1_long(x, constants):
    """L is zero-based: L[0] through L[10] are the eleven literals."""
    L, ln2 = constants["F2_LONG"], constants["F2_LN2"]
    z = M(ln2, x)
    u = M(z, N64(ln2 * x))
    odd, even = M(u, L[9]), M(u, L[10])
    for i in (7, 5, 3, 1):
        odd, even = A(odd, L[i]), A(even, L[i + 1])
        if i != 1:
            odd, even = M(u, odd), M(u, even)
    odd, even = N64(u * odd), N64(u * even)
    odd, even = M(z, odd), M(u, even)
    correction = A(M(u, L[0]), A(odd, even))
    return z + correction


def f2xm1_table(x, constants):
    K, ln2 = constants["F2_SHORT"], constants["F2_LN2"]
    e = exponent(abs(x))
    lane = int(abs(x) / power2(e) * 16) - 16
    index = (32 if x < 0 else 0) + (16 if e == -2 else 0) + lane
    numerator = 33 + 2 * lane if e == -2 else 66 + 4 * lane
    anchor = F((-1 if x < 0 else 1) * numerator, 128)
    z = N64(ln2 * N64(x - anchor))
    u = M(z, z)
    even = A(M(u, K[4]), K[2])
    even = A(M(u, even), K[0])
    even = A(z, M(u, even))
    odd = A(M(u, K[5]), K[3])
    odd = A(M(u, odd), K[1])
    odd = M(z, M(u, odd))
    lookup = constants["F2_TABLE"][index]
    return lookup + M(A(lookup, F(1)), A(even, odd))


def reduce_angle(x):
    """Exact centered reduction with the 66-bit pi/2 divisor."""
    boundary = F(0xc90fdaa22168c234) * power2(-64)
    if abs(x) < boundary:
        return x, 0
    divisor = 0x3243f6a8885a308d3
    dividend = abs(x) * power2(65)
    assert dividend.denominator == 1
    q, rem = divmod(dividend.numerator, divisor)
    q += int(2 * rem > divisor)  # Odd divisor excludes a halfway tie.
    residual = (dividend - q * divisor) * power2(-65)
    return (-residual, -q) if x < 0 else (residual, q)


def horner(square, coefficients):
    """Coefficients are ascending powers; every product is cut first."""
    value = coefficients[-1]
    for coefficient in reversed(coefficients[:-1]):
        value = A(M(value, square), coefficient)
    return value


def fptan_polynomial(r, constants):
    u = M(r, r)
    p = horner(u, constants["S6"])
    q = horner(u, constants["C6"])
    sine = T67(r + M(r, N64(u * p)))
    cosine = T67(1 + M(u, q))
    return sine, cosine


def fptan_table(r, constants):
    if r < F(1, 2):
        b = 18 + 4 * int(16 * (r - F(1, 4)))
    else:
        b = 36 + 8 * min(2, int(8 * (r - F(1, 2))))
    a = r - F(b, 64)
    u = M(a, a)
    S4 = list(constants["S4"])
    S4[3] -= power2(-25)  # Fixed P6 adjustment to the P5 coefficient.
    p, q = horner(u, S4), horner(u, constants["C4"])
    v = A(a, M(M(p, u), a))
    w = N64(q * u)
    ts, tc = constants["TABLE"][b]
    denominator_partial = W(M(-ts, -v), M(tc, w))
    numerator_partial = W(M(tc, -v), M(ts, w))
    return W(ts, numerator_partial), W(tc, denominator_partial)


def fptan_ratio(x, constants):
    residual, quadrant = reduce_angle(x)
    r = abs(residual)
    if r < F(1, 4):
        sine, cosine = fptan_polynomial(r, constants)
    else:
        sine, cosine = fptan_table(r, constants)
    if residual < 0:
        sine = -sine
    sine, cosine = ((sine, cosine), (cosine, -sine),
                    (-sine, -cosine), (-cosine, sine))[quadrant % 4]
    return sine / cosine


def evaluate(instruction, se, sig, mode, constants):
    """Return (raw result, pushed raw value or None, C1, C2).

    Contract: ordinary raw80 values, subnormals/pseudo-denormals, signed
    zeros, infinities and valid NaNs. No arbitrary stack/exception emulation.
    The caller validates controls; unsupported encodings raise ValueError.
    """
    if instruction not in ("F2XM1", "FPTAN") or mode not in ("rn", "rd", "ru", "rz"):
        raise ValueError("Invalid instruction or rounding mode")
    e = se & 0x7fff
    if not (0 <= se < 65536 and 0 <= sig < 1 << 64):
        raise ValueError("Invalid raw80 fields")
    if e and not (sig >> 63):
        raise ValueError("Unsupported raw80 encoding outside this contract")
    raw = (se, sig)
    one = (0x3fff, 1 << 63)
    if e == 0x7fff:
        if sig != 1 << 63:
            raw = se, sig | (1 << 62)
        elif instruction == "FPTAN":
            raw = 0xffff, 0xc000000000000000
        return raw, raw if instruction == "FPTAN" else None, 0, 0
    x = decode(se, sig)
    if not sig:
        return raw, one if instruction == "FPTAN" else None, 0, 0
    if instruction == "FPTAN":
        if abs(x) >= power2(63):
            return raw, None, 0, 1
        if abs(x) < power2(-68):
            return store(x), one, 0, 0
        result, c1 = finish(fptan_ratio(x, constants), mode)
        return result, one, c1, 0
    if abs(x) > 1:
        return store(x), None, 0, 0  # Empirical out-of-domain policy.
    if abs(x) == 1:
        return (one if x > 0 else (0xbffe, 1 << 63)), None, 0, 0
    if abs(x) < power2(-68):
        value = constants["F2_LN2"] * x
    elif abs(x) < F(1, 4):
        value = f2xm1_long(x, constants)
    else:
        value = f2xm1_table(x, constants)
    result, c1 = finish_raw80(value, mode, se >> 15)
    return result, None, c1, 0
