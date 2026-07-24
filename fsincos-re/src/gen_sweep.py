#!/usr/bin/env python3
"""Generate a structured input sweep for the Itanium-algorithm-vs-real-x87
comparison.  Emits "se_hex sig_hex" lines (x87 80-bit) on stdout.

Structured by algorithm path so the comparison report can attribute
mismatches:
  A quick-small   |x| < 2^-3            (small_r, r=x, c=0)
  B quick-normal  2^-3 <= |x| < pi/4    (normal_r, r=x, c=0)
  C moderate      pi/4 <= |x| < 2^24    (rshf reduction; small_r/normal_r)
  D mod-near      moderate, within a few ulps of k*(pi/2)  (Case 2 / tiny s)
  E large         2^24 <= |x| < 2^63    (P_0 pre-reduction)
  F large-near    large, near k*(pi/2)  (Case 4)
  G boundary      path-threshold neighborhoods
Deterministic (fixed seed).  ~50k inputs by default.
"""
import random
import sys
from fractions import Fraction

random.seed(0xF51C05)
N_A, N_B, N_C, N_D, N_E, N_F = 4000, 6000, 16000, 8000, 10000, 6000

def emit(se, sig):
    print(f"{se:04x} {sig:016x}")

def rand_sig():
    return random.getrandbits(64) | (1 << 63)

def enc(x):
    """Fraction -> nearest-even double-extended (se, sig)."""
    if x == 0:
        return 0, 0
    sign = 1 if x < 0 else 0
    a = abs(x)
    e = a.numerator.bit_length() - a.denominator.bit_length()
    if Fraction(2) ** e > a:
        e -= 1
    scaled = a * Fraction(2) ** (63 - e)
    i = scaled.numerator // scaled.denominator
    if scaled - i > Fraction(1, 2) or (scaled - i == Fraction(1, 2) and (i & 1)):
        i += 1
    if i == 1 << 64:
        i >>= 1
        e += 1
    return (sign << 15) | (e + 16383), i

def pi_frac(prec=300):
    def atan_inv(n):
        t, k = Fraction(0), 0
        while True:
            term = Fraction((-1) ** k, (2 * k + 1) * n ** (2 * k + 1))
            t += term
            if abs(term) < Fraction(1, 2 ** (prec + 16)):
                return t
            k += 1
    return 16 * atan_inv(5) - 4 * atan_inv(239)

PI = pi_frac()

# A: quick-small (exclude denormals for round 1)
for _ in range(N_A):
    e = random.randint(-100, -4)
    emit((random.getrandbits(1) << 15) | (e + 16383), rand_sig())

# B: quick-normal
for _ in range(N_B):
    e = random.randint(-3, -1)
    se = (random.getrandbits(1) << 15) | (e + 16383)
    sig = rand_sig()
    if e == -1 and sig >= 0xC90FDAA22168C234:   # keep below pi/4
        sig = 0x8000000000000000 | (sig & 0x3FFFFFFFFFFFFFFF)
    emit(se, sig)

# C: moderate
for _ in range(N_C):
    e = random.randint(0, 23)
    emit((random.getrandbits(1) << 15) | (e + 16383), rand_sig())

# D: moderate near k*pi/2 (drives |s| small -> Case 2 & compensation)
for _ in range(N_D):
    k = random.randint(1, 2**23)
    se, sig = enc(PI / 2 * k)
    d = random.choice([0, 0, 1, -1, 2, -2, 3, 7, 15])
    sig = (sig + d) & 0xFFFFFFFFFFFFFFFF
    if not (sig >> 63):
        sig |= 1 << 63
    if random.getrandbits(1):
        se ^= 0x8000
    emit(se, sig)

# E: large (pre-reduction)
for _ in range(N_E):
    e = random.randint(24, 62)
    emit((random.getrandbits(1) << 15) | (e + 16383), rand_sig())

# F: large near k*pi/2 (Case 4)
for _ in range(N_F):
    ebits = random.randint(25, 62)
    k = random.randint(2 ** (ebits - 1), 2 ** ebits) * 2 // 3 + 1
    se, sig = enc(PI / 2 * k)
    d = random.choice([0, 0, 1, -1, 2, -2])
    sig = (sig + d) & 0xFFFFFFFFFFFFFFFF
    if not (sig >> 63):
        sig |= 1 << 63
    if random.getrandbits(1):
        se ^= 0x8000
    emit(se, sig)

# G: boundaries and specials
G = []
pi4se, pi4sig = enc(PI / 4)
for d in range(-4, 5):
    G.append((pi4se, pi4sig + d))
G += [(16383 - 3, 1 << 63), (16383 - 3, (1 << 63) + 1), (16383 - 4, 0xFFFFFFFFFFFFFFFF)]
G += [(16383 + 24, 1 << 63), (16383 + 23, 0xFFFFFFFFFFFFFFFF)]
G += [(16383 + 62, 0xFFFFFFFFFFFFFFFF), (16383 + 63, 1 << 63)]   # C2 edge
G += [(16383, 1 << 63), (16383 + 1, 0xC90FDAA22168C235)]          # 1.0, ~pi
G += [(0x0001, 1 << 63)]                                          # smallest normal
for se, sig in G:
    emit(se, sig & 0xFFFFFFFFFFFFFFFF)
    emit(se | 0x8000, sig & 0xFFFFFFFFFFFFFFFF)

print(f"generated to stdout", file=sys.stderr)
