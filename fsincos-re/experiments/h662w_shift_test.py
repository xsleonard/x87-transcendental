#!/usr/bin/env python3
"""h662w: is the lud2 effect an additive margin shift at all?

h662v: folding lud2 at its natural column is refuted (near-tie
margins are tiny vs the tail's weight; rates shift only ~7 points
per lud2 step).  Additive-model signature: the class-rate-vs-
margin curves for lud2 = 0..3 must be HORIZONTAL SHIFTS of each
other by the effective weight.  Test: per stratum, build fine-
resolution rate curves r_l(x) where x = gap to the boundary
(up: 2^kf - Vlow; dn: Vlow), for each lud2; then find the shift s
minimizing the L2 distance between r_l(x) and r_0(x - l*s).
Additive => consistent s > 0 across strata and l, quality good.
Non-additive => no aligning shift (curves differ in shape/level).
Uses h662v caches.
"""
import pickle
from collections import defaultdict

XBITS = 16   # gap resolution: x = gap * 2^XBITS >> kf
NB = 256     # curve buckets over the observed x range


def curves(rows, strat):
    pts = defaultdict(list)
    for r in rows:
        if (r[0], r[1], r[2], r[3], r[4]) != strat:
            continue
        sign = r[0]
        kf, Vlow, alsb, lt8 = r[12], r[13], r[14], r[15]
        lud2 = lt8 >> 6
        gap = ((1 << kf) - Vlow) if sign == "up" else Vlow
        x = gap * (1 << XBITS) >> kf
        pts[lud2].append((x, r[6]))
    return pts


def buckets(samples, lo, wid):
    t = defaultdict(lambda: [0, 0])
    for x, c in samples:
        t[(x - lo) // wid][c] += 1
    return {b: v[1] / (v[0] + v[1]) for b, v in t.items()
            if sum(v) >= 30}


def main():
    c9 = pickle.load(open("h662v_comb9.pkl", "rb"))
    print(f"{len(c9)} comb9 rows", flush=True)

    cnt = defaultdict(int)
    for r in c9:
        cnt[(r[0], r[1], r[2], r[3], r[4])] += 1
    top = sorted(cnt, key=cnt.get, reverse=True)[:6]

    for strat in top:
        pts = curves(c9, strat)
        allx = [x for l in pts for x, c in pts[l]]
        if not allx:
            continue
        lo, hi = min(allx), max(allx)
        wid = max((hi - lo) // NB, 1)
        r0 = buckets(pts.get(0, []), lo, wid)
        print(f"\nstratum {strat} (n={cnt[strat]}), gap range "
              f"[{lo},{hi}] wid={wid}:")
        if len(r0) < 10:
            print("  lud2=0 curve too sparse")
            continue
        for l in (1, 2, 3):
            rl = buckets(pts.get(l, []), lo, wid)
            common0 = set(r0)
            best = None
            for s in range(-40, 41):
                com = [(b, rl[b]) for b in rl if b + l * s in r0]
                if len(com) < 8:
                    continue
                d = sum((rl[b] - r0[b + l * s]) ** 2
                        for b, _ in com) / len(com)
                if best is None or d < best[0]:
                    best = (d, s, len(com))
            zero = None
            com = [(b, rl[b]) for b in rl if b in r0]
            if len(com) >= 8:
                zero = sum((rl[b] - r0[b]) ** 2
                           for b, _ in com) / len(com)
            if best:
                print(f"  lud2={l}: best shift {best[1]:+3d} "
                      f"bkts (rmse {best[0]**0.5:.4f}, "
                      f"{best[2]} pts) vs shift0 rmse "
                      f"{(zero or 0)**0.5:.4f}")
            # curve level summary
            n = len(pts.get(l, []))
            rate = sum(c for _, c in pts.get(l, [])) / max(n, 1)
            print(f"           overall rate {rate:.4f} (n={n})")


if __name__ == "__main__":
    main()
