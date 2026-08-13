#!/usr/bin/env python3
"""h546: fire-rate vs rho = gap/rf (staircase test of the rf-ladder
hypothesis).  Uses h538_rows.tsv (glog) with rf ~ 2/3*2^64 (rfv's
low-bit drift is ~2^-40 relative — irrelevant at bin width 0.02).
If D concentrates near multiples of rf-fractions, the fire-rate
curve is a staircase with drops at rho = 1/3, 2/3, 1, ...
"""
import math
from collections import defaultdict

LOG2RF = math.log2(2 / 3) + 64

hist = defaultdict(lambda: [0, 0])
with open("h538_rows.tsv") as fh:
    next(fh)
    for ln in fh:
        f = ln.split("\t")
        theta, req2, side = int(f[1]), int(f[2]), f[3]
        glog = float(f[8])
        rho = 2 ** (glog - LOG2RF)
        if rho > 1.7:
            continue
        b = int(rho * 60)
        hist[(side, theta, b)][1] += 1
        if req2:
            hist[(side, theta, b)][0] += 1

for side in ("u", "d"):
    for theta in (-2, -1, 0, 1, 2):
        bins = {b: hist[(side, theta, b)] for b in range(102)
                if (side, theta, b) in hist}
        if not bins:
            continue
        tot = sum(v[1] for v in bins.values())
        totf = sum(v[0] for v in bins.values())
        if totf == 0:
            continue
        print(f"\n=== side={side} theta={theta:+d} "
              f"(n={tot}, fires={totf}) rho-bin: rate ===")
        for b in sorted(bins):
            nf, n = bins[b]
            if n < 200:
                continue
            bar = "#" * int(50 * nf / n)
            print(f"  {b/60:5.3f}-{(b+1)/60:5.3f} {n:7d} "
                  f"{nf/n:6.3f} {bar}")
