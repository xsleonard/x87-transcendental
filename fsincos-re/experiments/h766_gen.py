#!/usr/bin/env python3
# h766: small-argument corpus — ck1 class mix, |x| in [0.25, pi/4).
import random, sys
seed, N, out = int(sys.argv[1],0), int(sys.argv[2]), sys.argv[3]
random.seed(seed)
PI4 = 0xC90FDAA22168C234   # pi/4 sig top-64 (value ~0.785)
w = open(out,'w')
n = 0
while n < N:
    r = random.random()
    if r < 0.55: sig = (1<<63) | random.getrandbits(63)
    elif r < 0.85: sig = ((1<<52) | random.getrandbits(52)) << 11
    else: sig = ((1<<63) | random.getrandbits(63)) & ~((1<<random.randrange(1,12))-1)
    se = random.choice([0x3ffd, 0x3ffe])
    if se == 0x3ffe and sig >= PI4: continue
    if random.random() < 0.5: se |= 0x8000
    w.write('%04x %016x\n' % (se, sig)); n += 1
w.close()
