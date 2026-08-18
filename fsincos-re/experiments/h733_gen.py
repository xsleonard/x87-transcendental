#!/usr/bin/env python3
# h733: large-|x| corpus chunk generator for B10 densification.
# Usage: h733_gen.py SEED N OUT
import random, sys
seed, N, out = int(sys.argv[1], 0), int(sys.argv[2]), sys.argv[3]
random.seed(seed)
w = open(out, "w")
for _ in range(N):
    r = random.random()
    se = random.randrange(0x4003, 0x403e)
    if r < 0.55:
        sig = (1 << 63) | random.getrandbits(63)
    elif r < 0.85:
        sig = ((1 << 52) | random.getrandbits(52)) << 11
    else:
        sig = ((1 << 63) | random.getrandbits(63)) & ~((1 << random.randrange(1, 12)) - 1)
    if random.random() < 0.5: se |= 0x8000
    w.write("%04x %016x\n" % (se, sig))
w.close()
