#!/usr/bin/env python3
"""h658b: theta-ladder edge table — global verification + unification.

h658 produced feasible integer taps per (sign, |theta|, quadrant), all
at o=0, split-half stable.  This pass scores candidate tap vectors
(c0, c_b1, c_b2, c_Lpar, c_d) DIRECTLY against every labeled row:

    dn: fire possible <=> M <  u_T*2^66
    up: fire possible <=> M >= u_T*2^66
    u_T = K*floor((base -/+ T)/Q) + par*(L%2),
    T = c0 + c_b1*b1 + c_b2*b2 + c_Lpar*(L%2) + c_d*(d-7)

reporting violations (fires outside the region — the residue is the
known <=3-row anomaly families), region size and in-region fire rate
(should sit at the 3/4 ceiling).  Cross-group candidates test whether
one form serves several quadrants (as at theta=0, where (66,hi) and
(67,lo) shared parameters).
"""
import pickle
from collections import defaultdict

UNIT = 2**66

QUAD = {
    (66, 1): (2, 2, 1,  0, 4, 1, 0, lambda d: -5 * (d - 7)),
    (66, 0): (4, 1, 0,  0, 2, 1, 0, lambda d: -9 - 5 * (d - 9)),
    (67, 0): (4, 2, 1, -2, 4, 2, 1, lambda d: -5 * (d - 7)),
    (67, 1): (2, 2, 3, -3, 8, 2, 1, lambda d: -4 - 2 * (d - 7)),
}

# candidates per (sign, theta): list of tap vectors to score on every quad
CANDS = {
    ("dn", 1): [(8, 1, -1, 1, -3), (9, 1, 0, 1, -4), (2, 1, 0, 0, 4)],
    ("dn", 2): [(18, 0, 0, 0, -6), (16, 2, -2, 2, -6), (8, 1, 1, 1, -2)],
    ("up", 1): [(6, 1, 0, -2, 0), (6, -1, 0, 1, -1), (1, 0, 0, 1, 1)],
    ("up", 2): [(6, 0, 0, 1, 0), (12, 0, 0, 0, 0), (11, 1, 0, 0, 0),
                (0, 0, 0, 0, 3)],
}


def main():
    groups = defaultdict(list)
    for name in ("comb7", "comb8"):
        rows = pickle.load(open(f"h657m_{name}.pkl", "rb"))
        for mhex, theta, dist, s4, side, L, rdisc, sR, label, M, sqlow in rows:
            b1 = 1 if 3 * rdisc >= (1 << sR) else 0
            b2 = 1 if 3 * rdisc >= (1 << (sR + 1)) else 0
            sign = "dn" if theta > 0 else "up"
            fire = int(label == (1 if sign == "dn" else 2))
            groups[(sign, abs(theta), (s4, side))].append(
                (dist, L, b1, b2, M, fire))
        print(f"{name} loaded", flush=True)

    print(f"\n{'group':>22} {'tap (c0,b1,b2,Lp,d7)':>22} {'viol':>5} "
          f"{'region':>8} {'rate':>7} {'fires':>7}")
    for (sign, th, quad) in sorted(groups, key=str):
        rr = groups[(sign, th, quad)]
        a, G1, G2, p, Q, K, par, W = QUAD[quad]
        nf_tot = sum(r[5] for r in rr)
        for cand in CANDS[(sign, th)]:
            c0, cb1, cb2, clp, cd = cand
            viol = nin = fin = 0
            vlist = []
            for dist, L, b1, b2, M, fire in rr:
                lp = L % 2
                base = a * L + G1 * b1 + G2 * b2 + p * lp + W(dist)
                T = c0 + cb1 * b1 + cb2 * b2 + clp * lp + cd * (dist - 7)
                if sign == "dn":
                    u = K * ((base - T) // Q) + par * lp
                    inside = M < u * UNIT
                else:
                    u = K * ((base + T) // Q) + par * lp
                    inside = M >= u * UNIT
                if inside:
                    nin += 1
                    fin += fire
                elif fire:
                    viol += 1
                    if len(vlist) < 4:
                        vlist.append((dist, L, b1, b2))
            tag = f"({','.join(map(str, cand))})"
            print(f"{sign} |t|={th} {str(quad):>9} {tag:>22} {viol:>5} "
                  f"{nin:>8} {fin/nin if nin else 0:>7.4f} {nf_tot:>7}"
                  + (f"   viol@{vlist}" if vlist else ""), flush=True)
        print()


if __name__ == "__main__":
    main()
