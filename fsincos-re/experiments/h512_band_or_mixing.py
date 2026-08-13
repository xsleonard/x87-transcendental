#!/usr/bin/env python3
"""h512: for the mixed dist=8 strata (low3 in {1,2,5}), decide between
(a) a broad transition BAND around the fitted line (fire rate is a
function of residual r = m - s*XT - c: ~1 far below, ~0 far above,
wide middle) and (b) position-independent MIXING (rate flat in r —
pure hidden state).  Controls: the clean strata low3=6 lower / 7 lower.

Output per region: fire rate in residual bins, the 10-90 band width,
and the far-field leak rates (r < -0.02, r > +0.02).
"""
from collections import defaultdict
from h509_d8_regions import built_comb3

REGIONS = [
    # (low3, xdlo, xdhi, s, c, label)
    (1, 0.0, 2/3, 0.354, 0.613, "MIXED (8,1) XD<2/3"),
    (1, 2/3, 1.0, 0.194, 0.744, "MIXED (8,1) XD>=2/3"),
    (2, 1/3, 1.0, 0.403, 0.645, "MIXED (8,2) XD>=1/3"),
    (5, 1/6, 1/3, 0.0619, 0.7750, "MIXED (8,5) XD [1/6,1/3)"),
    (5, 5/12, 2/3, 0.0619, 0.7750, "MIXED (8,5) XD [5/12,2/3)"),
    (5, 2/3, 1.0, 0.0510, 0.8280, "MIXED (8,5) XD>=2/3"),
    (6, 0.0, 1/3, 0.05141, 0.76507, "CONTROL (8,6) XD<1/3"),
    (7, 0.0, 2/3, 0.04320, 0.80194, "CONTROL (8,7) XD<2/3"),
]

BINS = [-1, -0.05, -0.02, -0.01, -0.005, -0.002, -0.001,
        0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 1]


def main():
    data = built_comb3()
    rows8 = defaultdict(list)
    for cell, XT, XD, mf, fire in data:
        if cell[0] == 8:
            rows8[cell[1]].append((XT, XD, mf, fire))
    for low3, xlo, xhi, s, c, label in REGIONS:
        pts = [(XT, XD, mf, o) for XT, XD, mf, o in rows8[low3]
               if xlo <= XD < xhi]
        hist = defaultdict(lambda: [0, 0])
        for XT, XD, mf, o in pts:
            r = mf - s*XT - c
            for i in range(len(BINS) - 1):
                if BINS[i] <= r < BINS[i + 1]:
                    hist[i][0] += 1
                    hist[i][1] += o
                    break
        print(f"\n{label}  n={len(pts)} "
              f"fires={sum(p[3] for p in pts)}  (s={s} c={c})")
        for i in range(len(BINS) - 1):
            n, n1 = hist[i]
            if n == 0:
                continue
            rate = n1 / n
            bar = "#" * int(rate * 40)
            print(f"  r in [{BINS[i]:+.3f},{BINS[i+1]:+.3f}) "
                  f"n={n:6d} rate={rate:.3f} {bar}")


if __name__ == "__main__":
    main()
