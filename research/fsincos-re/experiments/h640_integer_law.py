#!/usr/bin/env python3
"""h640: the integer closed-form law test.

Reframing the h638 boundary out of the m-frame into the square's own low
field dissolves every fitted constant:

    sqlow = sq - 2^66 (low field of the chopped square, s4=66 side)
    fm - c1 ~ sqlow / (2 c1 2^67)  =>  1/(2 c1 s(d0)) comes out
    8.46 / 10.42 / 12.50 / 14.49 for d0=-4..-1: step EXACTLY 2,
    gains (4*low3+1)/16 = 17/16, 21/16, 25/16, 29/16.

    Then 1/s = 4 c1 |...|: intercept 33/sqrt2 = 23.335 (measured 23.36)
    and ladder step 2 sqrt2 = 2.828 (measured 2.85): both h635 "fitted
    constants" are this law seen through the sqrt.

CANDIDATE CLOSED FORM (s4=66, d0<0):
    b = [XD >= 1/3]
    u = ceil((d0+4+b)/2) - 1   in {-1, 0, +1}
    fire  <=>  (4*low3+1) * sqlow  <  16 * (t4 + u*2^66) + C
    d0 >= 0: never fire.

Tests: (1) per-stratum free fit in the (eff, sqlow) frame — slopes should
land on 16/(4*low3+1) and errors should not exceed the fm-frame fits;
(2) forced-slope fit: only C free per stratum — is C constant?
(3) single global C — total errors vs the 226 of the per-stratum
empirical surface (24 fitted numbers -> 1).
"""
import math, pickle, sys
from collections import defaultdict

ROWCACHE = "h638_rows.pkl"


def d0f(l3):
    return l3 if l3 < 4 else l3 - 8


def best_c_below(pts, s):
    """fire iff y - s*x < c; return (errs, c)."""
    arr = sorted((y - s * x, fr) for x, y, fr in pts)
    n = len(arr); tot1 = sum(fr for _, fr in arr)
    lo_cnt, hi_cnt = 0, tot1
    best = (n + 1, None)
    for idx in range(n + 1):
        e = lo_cnt + hi_cnt
        if e < best[0]:
            rlo = arr[idx - 1][0] if idx > 0 else arr[0][0] - 1e-9
            rhi = arr[idx][0] if idx < n else arr[-1][0] + 1e-9
            best = (e, 0.5 * (rlo + rhi))
        if idx < n:
            _, fr = arr[idx]
            lo_cnt += (1 - fr); hi_cnt -= fr
    return best


def fit_below(pts, slo, shi):
    best = (len(pts) + 1, None, None)
    lo, hi, step = slo, shi, (shi - slo) / 380
    for _ in range(4):
        loc = (len(pts) + 1, None, None); si = lo
        while si <= hi:
            e, c = best_c_below(pts, si)
            if e < loc[0]:
                loc = (e, si, c)
            si += step
        best = loc
        lo, hi, step = best[1] - step, best[1] + step, step / 10
    return best


