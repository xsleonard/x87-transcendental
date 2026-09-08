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
