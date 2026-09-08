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
