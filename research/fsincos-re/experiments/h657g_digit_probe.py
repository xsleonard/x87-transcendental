#!/usr/bin/env python3
"""h657g: theta ladder — hunt the 3/4 bit-pair in the fireable region.

h657f: inside the fireable region (crisp lattice edge) fire probability
is ~exactly 3/4, flat in xd-fine, S, sR, y-band, theta, direction.
3/4 = two unbiased bits (fire unless both clear) or one 3-bit digit
comparison (P(d >= 2) = 6/8).  sq is fully reconstructible from the
cache (sq = 2^66 + sqlow), so every Booth digit of sq/sqlow/f4 and all
of t4's fine structure are testable NOW (only rdisc needs h657m).

For each target cell's mixed y-bands: cross-tab fire against
  d1 = (sq >> 3) & 7, d2 = (sq >> 6) & 7 (radix-8 Booth digits),
  b34 = (sq >> 3) & 3, b45 = (sq >> 4) & 3 (bit pairs),
  t4 quarter position within 2^s4, frac(y) quarters,
and print any variable whose per-value fire rates leave the 0.70-0.80
band (the flat hypothesis is rejected by that variable).
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
            data[key].append((y, sqlow, M, s4, L, fire))
        print(f"{name} loaded", flush=True)

    for key in TARGETS:
        pts = data.get(key, [])
        if not pts:
            continue
        # mixed y-bands only: keep bands with both classes
        byband = defaultdict(list)
        for p in pts:
            byband[int(p[0]) if p[0] >= 0 else int(p[0]) - 1].append(p)
        sub = []
        for b, grp in byband.items():
            nf = sum(g[5] for g in grp)
            if 0 < nf < len(grp):
                sub.extend(grp)
        n = len(sub)
        nf = sum(g[5] for g in sub)
        print(f"\n===== {key}: fireable-region rows n={n} fires={nf} "
              f"({nf/n:.4f}) =====")

        def xtab(tag, fn, nvals):
            t = defaultdict(lambda: [0, 0])
            for y, sqlow, M, s4, L, f in sub:
                t[fn(y, sqlow, M, s4, L)][f] += 1
            rates = []
            flag = ""
            for v in sorted(t):
                c0, c1 = t[v]
                r = c1 / (c0 + c1) if c0 + c1 else 0
                rates.append(f"{v}:{c0 + c1}={r:.3f}")
                if c0 + c1 >= 50 and not 0.70 <= r <= 0.80:
                    flag = "  <== STRUCTURE"
            print(f"  {tag:>10}: " + "  ".join(rates) + flag, flush=True)

        xtab("d1", lambda y, sl, M, s4, L: (sl >> 3) & 7, 8)
        xtab("d2", lambda y, sl, M, s4, L: (sl >> 6) & 7, 8)
        xtab("b34", lambda y, sl, M, s4, L: (sl >> 3) & 3, 4)
        xtab("b45", lambda y, sl, M, s4, L: (sl >> 4) & 3, 4)
        xtab("b56", lambda y, sl, M, s4, L: (sl >> 5) & 3, 4)
        xtab("t4q", lambda y, sl, M, s4, L:
             ((L * sl - M) * 4) // (1 << s4), 4)
        xtab("t4o", lambda y, sl, M, s4, L:
             ((L * sl - M) * 8) // (1 << s4), 8)
        xtab("fracy", lambda y, sl, M, s4, L: int((y % 1) * 4), 4)
        xtab("sq_hi3", lambda y, sl, M, s4, L: (sl >> 63) & 7, 8)
        xtab("sq_b60", lambda y, sl, M, s4, L: (sl >> 60) & 7, 8)


if __name__ == "__main__":
    main()
