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
