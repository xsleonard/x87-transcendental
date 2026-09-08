#!/usr/bin/env python3
"""h637: first cut at the Booth generate-column model.

Structural prior (HANDOFF h525-h532): the terminal product is a radix-8
Booth array; near a tie the discarded low field is a propagate run, and
the borrow into the retained field is decided by whether a GENERATE
reaches the retention window.  The lowest radix-8 Booth digit d0 recodes
multiplier bits [2:-1] = signed3(low3); it gates the BOTTOM of the
propagate run.

CLAIM under test: the per-low3 boundary slope s(low3) in the dist-9
window is a function of the lowest Booth digit d0(low3), i.e. the
"1/s arithmetic in low3" is really "1/s arithmetic in d0".  Test across
ALL 8 low3 values (not just the 4/5/6 pencil): does 1/s line up on
d0 = [0,1,2,3,-4,-3,-2,-1]?

Reads the h628 feature cache (dist, low3, s4, XT, XTabs, XD, m, fire).
"""
import sys, os, pickle, math
from collections import defaultdict
sys.path.insert(0, "/Users/steve/llm/x87-transcendental/fsincos-re/experiments")

CACHE = "h628_feats.pkl"


def booth8_d0(low3):
    """Lowest radix-8 Booth digit = signed 3-bit value of low3 (overlap
    bit b_{-1}=0 for an integer significand)."""
    return low3 if low3 < 4 else low3 - 8


# ---- line fitter (max-margin, corrected h627 version) ----
def best_c(pts, s):
    arr = sorted((y - s * x, fr) for x, y, fr in pts)
    n = len(arr); tot1 = sum(fr for _, fr in arr)
    below1, above0 = 0, n - tot1
    b1 = (n + 1, None)
    for idx in range(n + 1):
        e = below1 + above0
        if e < b1[0]:
            rlo = arr[idx - 1][0] if idx > 0 else arr[0][0] - 1e-9
            rhi = arr[idx][0] if idx < n else arr[-1][0] + 1e-9
            b1 = (e, 0.5 * (rlo + rhi))
        if idx < n:
            _, fr = arr[idx]
            below1 += fr; above0 -= (1 - fr)
    below0, above1 = 0, tot1
    b2 = (n + 1, None)
    for idx in range(n + 1):
        e = below0 + above1
        if e < b2[0]:
            rlo = arr[idx - 1][0] if idx > 0 else arr[0][0] - 1e-9
            rhi = arr[idx][0] if idx < n else arr[-1][0] + 1e-9
            b2 = (e, 0.5 * (rlo + rhi))
        if idx < n:
            _, fr = arr[idx]
            below0 += (1 - fr); above1 -= fr
    return b1 if b1[0] <= b2[0] else b2


def fit(pts, slo=-0.05, shi=0.40):
    best = (len(pts) + 1, None, None)
    lo, hi, step = slo, shi, (shi - slo) / 380
    for _ in range(4):
        loc = (len(pts) + 1, None, None); si = lo
        while si <= hi:
            e, c = best_c(pts, si)
            if e < loc[0]:
                loc = (e, si, c)
            si += step
        best = loc
        lo, hi, step = best[1] - step, best[1] + step, step / 10
    return best


def main():
    data = pickle.load(open(CACHE, "rb"))
    # dist-9, transition side only (m > 1/sqrt2, s4=66; h636 showed the
    # graded boundary lives there — below is saturated all-fire).
    strata = defaultdict(list)
    # XD isolation matching h518 (the next Booth digit d1 selects the
    # pivot zone; hold it to the shared-pivot branch so d0 sets slope).
    for dist, low3, s4, XT, XTabs, XD, m, fire in data:
        if dist != 9 or not (0.656 <= m < 0.938):
            continue
        if s4 != 66:                 # transition side
            continue
        if low3 == 4 and XD < 1/3:
            continue
        if low3 == 6 and XD >= 1/3:
            continue
        if low3 == 7 and XD >= 2/3:
            continue
        strata[low3].append((XT, m, fire))

    print("dist-9, m>1/sqrt2 (s4=66) side; slope per low3 vs Booth d0\n")
    print(f"{'low3':>4} {'d0':>3} {'n':>7} {'frac':>6} {'errs':>6} "
          f"{'slope s':>10} {'pivot c':>10} {'1/s':>9}")
    rows = []
    for low3 in range(8):
        pts = strata.get(low3, [])
        if len(pts) < 300:
            print(f"{low3:>4} {booth8_d0(low3):>3} {len(pts):>7}  (sparse)")
            continue
        fr = sum(p[2] for p in pts) / len(pts)
        if min(fr, 1 - fr) < 0.02:
            print(f"{low3:>4} {booth8_d0(low3):>3} {len(pts):>7} "
                  f"{fr:>6.3f}  (near-pure, no boundary)")
            continue
        e, s, c = fit(pts)
        d0 = booth8_d0(low3)
        print(f"{low3:>4} {d0:>3} {len(pts):>7} {fr:>6.3f} {e:>6} "
              f"{s:>10.6f} {c:>10.6f} {1/s:>9.4f}")
        rows.append((low3, d0, s, c, 1 / s))

    # --- test 1/s linear in d0 ---
    print("\n--- 1/s vs d0 ---")
    rows.sort(key=lambda r: r[1])
    for low3, d0, s, c, inv in rows:
        print(f"  d0={d0:+d} (low3={low3}): 1/s={inv:8.4f}  pivot={c:.5f}")
    # fit line over the pencil run d0 in {-4,-3,-2} and over ALL
    for label, sub in (("pencil d0∈{-4,-3,-2}",
                        [r for r in rows if r[1] in (-4, -3, -2)]),
                       ("all fitted strata", rows)):
        if len(sub) < 2:
            continue
        xs = [r[1] for r in sub]; ys = [r[4] for r in sub]
        xm, ym = sum(xs)/len(xs), sum(ys)/len(ys)
        den = sum((x-xm)**2 for x in xs)
        B = sum((x-xm)*(y-ym) for x, y in zip(xs, ys))/den
        A = ym - B*xm
        ss_res = sum((y-(A+B*x))**2 for x, y in zip(xs, ys))
        ss_tot = sum((y-ym)**2 for y in ys) or 1e-12
        print(f"\n  [{label}] 1/s = {A:.4f} + {B:.4f}*d0   "
              f"R^2={1-ss_res/ss_tot:.4f}  (n={len(sub)})")
        print(f"     => slope-vs-d0 step |B| = {abs(B):.4f} "
              f"(cf. reciprocal-slope 'ladder step' 2.80/2.9257)")


if __name__ == "__main__":
    main()
