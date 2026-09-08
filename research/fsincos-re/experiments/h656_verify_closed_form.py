#!/usr/bin/env python3
"""h656: FULL verification of the closed-form u-table law.

    M  = low3*sqlow - (sqlow^2 mod 2^s4)
    b1 = [3*rdisc >= 2^sR],  b2 = [3*rdisc >= 2^(sR+1)]
    u  = K*floor((a*L + G1*b1 + G2*b2 + p*(L%2) + W(d))/Q) + par*(L%2)
    fire <=> M < u * 2^66

Quadrant parameters (a, G1, G2, p, Q, K, par, W-ladder):
    (66,hi): 2,2,1,+0, 4, 1,0,  W = -5*(d-7)
    (66,lo): 4,1,0,+0, 2, 1,0,  W = -9 -5*(d-9)
    (67,lo): 4,2,1,-2, 4, 2,1,  W = -5*(d-7)
    (67,hi): 2,2,3,-3, 8, 2,1,  W = -4 -2*(d-7)

Verified on every theta=0 row of comb3/4/5/6/7/8.
"""
import pickle
from collections import defaultdict

NAMES = ["comb4", "comb3", "comb5", "comb6", "comb7", "comb8"]
T60 = 1 << 60

PARAMS = {
    (66, 1): (2, 2, 1, 0, 4, 1, 0, lambda d: -5 * (d - 7)),
    (66, 0): (4, 1, 0, 0, 2, 1, 0, lambda d: -9 - 5 * (d - 9)),
    (67, 0): (4, 2, 1, -2, 4, 2, 1, lambda d: -5 * (d - 7)),
    (67, 1): (2, 2, 3, -3, 8, 2, 1, lambda d: -4 - 2 * (d - 7)),
}


def main():
    tot = bad = 0
    badcell = defaultdict(int)
    seen = set()
    for nm in NAMES:
        for (d, s4, side, L, xd60, sR, fire, req) in pickle.load(
                open(f"h649_{nm}.pkl", "rb")):
            a, G1, G2, p, Q, K, par, Wf = PARAMS[(s4, side)]
            v3 = 3 * xd60
            b1 = 1 if v3 >= T60 else 0
            b2 = 1 if v3 >= 2 * T60 else 0
            u = K * ((a * L + G1 * b1 + G2 * b2 + p * (L % 2) + Wf(d)) // Q) \
                + par * (L % 2)
            ok = (u >= req) if fire else (u <= req)
            tot += 1
            if not ok:
                bad += 1
                badcell[(d, s4, side, L, b1 + b2, fire)] += 1
    print(f"rows {tot}  mismatches {bad}  ({bad/tot:.2e})")
    for k in sorted(badcell):
        print(f"  {k}: {badcell[k]}")


if __name__ == "__main__":
    main()
