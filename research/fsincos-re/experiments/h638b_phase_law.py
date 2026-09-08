#!/usr/bin/env python3
"""h638b: orientation-aware phase law + second-pivot identification.

h638 part 1 found: per (low3, XD-third) the boundary is essentially exact
(226/176,922) with TWO pivots (c1~0.7076 = the 1/sqrt2 edge; c2~0.7639 /
c3~0.7561) and an apparent ORIENTATION FLIP (fire-above-line vs
fire-below-line) advancing with k = d0 + 4 + [XD >= 1/3]:

    phase(k) = ceil(k/2):  0 -> never fire
                           1 -> fire iff m ABOVE the A-line (pivot c1)
                           2 -> fire iff m BELOW the B-line (pivot c1+s)

This script:
  1. re-fits every (low3, third) stratum on BOTH s4 sides reporting the
     winning orientation and the zero-error feasible slope cone;
  2. scores the global k-phase predictor on all s4=66 window rows;
  3. scans build() internals for bit-length flips at the second pivot
     (c2/c3 candidates), h635-style.
"""
import math, os, pickle, sys
from collections import defaultdict

sys.path.insert(0, "/Users/steve/llm/x87-transcendental/fsincos-re/experiments")

ROWCACHE = "h638_rows.pkl"


def booth8_d0(low3):
    return low3 if low3 < 4 else low3 - 8


# ---- fitter reporting orientation ----
def best_c_orient(pts, s):
    arr = sorted((y - s * x, fr) for x, y, fr in pts)
    n = len(arr); tot1 = sum(fr for _, fr in arr)
    res = []
    for orient in ("above", "below"):
        if orient == "above":     # predict fire when y - s*x > c
            wrong_lo, wrong_hi = 0, n - tot1   # fires below, cleans above
        else:                     # predict fire when y - s*x < c
            wrong_lo, wrong_hi = 0, tot1
        best = (n + 1, None)
        lo_cnt, hi_cnt = wrong_lo, wrong_hi
        for idx in range(n + 1):
            e = lo_cnt + hi_cnt
            if e < best[0]:
                rlo = arr[idx - 1][0] if idx > 0 else arr[0][0] - 1e-9
                rhi = arr[idx][0] if idx < n else arr[-1][0] + 1e-9
                best = (e, 0.5 * (rlo + rhi))
            if idx < n:
                _, fr = arr[idx]
                if orient == "above":
                    lo_cnt += fr; hi_cnt -= (1 - fr)
                else:
                    lo_cnt += (1 - fr); hi_cnt -= fr
        res.append((best[0], orient, best[1]))
    return min(res)


def fit_orient(pts, slo=-0.05, shi=0.40):
    best = (len(pts) + 1, None, None, None)
    lo, hi, step = slo, shi, (shi - slo) / 380
    for _ in range(4):
        loc = (len(pts) + 1, None, None, None); si = lo
        while si <= hi:
            e, orient, c = best_c_orient(pts, si)
            if e < loc[0]:
                loc = (e, si, c, orient)
            si += step
        best = loc
        lo, hi, step = best[1] - step, best[1] + step, step / 10
    return best  # (errs, slope, c, orient)


def slope_cone(pts, orient, slo=0.0, shi=0.12, n=241):
    """range of slopes attaining the minimum error for this orientation"""
    errs = []
    for i in range(n):
        s = slo + (shi - slo) * i / (n - 1)
        arr = best_c_orient(pts, s)
        # keep only the requested orientation
        e = None
        a = sorted((y - s * x, fr) for x, y, fr in pts)
        # recompute for fixed orient
        nn = len(a); tot1 = sum(fr for _, fr in a)
        if orient == "above":
            lo_cnt, hi_cnt = 0, nn - tot1
        else:
            lo_cnt, hi_cnt = 0, tot1
        best = nn + 1
        for idx in range(nn + 1):
            best = min(best, lo_cnt + hi_cnt)
            if idx < nn:
                _, fr = a[idx]
                if orient == "above":
                    lo_cnt += fr; hi_cnt -= (1 - fr)
                else:
                    lo_cnt += (1 - fr); hi_cnt -= fr
        errs.append((s, best))
    mn = min(e for _, e in errs)
    good = [s for s, e in errs if e == mn]
    return mn, min(good), max(good)


