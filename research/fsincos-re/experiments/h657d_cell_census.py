#!/usr/bin/env python3
"""h657d: theta ladder — per-cell census of the derivative-ratio threshold.

h657c: rho = (u*2^66 - M) / (|theta| * S), S = 2*sqlow - L, is a hard
necessary condition (rho < 0 => zero fires, both directions, 4.7M rows)
and P(fire) rises monotonically in rho — but pooled thresholds sit at
~50 percent mixing.  Same shape the theta=0 campaign saw before the
per-stratum intercepts were tabulated (h500 -> h641).

This script: cells = (sign, theta, s4, side, dist, L, third).  Per cell,
best single rho threshold; count exact cells (0 errs), near cells, and
the mixing profile of the rest.  Verdict input for whether the ladder is
"derivative slope + intercept table" (then close the table) or carries a
genuine extra bit inside cells.
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


def u_closed(dist, s4, side, L, b1, b2):
    a, G1, G2, p, Q, K, par, W = QUAD[(s4, side)]
    return (K * ((a * L + G1 * b1 + G2 * b2 + p * (L % 2) + W(dist)) // Q)
            + par * (L % 2))


def best_step(pairs):
    pairs.sort()
    nf = sum(p[1] for p in pairs)
    fires_below = 0
    cleans_above = len(pairs) - nf
    best = (cleans_above, float("-inf"))
    for rho, f in pairs:
        fires_below += f
        cleans_above -= 1 - f
        e = fires_below + cleans_above
        if e < best[0]:
            best = (e, rho)
    return best[0], best[1], nf


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
            third = b1 + b2
            if theta > 0:
                rho = (u * UNIT - M) / (theta * S)
                fire = int(label == 1)
                key = ("dn", theta, s4, side, dist, L, third)
            else:
                rho = (M - u * UNIT) / (-theta * S)
                fire = int(label == 2)
                key = ("up", theta, s4, side, dist, L, third)
            cells[key].append((rho, fire))
        print(f"{name} loaded", flush=True)

    stats = {"exact": 0, "near": 0, "mixed": 0}
    rows_tot = {"exact": 0, "near": 0, "mixed": 0}
    mixed_list = []
    print(f"\n{'cell':>34} {'n':>8} {'fires':>7} {'errs':>6} "
          f"{'rate':>8} {'c*':>9}")
    for key in sorted(cells):
        pairs = cells[key]
        n = len(pairs)
        if n < 200:
            continue
        e, c, nf = best_step(pairs)
        if nf == 0 or nf == n:
            cls = "exact" if e == 0 else "near"
        elif e == 0:
            cls = "exact"
        elif e <= max(3, 0.002 * n):
            cls = "near"
        else:
            cls = "mixed"
            mixed_list.append((e / n, key, n, nf, e, c))
        stats[cls] += 1
        rows_tot[cls] += n
        mark = {"exact": "EXACT", "near": "near", "mixed": ""}[cls]
        if nf or e:
            print(f"{str(key):>34} {n:>8} {nf:>7} {e:>6} "
                  f"{e/n:>8.5f} {c:>9.4f}  {mark}", flush=True)
    print(f"\nSUMMARY: exact {stats['exact']} cells ({rows_tot['exact']} rows), "
          f"near {stats['near']} ({rows_tot['near']}), "
          f"mixed {stats['mixed']} ({rows_tot['mixed']})")
    mixed_list.sort(reverse=True)
    print("\nworst mixed cells:")
    for rate, key, n, nf, e, c in mixed_list[:15]:
        print(f"  {key}: {e}/{n} (fires {nf}) c*={c:.4f}")


if __name__ == "__main__":
    main()
