#!/usr/bin/env python3
# h912 phase-C generator: operands near N*(pi/2) with |eps| log-uniform
# in [2^-9, 2^-5.5] — targets the activation block (mule2 -72/-73,
# dist 9/10).  Exact 256-bit fixed-point pi/2.
import sys, random
seed, count = int(sys.argv[1]), int(sys.argv[2])
random.seed(seed)
# pi to 320 fractional hex digits' worth (0x3.243F6A88...); value = PI_INT / 2^316
PI_HEX = "3243F6A8885A308D313198A2E03707344A4093822299F31D0082EFA98EC4E6C89452821E638D01377BE5466CF34E90C6C"
PI_INT = int(PI_HEX, 16)          # pi * 2^(4*97-4) = pi * 2^384... compute shift:
# PI_HEX has 97 hex digits; value = int / 16^96 = pi  (leading '3' is the integer part)
PI_SHIFT = 4 * 96                 # pi = PI_INT / 2^384
HALFPI_INT = PI_INT               # pi/2 = PI_INT / 2^385
HALFPI_SHIFT = PI_SHIFT + 1
w = sys.stdout.write
for _ in range(count):
    N = random.randint(3, (1 << 51))
    u = random.uniform(-9.0, -5.5)
    mant = 1.0 + random.random()
    eps = mant * (2.0 ** u)
    s = random.choice((1, -1))
    # t = N*pi/2 + s*eps in 385-bit fixed point
    t = N * HALFPI_INT
    ei = int(eps * (1 << 80)) << (HALFPI_SHIFT - 80)
    t = t + s * ei
    if t <= 0:
        continue
    # round to 64-bit significand extended
    bl = t.bit_length()
    e2 = bl - 1 - HALFPI_SHIFT          # value = t / 2^HALFPI_SHIFT in [2^e2, 2^(e2+1))
    sh = bl - 65
    sig = (t >> sh) if sh >= 0 else (t << -sh)
    sig = (sig + 1) >> 1                 # round to nearest 64
    if sig >> 64:
        sig >>= 1
        e2 += 1
    se = 0x3FFF + e2
    if random.random() < 0.5:
        se |= 0x8000
    w("%04x %016x\n" % (se, sig & 0xFFFFFFFFFFFFFFFF))
