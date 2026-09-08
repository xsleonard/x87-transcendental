#!/usr/bin/env python3
"""Task 3 (SESSION-GUIDE): enumerate the special/boundary operand
classes for the FSIN/FCOS exhaustive-insurance sweep.

Emits "se sig" hex lines (x87 80-bit: se = sign|15-bit exponent, sig =
explicit-integer-bit significand) with a leading "# class" comment
stream on stderr kept OFF stdout so the file feeds the capture harness
directly.  Deterministic — no RNG.

Classes: zeros, denormals, pseudo-denormals, infinities, qNaN/sNaN
payload families, pseudo-NaN/pseudo-infinity (integer bit 0),
unnormals, boundary exponents, the |x| >= 2^63 C2 edge (dense),
near-identity path edges, and near-(k*pi/2) cancellation operands.
"""
import sys

B63 = (1 << 63)
M63 = B63 - 1
M64 = (1 << 64) - 1

# pi to 384 fractional hex bits
PI_HEX = ("3243F6A8885A308D313198A2E03707344A4093822299F31D0082EFA98"
          "EC4E6C89452821E638D01377BE5466CF34E90C6CC0AC29B7C97C50DD")
PI_NUM = int(PI_HEX, 16)          # pi * 16^(len-1)
PI_SCALE = 4 * (len(PI_HEX) - 1)  # pi = PI_NUM / 2^PI_SCALE


def field_patterns(width):
    """structured payload patterns for a bit-field of `width` bits"""
    s = set()
    for k in range(width):
        s.add(1 << k)
    for k in range(1, width + 1):
        s.add((1 << k) - 1)
    full = (1 << width) - 1
    for k in range(width):
        s.add(full ^ ((1 << k) - 1))
    s.add(0x5555555555555555 & full)
    s.add(0xAAAAAAAAAAAAAAAA & full)
    s.add(0x3333333333333333 & full)
    s.add(0x0F0F0F0F0F0F0F0F & full)
    s.discard(0)
    return sorted(s)


def emit(rows, se, sig, cls):
    rows.append((se, sig, cls))
    rows.append((se | 0x8000, sig, cls + "-neg"))


def main():
    rows = []
    # A. zeros
    emit(rows, 0x0000, 0, "zero")
    # B. denormals (exp 0, int bit 0)
    for p in field_patterns(63):
        emit(rows, 0x0000, p, "denormal")
    # C. pseudo-denormals (exp 0, int bit 1)
    emit(rows, 0x0000, B63, "pseudo-denormal")
    for p in field_patterns(63):
        emit(rows, 0x0000, B63 | p, "pseudo-denormal")
    # D. infinities
    emit(rows, 0x7fff, B63, "infinity")
    # E. quiet NaNs (int bit 1, quiet bit 1)
    emit(rows, 0x7fff, 0xC000000000000000, "qnan-indefinite")
    for p in field_patterns(62):
        emit(rows, 0x7fff, 0xC000000000000000 | p, "qnan")
    # F. signaling NaNs (int bit 1, quiet bit 0, payload != 0)
    for p in field_patterns(62):
        emit(rows, 0x7fff, B63 | p, "snan")
    # G. pseudo-NaN / pseudo-infinity (exp 7fff, int bit 0)
    emit(rows, 0x7fff, 0, "pseudo-inf")
    for p in field_patterns(63):
        emit(rows, 0x7fff, p, "pseudo-nan")
    # H. unnormals (0 < exp < 7fff, int bit 0)
    for e in (0x0001, 0x0002, 0x2000, 0x3ffe, 0x3fff, 0x403e, 0x7ffe):
        for s in (0, 1, 0x4000000000000000, 0x7fffffffffffffff):
            emit(rows, e, s, "unnormal")
    # I. boundary-exponent normals x significand corners
    exps = (0x0001, 0x0002, 0x3fbe, 0x3fbf, 0x3fc0, 0x3fdd, 0x3fde,
            0x3fdf, 0x3fe0, 0x3ff0, 0x3ffb, 0x3ffc, 0x3ffd, 0x3ffe,
            0x3fff, 0x4000, 0x4001, 0x403c, 0x403d, 0x403e, 0x403f,
            0x7ffd, 0x7ffe)
    sigs = (0x8000000000000000, 0x8000000000000001, 0x8000000000000002,
            0xbfffffffffffffff, 0xc000000000000000, 0xb504f333f9de6484,
            0xb504f333f9de6485, 0xc90fdaa22168c234, 0xc90fdaa22168c235,
            0xc90fdaa22168c236, 0xfffffffffffffffe, 0xffffffffffffffff)
    for e in exps:
        for s in sigs:
            emit(rows, e, s, "boundary-exp")
    # J. dense |x| >= 2^63 C2 edge
    for k in range(128):
        emit(rows, 0x403d, M64 - k, "c2-edge-below")
        emit(rows, 0x403e, B63 + k, "c2-edge-above")
    # K. near-identity / tiny-r path edges (|r| < 2^-33 documented)
    for e in (0x3fdc, 0x3fdd, 0x3fde, 0x3fdf):
        for s in (0x8000000000000000, 0x8000000000000001,
                  0xfffffffffffffffe, 0xffffffffffffffff):
            emit(rows, e, s, "tiny-path-edge")
    # L. near-(k*pi/2): x87 operands whose reduced r is pathologically
    # small (top-64-bit truncation and neighbors of k*pi/2)
    for k in range(1, 33):
        v_num = k * PI_NUM               # k*pi * 2^PI_SCALE
        w = v_num.bit_length()
        top = v_num >> (w - 64)          # 64-bit truncation
        e2 = (w - 64) - PI_SCALE + 1     # k*pi/2 exponent adjust below
        # k*pi/2 = v_num / 2^(PI_SCALE+1)
        exp = 0x3fff + (w - 1 - (PI_SCALE + 1))
        for d in (-2, -1, 0, 1, 2):
            emit(rows, exp, (top + d) & M64 | B63, f"near-kpi2")
    seen = set()
    for se, sig, cls in rows:
        key = (se, sig)
        if key in seen:
            continue
        seen.add(key)
        print(f"{se:04x} {sig:016x}")
        print(f"{se:04x} {sig:016x} {cls}", file=sys.stderr)


if __name__ == "__main__":
    main()
