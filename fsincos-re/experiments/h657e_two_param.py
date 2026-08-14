#!/usr/bin/env python3
"""h657e: theta ladder — two-parameter (slope + lattice offset) per cell.

h657d left 95 mixed cells (1.17M rows): the pure ratio threshold
(intercept forced 0) and the pure lattice offset (h657b, slope forced 0)
each fail alone.  Natural generalization, mirroring the theta=0 closure
(universal slope + tabulated lattice intercepts):

    dn (theta>0):  fire  <=>  u*2^66 - M  >  alpha*theta*S + beta*2^66
    up (theta<0):  fire  <=>  M - u*2^66  >  alpha*|theta|*S + beta*2^66
    S = 2*sqlow - L

Per fire-carrying cell (sign, theta, s4, side, dist, L, third): sweep
alpha over a fine grid, 1D-threshold the residual, report best
(alpha, errs, beta).  Verdict: do the mixed cells collapse, is alpha
universal (per quadrant?), and does beta land on a simple lattice?
"""
import pickle
from collections import defaultdict

UNIT = 2**66
X60 = 1 << 60

QUAD = {
    (66, 1): (2, 2, 1,  0, 4, 1, 0, lambda d: -5 * (d - 7)),
    (66, 0): (4, 1, 0,  0, 2, 1, 0, lambda d: -9 - 5 * (d - 9)),
    (67, 0): (4, 2, 1, -2, 4, 2, 1, lambda d: -5 * (d - 7)),
    (67, 1): (2, 2, 3, -3, 8, 2, 1, lambda d: -4 - 2 * (d - 7)),
}

ALPHAS = [i / 8 for i in range(-8, 41)]  # -1.0 .. 5.0 step 0.125


def u_closed(dist, s4, side, L, b1, b2):
    a, G1, G2, p, Q, K, par, W = QUAD[(s4, side)]
    return (K * ((a * L + G1 * b1 + G2 * b2 + p * (L % 2) + W(dist)) // Q)
            + par * (L % 2))


def best_1d(vals):
    """vals: [(v, fire)]; model fire <=> v > t.  Return (errs, t)."""
    vals.sort()
    nf = sum(v[1] for v in vals)
    fires_below = 0
    cleans_above = len(vals) - nf
    best = (cleans_above, float("-inf"))
    for v, f in vals:
        fires_below += f
        cleans_above -= 1 - f
        e = fires_below + cleans_above
        if e < best[0]:
            best = (e, v)
    return best


def main():
    cells = defaultdict(list)
    for name in ("comb7", "comb8"):
        rows = pickle.load(open(f"h657_{name}.pkl", "rb"))
        for theta, dist, s4, side, L, xd60, sR, label, M, sqlow in rows:
            b1 = 1 if 3 * xd60 >= X60 else 0
            b2 = 1 if 3 * xd60 >= 2 * X60 else 0
            u = u_closed(dist, s4, side, L, b1, b2)
            S = 2 * sqlow - L
            if S <= 0:
                continue
            if theta > 0:
                y = (u * UNIT - M) / UNIT
                fire = int(label == 1)
                key = ("dn", theta, s4, side, dist, L, b1 + b2)
            else:
                y = (M - u * UNIT) / UNIT
                fire = int(label == 2)
                key = ("up", theta, s4, side, dist, L, b1 + b2)
            x = abs(theta) * S / UNIT
            cells[key].append((y, x, fire))
        print(f"{name} loaded", flush=True)

    print(f"\n{'cell':>34} {'n':>8} {'fires':>7} {'errs':>6} "
          f"{'rate':>8} {'alpha*':>7} {'beta*':>8}")
    n_exact = n_near = n_mixed = 0
    r_exact = r_near = r_mixed = 0
    for key in sorted(cells):
        pts = cells[key]
        n = len(pts)
        nf = sum(p[2] for p in pts)
        if n < 200 or nf == 0 or nf == n:
            continue
        best = (1 << 62, None, None)
        for a in ALPHAS:
            e, t = best_1d([(y - a * x, f) for y, x, f in pts])
            if e < best[0]:
                best = (e, a, t)
        e, a, t = best
        if e == 0:
            cls, mark = "exact", "EXACT"
            n_exact += 1; r_exact += n
        elif e <= max(3, 0.002 * n):
            cls, mark = "near", "near"
            n_near += 1; r_near += n
        else:
            cls, mark = "mixed", ""
            n_mixed += 1; r_mixed += n
        print(f"{str(key):>34} {n:>8} {nf:>7} {e:>6} "
              f"{e/n:>8.5f} {a:>7.3f} {t:>8.4f}  {mark}", flush=True)
    print(f"\nSUMMARY (fire-carrying cells only): "
          f"exact {n_exact} ({r_exact} rows), near {n_near} ({r_near}), "
          f"mixed {n_mixed} ({r_mixed})")


if __name__ == "__main__":
    main()
