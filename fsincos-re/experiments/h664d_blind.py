#!/usr/bin/env python3
"""h664d: BLIND transfer of the h664b (66,0) tap vectors to comb12.

comb12 = the 160 comb11 W1 segment starts shifted +2^53 (gap
midpoints, zero overlap).  NO REFIT: the four h664b vectors (plus the
h658 (67,0) vectors for the window's other quadrant) are applied as
frozen region gates; any fire outside its region is an edge
violation.  h646 verdict rule: a real basis transfers exactly.

Reads h664_<c>.pkl (built by h664_w1_census.py).
"""
import pickle, sys
from collections import defaultdict

UNIT = 2**66

QUAD = {
    (66, 1): (2, 2, 1,  0, 4, 1, 0, lambda d: -5 * (d - 7)),
    (66, 0): (4, 1, 0,  0, 2, 1, 0, lambda d: -9 - 5 * (d - 9)),
    (67, 0): (4, 2, 1, -2, 4, 2, 1, lambda d: -5 * (d - 7)),
    (67, 1): (2, 2, 3, -3, 8, 2, 1, lambda d: -4 - 2 * (d - 7)),
}
TAPS = {
    ("dn", 1, (66, 1)): (8, 1, -1, 1, -3),
    ("dn", 1, (67, 0)): (8, 1, -1, 1, -3),
    ("dn", 1, (67, 1)): (2, 1, 0, 0, 4),
    ("dn", 2, (66, 1)): (18, 0, 0, 0, -6),
    ("dn", 2, (67, 0)): (18, 0, 0, 0, -6),
    ("up", 1, (66, 1)): (6, -1, 0, 1, -1),
    ("up", 1, (67, 0)): (6, -1, 0, 1, -1),
    ("up", 1, (67, 1)): (6, 1, 0, -2, 0),
    ("up", 2, (66, 1)): (6, 0, 0, 1, 0),
    ("up", 2, (67, 0)): (6, 0, 0, 1, 0),
    ("up", 2, (67, 1)): (12, 0, 0, 0, 0),
    # h664b, comb11-derived — the vectors under blind test:
    ("dn", 1, (66, 0)): (1, 1, -1, 1, 0),
    ("dn", 2, (66, 0)): (12, 0, 0, 0, -3),
    ("up", 1, (66, 0)): (7, -1, 1, 1, -2),
    ("up", 2, (66, 0)): (8, 1, 0, 1, -2),
}


def main():
    for name in sys.argv[1:] or ("comb12",):
        rows = pickle.load(open(f"h664_{name}.pkl", "rb"))
        stats = defaultdict(lambda: [0, 0, 0, 0])  # rows, in, fin, viol
        for mhex, th, dist, s4, side, L, rdisc, sR, label, M, sqlow in rows:
            if th == 0 or label < 0:
                continue
            sign = "dn" if th > 0 else "up"
            fire = int(label == (1 if th > 0 else 2))
            quad = (s4, side)
            tap = TAPS.get((sign, abs(th), quad))
            key = (sign, abs(th), quad)
            st = stats[key]
            st[0] += 1
            if tap is None:
                st[3] += fire      # fires in a no-fire stratum
                continue
            a, G1, G2, p, Q, K, par, W = QUAD[quad]
            lp = L % 2
            base = a * L + G1 * b1v(rdisc, sR) + G2 * b2v(rdisc, sR) \
                + p * lp + W(dist)
            c0, cb1, cb2, clp, cd = tap
            T = c0 + cb1 * b1v(rdisc, sR) + cb2 * b2v(rdisc, sR) \
                + clp * lp + cd * (dist - 7)
            if sign == "dn":
                u = K * ((base - T) // Q) + par * lp
                inr = M // UNIT < u
            else:
                u = K * ((base + T) // Q) + par * lp
                inr = M // UNIT >= u
            if inr:
                st[1] += 1
                st[2] += fire
            elif fire:
                st[3] += 1
        print(f"===== {name} blind tap transfer =====")
        tv = 0
        for k in sorted(stats, key=str):
            n, nin, nf, viol = stats[k]
            rate = nf / nin if nin else 0.0
            tv += viol
            print(f"  {k}: rows={n:>7,} in-region={nin:>7,} "
                  f"fires-in={nf:>7,} rate={rate:.3f} VIOL={viol}")
        print(f"  TOTAL edge violations: {tv}")


def b1v(rdisc, sR):
    return 1 if 3 * rdisc >= (1 << sR) else 0


def b2v(rdisc, sR):
    return 1 if 3 * rdisc >= (1 << (sR + 1)) else 0


if __name__ == "__main__":
    main()