def main():
    rows = pickle.load(open(ROWCACHE, "rb"))
    UNIT = 2**66
    recs = []
    for (mhex, fire, dist, sq, f2, p2, n2, s4, XT, sR, XD, mf) in rows:
        if s4 != 66:
            continue
        low3 = sq & 7
        d0 = d0f(low3)
        b = 1 if XD >= 1 / 3 else 0
        sqlow = sq - UNIT
        f4 = sq * sq
        t4 = f4 & (UNIT - 1)
        u = math.ceil((d0 + 4 + b) / 2) - 1
        recs.append((fire, low3, d0, b, u, sqlow, t4))

    # ---------- 1. free fit in the integer frame ----------
    # x = eff/2^66, y = sqlow/2^66; theory slope = 16/(4*low3+1)
    print("=== free fits: y=sqlow/2^66 vs x=(t4+u*2^66)/2^66, fire below ===")
    print(f"{'d0':>3} {'b':>2} {'u':>2} {'n':>7} {'errs':>5} "
          f"{'slope':>9} {'theory':>9} {'C=c*2^66':>12}")
    strata = defaultdict(list)
    for fire, low3, d0, b, u, sqlow, t4 in recs:
        if d0 >= 0:
            continue
        strata[(d0, b)].append(((t4 + u * UNIT) / UNIT, sqlow / UNIT, fire))
    freefit = {}
    for (d0, b) in sorted(strata):
        pts = strata[(d0, b)]
        th = 4 / (4 * (d0 + 8) + 1)
        fr = sum(p[2] for p in pts) / len(pts)
        if min(fr, 1 - fr) < 0.002:
            print(f"{d0:>3} {b:>2} {'':>2} {len(pts):>7} "
                  f"(pure {'fire' if fr > .5 else 'clean'} {fr:.4f})")
            continue
        e, s, c = fit_below(pts, 0.05, 0.40)
        freefit[(d0, b)] = (e, s, c)
        u = math.ceil((d0 + 4 + b) / 2) - 1
        print(f"{d0:>3} {b:>2} {u:>2} {len(pts):>7} {e:>5} "
              f"{s:>9.5f} {th:>9.5f} {c:>12.6f}")

    # ---------- 2. forced theory slope, C free per stratum ----------
    print("\n=== forced slope 4/(4*low3+1): only C free ===")
    print(f"{'d0':>3} {'b':>2} {'n':>7} {'errs':>5} {'C (x2^66)':>12} "
          f"'C in 2^60 units':>16")
    totn = tote = 0
    for (d0, b) in sorted(strata):
        pts = strata[(d0, b)]
        fr = sum(p[2] for p in pts) / len(pts)
        if min(fr, 1 - fr) < 0.002:
            continue
        th = 4 / (4 * (d0 + 8) + 1)
        e, c = best_c_below(pts, th)
        totn += len(pts); tote += e
        print(f"{d0:>3} {b:>2} {len(pts):>7} {e:>5} {c:>12.6f} "
              f"{c * 64:>16.4f}")
    print(f"  forced-slope total: {tote} errs / {totn}")

    # ---------- 3. single global law ----------
    # fire <=> (4*low3+1)*sqlow - 16*(t4+u*2^66) < C_glob ; scan C_glob
    print("\n=== single global C: fire <=> (4*low3+1)*sqlow - 4*eff < C ===")
    vals = []
    ndead_fire = 0
    for fire, low3, d0, b, u, sqlow, t4 in recs:
        if d0 >= 0:
            ndead_fire += fire
            continue
        lhs = (4 * low3 + 1) * sqlow - 4 * (t4 + u * UNIT)
        vals.append((lhs, fire))
    vals.sort()
    n = len(vals); tot1 = sum(f for _, f in vals)
    lo_cnt, hi_cnt = 0, tot1     # fire iff lhs < C
    best = (n + 1, None)
    for idx in range(n + 1):
        e = lo_cnt + hi_cnt
        if e < best[0]:
            cval = vals[min(idx, n - 1)][0]
            best = (e, cval)
        if idx < n:
            _, f = vals[idx]
            lo_cnt += (1 - f); hi_cnt -= f
    print(f"  d0>=0 rows: {ndead_fire} fires (law says 0)")
    print(f"  d0<0: best C = {best[1]} = {best[1]/2**66:.6f} * 2^66")
    print(f"        errors {best[0]} / {n} = {best[0]/n:.5f}")
    print(f"  (empirical 24-parameter surface: 226 errs / 338172)")

    # error profile around best C per stratum
    C = best[1]
    per = defaultdict(lambda: [0, 0])
    for fire, low3, d0, b, u, sqlow, t4 in recs:
        if d0 >= 0:
            continue
        lhs = (4 * low3 + 1) * sqlow - 4 * (t4 + u * UNIT)
        pred = int(lhs < C)
        per[(d0, b)][0] += (pred != fire)
        per[(d0, b)][1] += 1
    print("\n  per-stratum errors at global C:")
    for k in sorted(per):
        e, nn = per[k]
        print(f"    d0={k[0]:+d} b={k[1]}: {e:>5} / {nn}")


if __name__ == "__main__":
    main()
