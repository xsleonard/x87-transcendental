#!/usr/bin/env python3
"""h657f: theta ladder — within-cell autopsy of the thinning discriminator.

h657e: mixed cells have exact-integer lattice thresholds (beta on the
native lattice, closed-form candidate = one integer tap -g*theta inside
the u-table floor), but 5-25 percent within-cell mixing that NO constant
threshold (nor y- or S-linear model) explains.  The discriminator varies
within cells and is not y = (u*2^66 - M)/2^66 itself.

This script, for the biggest mixed cells: split rows into the y-bands
around the cell's integer threshold; within each band, census fire rate
against (a) fine xd60 (1/24 bins — the next 8/3-lattice tap level),
(b) S = 2*sqlow-L fraction (1/8 bins), (c) sR.  Then per (cell, xd24)
subcell: best constant + best y-threshold — does the mixing purify?
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

TARGETS = [
    ("dn", 1, 67, 0, 8, 6, 0),
    ("dn", 1, 67, 0, 8, 4, 2),
    ("dn", 1, 66, 1, 9, 7, 2),
    ("dn", 1, 66, 1, 9, 6, 1),
    ("up", -1, 66, 1, 9, 2, 0),
    ("up", -1, 66, 1, 9, 3, 0),
    ("up", -1, 67, 1, 8, 6, 0),
    ("up", -2, 66, 1, 9, 1, 0),
]


def u_closed(dist, s4, side, L, b1, b2):
    a, G1, G2, p, Q, K, par, W = QUAD[(s4, side)]
    return (K * ((a * L + G1 * b1 + G2 * b2 + p * (L % 2) + W(dist)) // Q)
            + par * (L % 2))


def best_1d(vals):
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
    tset = set(TARGETS)
    data = defaultdict(list)
    for name in ("comb7", "comb8"):
        rows = pickle.load(open(f"h657_{name}.pkl", "rb"))
        for theta, dist, s4, side, L, xd60, sR, label, M, sqlow in rows:
            b1 = 1 if 3 * xd60 >= X60 else 0
            b2 = 1 if 3 * xd60 >= 2 * X60 else 0
            sign = "dn" if theta > 0 else "up"
            key = (sign, theta, s4, side, dist, L, b1 + b2)
            if key not in tset:
                continue
            u = u_closed(dist, s4, side, L, b1, b2)
            if sign == "dn":
                y = (u * UNIT - M) / UNIT
                fire = int(label == 1)
            else:
                y = (M - u * UNIT) / UNIT
                fire = int(label == 2)
            S = (2 * sqlow - L) / UNIT
            xf = xd60 / 2**60
            data[key].append((y, xf, S, sR, fire))
        print(f"{name} loaded", flush=True)

    for key in TARGETS:
        pts = data.get(key, [])
        if not pts:
            continue
        n = len(pts)
        nf = sum(p[4] for p in pts)
        print(f"\n===== {key}: n={n} fires={nf} ({nf/n:.3f}) =====")

        # y-band structure
        yb = defaultdict(lambda: [0, 0])
        for y, xf, S, sR, f in pts:
            yb[int(y) if y >= 0 else int(y) - 1][f] += 1
        print("  y-band: clean/fire  " + "  ".join(
            f"[{b}]:{yb[b][0]}/{yb[b][1]}" for b in sorted(yb)))

        # dominant mixed band = the one with most min(clean,fire)
        band = max(yb, key=lambda b: min(yb[b][0], yb[b][1]))
        sub = [p for p in pts if int(p[0] if p[0] >= 0 else p[0] - 1) == band]
        print(f"  mixed band [{band}]: n={len(sub)} "
              f"fires={sum(p[4] for p in sub)}")

        # (a) fine xd 1/24 bins within the mixed band
        xb = defaultdict(lambda: [0, 0])
        for y, xf, S, sR, f in sub:
            xb[int(xf * 24)][f] += 1
        print("  xd24 bins (clean/fire fire%):")
        line = []
        for b in sorted(xb):
            c0, c1 = xb[b]
            line.append(f"{b}:{c0}/{c1}={c1/(c0+c1):.2f}")
        print("    " + "  ".join(line))

        # (b) S 1/8 bins
        sb = defaultdict(lambda: [0, 0])
        for y, xf, S, sR, f in sub:
            sb[int(S * 8)][f] += 1
        print("  S8 bins: " + "  ".join(
            f"{b/8:.3f}:{sb[b][0]}/{sb[b][1]}={sb[b][1]/sum(sb[b]):.2f}"
            for b in sorted(sb)))

        # (c) sR
        rb = defaultdict(lambda: [0, 0])
        for y, xf, S, sR, f in sub:
            rb[sR][f] += 1
        print("  sR: " + "  ".join(
            f"{b}:{rb[b][0]}/{rb[b][1]}" for b in sorted(rb)))

        # purity: per xd24 subcell of the mixed band, best y-threshold
        tot_err = 0
        pure = impure = 0
        for b, grp in [(b, [p for p in sub if int(p[1] * 24) == b])
                       for b in sorted(xb)]:
            if len(grp) < 30:
                continue
            e, t = best_1d([(p[0], p[4]) for p in grp])
            tot_err += e
            if e <= max(1, 0.01 * len(grp)):
                pure += 1
            else:
                impure += 1
        print(f"  per-xd24 y-threshold: {tot_err} errs in band; "
              f"pure {pure} / impure {impure} subcells", flush=True)


if __name__ == "__main__":
    main()
