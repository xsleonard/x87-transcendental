#!/usr/bin/env python3
"""h657c: the theta ladder — the UNWRAPPED derivative test.

h657b showed: (i) theta>0 dn-fires occur ONLY where the theta=0 law
already fires (slack r <= -1, zero fires at r >= 0), with fire fraction
rising with depth below threshold; (ii) theta<0 up-fires occur ONLY on
the clean side (r >= 0), concentrated r in [0,2]; (iii) the integer
sqlow-shift rendering fails because (sqlow + k*theta)^2 mod 2^s4 wraps —
the mod discontinuity is not in the data.

The hypothesis proper is the LINEAR (unwrapped) derivative: the
effective threshold moves continuously by theta * dM/dsqlow, i.e.

    fire_dn  <=>  M + c * theta * S < u * 2^66,      S = 2*sqlow - L
    (theta > 0; c a single global scale, c=1 the unit hypothesis)

equivalently rho = (u*2^66 - M) / (theta * S) > c: ONE step in rho.
Mirror for theta<0 up-fires: rho2 = (M - u*2^66) / (|theta| * S) > c2.

This script computes rho per row (h657 caches), finds the best single
threshold per corpus / per theta / per quadrant, prints error counts,
threshold locations, and the rho histogram by label.
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


def u_closed(dist, s4, side, L, xd60):
    a, G1, G2, p, Q, K, par, W = QUAD[(s4, side)]
    b1 = 1 if 3 * xd60 >= X60 else 0
    b2 = 1 if 3 * xd60 >= 2 * X60 else 0
    return (K * ((a * L + G1 * b1 + G2 * b2 + p * (L % 2) + W(dist)) // Q)
            + par * (L % 2))


def best_step(pairs):
    """pairs: [(rho, is_fire)] -> (min errs, threshold, n_fire).
    Model: fire <=> rho > c.  Sweep all cut points."""
    pairs = sorted(pairs)
    nf = sum(p[1] for p in pairs)
    # cut below index i: predict fire for i..end
    # errs(i) = fires below i + cleans at/above i
    errs = nf and None
    fires_below = 0
    cleans_above = len(pairs) - nf
    best = (cleans_above, float("-inf"))  # cut below everything
    for i, (rho, f) in enumerate(pairs):
        fires_below += f
        cleans_above -= 1 - f
        e = fires_below + cleans_above
        if e < best[0]:
            best = (e, rho)
    return best[0], best[1], nf


def rho_hist(pairs, lo=-2.0, hi=6.0, step=0.25):
    h = defaultdict(lambda: [0, 0])
    for rho, f in pairs:
        b = max(lo, min(hi, step * int(rho / step)))
        h[round(b, 2)][f] += 1
    return h


def main():
    for name in ("comb7", "comb8"):
        rows = pickle.load(open(f"h657_{name}.pkl", "rb"))
        print(f"\n########## {name}: {len(rows)} rows ##########", flush=True)

        # rho per row
        by = defaultdict(list)       # (sign, theta, quad) -> [(rho, fire)]
        pooled = defaultdict(list)   # sign -> [(rho, fire)]
        for theta, dist, s4, side, L, xd60, sR, label, M, sqlow in rows:
            u = u_closed(dist, s4, side, L, xd60)
            S = 2 * sqlow - L
            if S <= 0:
                continue
            if theta > 0:
                rho = (u * UNIT - M) / (theta * S)
                fire = int(label == 1)
                by[("dn", theta, (s4, side))].append((rho, fire))
                pooled["dn"].append((rho, fire))
            else:
                rho = (M - u * UNIT) / (-theta * S)
                fire = int(label == 2)
                by[("up", theta, (s4, side))].append((rho, fire))
                pooled["up"].append((rho, fire))

        for sign in ("dn", "up"):
            pl = pooled[sign]
            e, c, nf = best_step(pl)
            base = min(nf, len(pl) - nf)
            print(f"\n[{name}] {sign}-fires pooled: n={len(pl)} fires={nf} "
                  f"| one-step best: {e} errs ({e/len(pl):.5f}) at c={c:.4f} "
                  f"(never/always={base})", flush=True)
            keys = sorted(k for k in by if k[0] == sign)
            print(f"  {'theta':>6} {'quad':>8} {'n':>8} {'fires':>7} "
                  f"{'errs':>7} {'rate':>8} {'c*':>9}")
            for k in keys:
                pl2 = by[k]
                e2, c2, nf2 = best_step(pl2)
                print(f"  {k[1]:>+6} {str(k[2]):>8} {len(pl2):>8} {nf2:>7} "
                      f"{e2:>7} {e2/len(pl2):>8.5f} {c2:>9.4f}", flush=True)
            # histogram, pooled
            h = rho_hist(pl)
            print(f"  rho histogram ({sign}):  bin  clean  fire  fire%")
            for b in sorted(h):
                cn, fn = h[b][0], h[b][1]
                print(f"    {b:>6.2f} {cn:>9} {fn:>8} "
                      f"{fn/(cn+fn):>7.3f}")


if __name__ == "__main__":
    main()
