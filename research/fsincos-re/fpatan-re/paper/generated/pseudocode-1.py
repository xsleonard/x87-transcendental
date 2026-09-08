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
