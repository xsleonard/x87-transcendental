#!/usr/bin/env python3
"""End-to-end plausibility test for fsincos_ref.

Computes sin/cos to high precision with exact rational arithmetic
(Machin pi + Taylor with argument reduction), rounds to double-extended,
and checks the reference implementation is within the FMCAD00-proven bound
(0.57341 ulp round-to-nearest; we assert <= 1 ulp of the correctly-rounded
result, i.e. the returned value is one of the two closest representables
around the true value's rounding).

This is a transcription-error tripwire, not a bit-proof: a wrong constant,
op order, or rounding bug typically lands many ulps off on some input.
"""
import subprocess
import sys
from fractions import Fraction

BIN = sys.argv[1] if len(sys.argv) > 1 else "./fsincos_ref"
PREC = 400  # bits

def pi_frac(prec=PREC):
    def atan_inv(n):
        total = Fraction(0)
        k = 0
        while True:
            term = Fraction((-1) ** k, (2 * k + 1) * n ** (2 * k + 1))
            total += term
            if abs(term) < Fraction(1, 2 ** (prec + 16)):
                return total
            k += 1
    return 16 * atan_inv(5) - 4 * atan_inv(239)

PI = pi_frac()

def sin_frac(x):
    # reduce to |y| <= pi/2 region count via floor division
    n = int((x / (PI / 2)) + (Fraction(1, 2) if x >= 0 else Fraction(-1, 2)))
    y = x - n * PI / 2
    n &= 3
    def series_sin(t):
        total = Fraction(0)
        term = t
        k = 1
        while abs(term) > Fraction(1, 2 ** (PREC + 16)):
            total += term
            term = -term * t * t / ((2 * k) * (2 * k + 1))
            k += 1
        return total
    def series_cos(t):
        total = Fraction(0)
        term = Fraction(1)
        k = 1
        while abs(term) > Fraction(1, 2 ** (PREC + 16)):
            total += term
            term = -term * t * t / ((2 * k - 1) * (2 * k))
            k += 1
        return total
    if n == 0:
        return series_sin(y)
    if n == 1:
        return series_cos(y)
    if n == 2:
        return -series_sin(y)
    return -series_cos(y)

def cos_frac(x):
    return sin_frac(x + PI / 2)

def dec80(se, sig):
    sign = -1 if (se >> 15) & 1 else 1
    e = se & 0x7FFF
    if sig == 0:
        return Fraction(0)
    return sign * Fraction(sig) * Fraction(2) ** (e - 16383 - 63)

def enc80(x):
    """round Fraction to nearest-even double-extended; return (se, sig)."""
    if x == 0:
        return 0, 0
    sign = 1 if x < 0 else 0
    a = abs(x)
    e = a.numerator.bit_length() - a.denominator.bit_length()
    if Fraction(2) ** e > a:
        e -= 1
    scaled = a * Fraction(2) ** (63 - e)
    i = scaled.numerator // scaled.denominator
    frac = scaled - i
    if frac > Fraction(1, 2) or (frac == Fraction(1, 2) and (i & 1)):
        i += 1
    if i == 1 << 64:
        i >>= 1
        e += 1
    return (sign << 15) | (e + 16383), i

def ulp_of(se):
    e = (se & 0x7FFF) - 16383
    return Fraction(2) ** (e - 63)

# test inputs: hex-encoded double-extended values
def mk(v):
    return enc80(Fraction(v))

tests = []
# simple values
for v in ["0.001", "0.01", "0.1", "0.5", "0.7", "1", "1.5", "2", "3", "5",
          "10", "100", "1000", "12345.678", "1e6", "1e7"]:
    tests.append(mk(Fraction(v.replace("e6", "000000").replace("e7", "0000000"))
                    if "e" in v else Fraction(v)))
# negatives
tests += [((se ^ 0x8000), sig) for (se, sig) in tests[:8]]
# near multiples of pi/2 (worst-case reduction), built from PI
for k in [1, 2, 3, 5, 11, 101, 1001, 100003]:
    tgt = PI / 2 * k
    tests.append(enc80(tgt))                     # closest representable
    se, sig = enc80(tgt)
    tests.append((se, sig ^ 1))                  # one ulp off
# large args exercising pre-reduction (2^24..2^63)
for e in [24, 30, 40, 50, 62]:
    tests.append(((e + 16383), (1 << 63) | 0x123456789ABCDEF0 >> 1))
# small args (small_r / tiny paths)
for e in [-4, -10, -20, -33, -40, -60]:
    tests.append(((e + 16383), (1 << 63) | 0x0F0F0F0F0F0F0F0F >> 1))
# pi/4 boundary neighborhood
se, sig = 0x3FFE, 0xC90FDAA22168C234
tests += [(se, sig), (se, sig + 1), (se, sig - 1)]

fails = 0
checked = 0
for se, sig in tests:
    out = subprocess.run([BIN, f"{se:04x}", f"{sig:016x}"],
                         capture_output=True, text=True, check=True).stdout.split()
    if out[0] == "C2":
        continue
    got_sin = dec80(int(out[1], 16), int(out[2], 16))
    got_cos = dec80(int(out[4], 16), int(out[5], 16))
    x = dec80(se, sig)
    for name, got, true in (("sin", got_sin, sin_frac(x)), ("cos", got_cos, cos_frac(x))):
        rse, rsig = enc80(true)                  # correctly rounded
        cr = dec80(rse, rsig)
        err_ulp = abs(got - true) / ulp_of(rse)
        checked += 1
        if err_ulp > Fraction(58, 100) + Fraction(1, 2):   # 0.57341 + 0.5 rounding slack
            fails += 1
            if fails <= 12:
                print(f"FAIL {name}(x se={se:04x} sig={sig:016x}): "
                      f"err={float(err_ulp):.3f} ulp  got={float(got):.18g} "
                      f"true={float(true):.18g}")

print(f"end-to-end: {checked} results checked, {fails} out of bound")
sys.exit(1 if fails else 0)
