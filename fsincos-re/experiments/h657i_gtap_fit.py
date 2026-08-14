#!/usr/bin/env python3
"""h657i: theta ladder — close the deterministic part: the g-tap.

Model of the ladder (from h657e/f):
  dn (theta>0):  fire possible  <=>  M <  u_g * 2^66,
      u_g = K*floor((a*L + G1*b1 + G2*b2 + p*(L%2) + W(d) - g_dn*theta)/Q)
            + par*(L%2)
  up (theta<0):  fire possible  <=>  M >= u_h * 2^66,
      u_h = same with + g_up*|theta| (+ outer offset o_up lattice units)
  Inside the possible region P(fire) ~ 3/4 flat (the hidden pair-bit,
  h657f/g/h); outside it fires MUST be zero.

Fit integer g (and o_up) per quadrant by: (1) zero-violation constraint
(fires outside region), (2) maximize Bernoulli(3/4) log-likelihood
inside.  Report per quadrant: best params, violations, region fire rate,
per-cell edge residuals for the worst cells.
"""
import pickle
from collections import defaultdict
from math import log

UNIT = 2**66
X60 = 1 << 60

QUAD = {
    (66, 1): (2, 2, 1,  0, 4, 1, 0, lambda d: -5 * (d - 7)),
    (66, 0): (4, 1, 0,  0, 2, 1, 0, lambda d: -9 - 5 * (d - 9)),
    (67, 0): (4, 2, 1, -2, 4, 2, 1, lambda d: -5 * (d - 7)),
    (67, 1): (2, 2, 3, -3, 8, 2, 1, lambda d: -4 - 2 * (d - 7)),
}

LP = {1: log(0.75), 0: log(0.25)}


def main():
    rows_all = defaultdict(list)   # (sign, quad) -> (theta,dist,L,b1,b2,M,fire)
    for name in ("comb7", "comb8"):
        rows = pickle.load(open(f"h657_{name}.pkl", "rb"))
        for theta, dist, s4, side, L, xd60, sR, label, M, sqlow in rows:
            b1 = 1 if 3 * xd60 >= X60 else 0
            b2 = 1 if 3 * xd60 >= 2 * X60 else 0
            if theta > 0:
                rows_all[("dn", (s4, side))].append(
                    (theta, dist, L, b1, b2, M, int(label == 1)))
            else:
                rows_all[("up", (s4, side))].append(
                    (-theta, dist, L, b1, b2, M, int(label == 2)))
        print(f"{name} loaded", flush=True)

    for (sign, quad), rr in sorted(rows_all.items()):
        a, G1, G2, p, Q, K, par, W = QUAD[quad]
        best = None
        for g in range(0, 33):
            for o in (0, 1, 2) if sign == "up" else (0,):
                viol = 0
                ll = 0.0
                nin = fin = 0
                for th, dist, L, b1, b2, M, fire in rr:
                    base = a * L + G1 * b1 + G2 * b2 + p * (L % 2) + W(dist)
                    if sign == "dn":
                        u = K * ((base - g * th) // Q) + par * (L % 2)
                        inside = M < u * UNIT
                    else:
                        u = K * ((base + g * th) // Q) + par * (L % 2) + o
                        inside = M >= u * UNIT
                    if inside:
                        nin += 1
                        fin += fire
                        ll += LP[fire]
                    elif fire:
                        viol += 1
                sc = (viol, -ll)
                if best is None or sc < best[0]:
                    best = (sc, g, o, viol, nin, fin)
        (sc, g, o, viol, nin, fin) = best
        nf = sum(r[6] for r in rr)
        print(f"\n[{sign} {quad}] n={len(rr)} fires={nf}: "
              f"best g={g} o={o} -> violations={viol}, "
              f"region {nin} rows, rate {fin/nin if nin else 0:.4f}",
              flush=True)
        # per-theta split at best params
        for th0 in sorted(set(r[0] for r in rr)):
            viol = nin = fin = ntot = 0
            for th, dist, L, b1, b2, M, fire in rr:
                if th != th0:
                    continue
                ntot += 1
                base = a * L + G1 * b1 + G2 * b2 + p * (L % 2) + W(dist)
                if sign == "dn":
                    u = K * ((base - g * th) // Q) + par * (L % 2)
                    inside = M < u * UNIT
                else:
                    u = K * ((base + g * th) // Q) + par * (L % 2) + o
                    inside = M >= u * UNIT
                if inside:
                    nin += 1
                    fin += fire
                elif fire:
                    viol += 1
            print(f"    |theta|={th0}: n={ntot} region={nin} "
                  f"rate={fin/nin if nin else 0:.4f} violations={viol}")


if __name__ == "__main__":
    main()