def main():
    rows = pickle.load(open(ROWCACHE, "rb"))
    print(f"{len(rows)} rows")
    enriched = []
    for (mhex, fire, dist, sq, f2, p2, n2, s4, XT, sR, XD, mf) in rows:
        low3 = sq & 7
        third = 0 if XD < 1/3 else (1 if XD < 2/3 else 2)
        enriched.append((fire, low3, third, s4, XT, XD, mf, sq, f2, p2, n2))

    # ---------- 1. orientation-aware fits, both s4 sides ----------
    fits = {}
    for s4v in (66, 67):
        strata = defaultdict(list)
        for (fire, low3, third, s4, XT, XD, mf, *_ ) in enriched:
            if s4 != s4v:
                continue
            strata[(low3, third)].append((XT, mf, fire))
        print(f"\n=== s4={s4v}: per (low3, third), orientation-aware ===")
        print(f"{'stratum':>9} {'n':>7} {'frac':>6} {'errs':>5} {'orient':>7} "
              f"{'slope':>9} {'pivot':>9} {'1/s':>8}  slope-cone(0-err)")
        for k in sorted(strata):
            pts = strata[k]
            if len(pts) < 250:
                print(f"{str(k):>9} {len(pts):>7}  (sparse)")
                continue
            frv = sum(p[2] for p in pts) / len(pts)
            if min(frv, 1 - frv) < 0.005:
                print(f"{str(k):>9} {len(pts):>7} {frv:>6.3f}  (pure: "
                      f"{'ALL-FIRE' if frv > 0.5 else 'NEVER-FIRE'})")
                fits[(s4v,)+k] = ("pure", frv > 0.5)
                continue
            e, s, c, orient = fit_orient(pts)
            cone = ""
            if e < 20:
                mn, smin, smax = slope_cone(pts, orient)
                cone = f"[{smin:.4f},{smax:.4f}] e={mn}"
            print(f"{str(k):>9} {len(pts):>7} {frv:>6.3f} {e:>5} {orient:>7} "
                  f"{s:>9.6f} {c:>9.6f} {1/s:>8.3f}  {cone}")
            fits[(s4v,)+k] = ("line", s, c, orient)

    # ---------- 2. global k-phase predictor on s4=66 ----------
    print("\n=== global k-phase predictor (s4=66) ===")
    print("k = d0+4+[XD>=1/3]; phase=ceil(k/2): 0 never, 1 above-A, 2 below-B")
    print("(lines taken from the per-stratum fits above)")
    tot = terr = 0
    perph = defaultdict(lambda: [0, 0])
    for (fire, low3, third, s4, XT, XD, mf, *_ ) in enriched:
        if s4 != 66:
            continue
        d0 = booth8_d0(low3)
        if d0 >= 0:
            pred = 0
            ph = "pos-dead"
        else:
            k = d0 + 4 + (1 if XD >= 1/3 else 0)
            phase = math.ceil(k / 2)
            f = fits.get((66, low3, third))
            if f is None:
                continue
            if phase == 0:
                pred = 0
            elif f[0] == "pure":
                pred = 1 if f[1] else 0
            else:
                _, s, c, orient = f
                above = mf > s * XT + c
                pred = int(above) if orient == "above" else int(not above)
            ph = f"k={k} ph{phase}"
        tot += 1
        bad = (pred != fire)
        terr += bad
        perph[ph][0] += bad
        perph[ph][1] += 1
    print(f"total: {terr} errors / {tot} rows = {terr/tot:.5f}")
    for ph in sorted(perph):
        b, n = perph[ph]
        print(f"  {ph:>10}: {b:>5} / {n}")

    # consistency of phase label with fitted orientation
    print("\nphase-vs-fit consistency (s4=66):")
    for low3 in range(1, 8):
        d0 = booth8_d0(low3)
        for third in range(3):
            f = fits.get((66, low3, third))
            if f is None or d0 >= 0:
                continue
            k = d0 + 4 + (1 if third >= 1 else 0)
            phase = math.ceil(k / 2)
            want = {0: "never", 1: "above", 2: "below"}[phase]
            got = ("all-fire" if f[1] else "never") if f[0] == "pure" else f[3]
            ok = (want == got) or (want == "never" and got == "never")
            print(f"  low3={low3} d0={d0:+d} third={third}: k={k} phase={phase} "
                  f"want={want:>6} fitted={got:>8} {'OK' if ok else 'XX'}")

    # ---------- 3. binade-flip scan for the second pivot ----------
    print("\n=== bit-length flip scan (s4=66 region, fm in [0.70,0.85]) ===")
    print("target pivots: c1=0.7076  c2=0.7639  c3=0.7561")
    cands = {
        "3*sq":   lambda sq, f2, p2, n2: 3 * sq,
        "3*f2":   lambda sq, f2, p2, n2: 3 * f2,
        "3*p2":   lambda sq, f2, p2, n2: 3 * p2,
        "3*n2":   lambda sq, f2, p2, n2: 3 * n2,
        "rprod":  lambda sq, f2, p2, n2: f2 * p2,
        "lprod":  lambda sq, f2, p2, n2: sq * n2,
        "f2":     lambda sq, f2, p2, n2: f2,
        "p2":     lambda sq, f2, p2, n2: p2,
        "n2":     lambda sq, f2, p2, n2: n2,
        "sq*p2":  lambda sq, f2, p2, n2: sq * p2,
        "f2*n2":  lambda sq, f2, p2, n2: f2 * n2,
        "sq*f2":  lambda sq, f2, p2, n2: sq * f2,
    }
    byfm = sorted((mf, sq, f2, p2, n2)
                  for (fire, low3, third, s4, XT, XD, mf, sq, f2, p2, n2)
                  in enriched if s4 == 66)
    for name, fn in cands.items():
        flips = []
        prev = None
        for mf, sq, f2, p2, n2 in byfm:
            bl = fn(sq, f2, p2, n2).bit_length()
            if prev is not None and bl != prev[0]:
                flips.append((0.5 * (prev[1] + mf), prev[0], bl))
            prev = (bl, mf)
        if flips:
            desc = ", ".join(f"{fm:.5f} ({a}->{b})" for fm, a, b in flips[:6])
            print(f"  {name:>7}: {desc}")
        else:
            print(f"  {name:>7}: no flips")


if __name__ == "__main__":
    main()
