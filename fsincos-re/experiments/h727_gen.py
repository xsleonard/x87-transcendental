#!/usr/bin/env python3
# h727: generate the "reasonable corpus" randv1 — a fresh, blind,
# broad random operand set for FCOS/FSIN validation (goal: accurate
# C implementation on a reasonable corpus).  Seeded, reproducible.
# Mix:
#   60% broad normals: exponent uniform in [0x3fbe, 0x403d]
#       (2^-65 .. 2^62), uniform 64-bit sig with MSB set
#   20% binary64-aligned operands (53-bit sigs), same exponent span
#   10% near k*pi/2: k random (1..2^40 skewed small), the 80-bit
#       neighbor of k*pi/2 with sig jitter in [-8, 8]
#    5% tiny/denormal: exponents [0x0001, 0x3fbd] + se=0 denormals
#    5% C2/specials: |x| >= 2^63, infinities, NaN payloads,
#       pseudo-denormals
# Sign bit random throughout.  Output: "se sig" hex lines.
import random
random.seed(0x662662)
N = 8_000_000
PI_FRAC = int(
    "243F6A8885A308D313198A2E03707344A4093822299F31D0082EFA98EC4E6C89"
    "452821E638D01377BE5466CF34E90C6CC0AC29B7C97C50DD3F84D5B5B5470917", 16)
PI_BITS = 512   # pi = 3 + PI_FRAC/2^512
PI = (3 << PI_BITS) | PI_FRAC       # pi * 2^512

def kpi2_neighbor():
    k = random.choice((
        random.randrange(1, 1 << 8),
        random.randrange(1, 1 << 20),
        random.randrange(1, 1 << 40)))
    v = k * PI                       # k*pi * 2^512
    v >>= 1                          # k*pi/2 * 2^512
    E = v.bit_length() - 1 - PI_BITS
    sig = v >> (v.bit_length() - 64)
    sig += random.randint(-8, 8)
    if sig < (1 << 63): sig = (1 << 63) | (sig & ((1 << 63) - 1))
    if sig >= (1 << 64): sig >>= 1; E += 1
    se = 0x3fff + E
    if not (1 <= se <= 0x7ffe): return None
    return se, sig & 0xffffffffffffffff

out = []
w = open("randv1_inputs.txt", "w")
n = 0
while n < N:
    r = random.random()
    if r < 0.60:
        se = random.randrange(0x3fbe, 0x403e)
        sig = (1 << 63) | random.getrandbits(63)
    elif r < 0.80:
        se = random.randrange(0x3fbe, 0x403e)
        sig = ((1 << 52) | random.getrandbits(52)) << 11
    elif r < 0.90:
        t = kpi2_neighbor()
        if t is None: continue
        se, sig = t
    elif r < 0.95:
        if random.random() < 0.2:
            se = 0                     # denormal / pseudo-denormal
            sig = random.getrandbits(64)
            if sig == 0: sig = 1
        else:
            se = random.randrange(0x0001, 0x3fbe)
            sig = (1 << 63) | random.getrandbits(63)
    else:
        c = random.random()
        if c < 0.7:
            se = random.randrange(0x403e, 0x7fff)   # C2 domain
            sig = (1 << 63) | random.getrandbits(63)
        elif c < 0.8:
            se = 0x7fff; sig = 1 << 63              # inf
        else:
            se = 0x7fff                              # NaN payloads
            sig = (1 << 63) | random.getrandbits(63)
            if sig == (1 << 63): sig |= 1
    if random.random() < 0.5: se |= 0x8000
    w.write("%04x %016x\n" % (se, sig))
    n += 1
w.close()
print("wrote", n, "rows")
