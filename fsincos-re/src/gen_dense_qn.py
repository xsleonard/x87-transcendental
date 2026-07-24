#!/usr/bin/env python3
"""Dense quick-normal sweep: pure-kernel probes (r = x exactly, c = 0).
r in [2^-3, pi/4), both signs, uniform per binade."""
import random, sys
random.seed(0xD15E)
N_PER = 80000
PI4SIG = 0xC90FDAA22168C234
for e in (-3, -2, -1):
    for _ in range(N_PER):
        sig = random.getrandbits(64) | (1 << 63)
        if e == -1 and sig >= PI4SIG:
            sig = 0x8000000000000000 | (sig >> 1)
        se = (random.getrandbits(1) << 15) | (e + 16383)
        print(f"{se:04x} {sig:016x}")
