#!/usr/bin/env python3
"""h627: pin the pivot (m0) and the reciprocal-slope ladder step to
full precision from the comb-7 hardware labels, then test closed forms.

Mechanism target (HANDOFF item 4 / answer criterion): the fire boundary
in the (XT, m) plane is a pencil of lines m = s(low3)*XT + c through a
shared pivot; the notes report 1/s arithmetic in low3 with step 2.9257
and pivot 0.707687 (whose square is ~0.5008, i.e. m^2 just above 1/2).
Refit against real labels; report high-precision s(low3), the pivot,
and the ladder step; test closed forms.
"""
import sys, math
from collections import defaultdict
from multiprocessing import Pool
sys.path.insert(0, "/Users/steve/llm/x87-transcendental/fsincos-re/experiments")
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h500_plane_m import build

TIES = "ties_comb4.txt"
PREFIX = "comb4"


def load():
    rows, seen = [], set()
    for lineS in open(TIES):
        f = lineS.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        rows.append(f)
    inputs = sorted(f[0] for f in rows)
    order = {m: i for i, m in enumerate(inputs)}
    st = {md: open(f"{PREFIX}_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    out = []
    for f in rows:
        R, ce, i = int(f[7], 16), int(f[8]), order[f[0]]
        hw, bad = [], False
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            if t[0] != "OK":
                bad = True
                break
            hw.append(int(t[2], 16))
        if bad:
            continue
        clean = [final_cosine_result(-R, ce, md) for md in ROUNDING_MODES]
        fired = [final_cosine_result(-(R - 1), ce, md) for md in ROUNDING_MODES]
        if hw == clean:
            out.append((f[0], False))
        elif hw == fired:
            out.append((f[0], True))
    return out


def best_c_and_margin(pts, s):
    """For boundary m = s*XT + c, fire iff m >= boundary (or <). Return
    (errors, c_mid, gap) at the optimal threshold c using the residual
    r = m - s*XT; choose split direction that minimizes errors."""
    arr = sorted((m - s * XT, fire) for XT, m, fire in pts)
    n = len(arr)
    tot1 = sum(fire for _, fire in arr)
    # try "fire iff r >= c": sweep c between consecutive residuals
    # errors(c) = (#fire below c) + (#nonfire at/above c)
    below1 = 0          # fires with r < c
    above0 = n - tot1    # nonfires with r >= c  (start c = -inf)
    best = (n + 1, None, None)        # errors, c, gap
    for idx in range(n + 1):
        err = below1 + above0
        rlo = arr[idx - 1][0] if idx > 0 else arr[0][0] - 1e-9
        rhi = arr[idx][0] if idx < n else arr[-1][0] + 1e-9
        if err < best[0]:
            best = (err, 0.5 * (rlo + rhi), rhi - rlo)
        if idx < n:
            r, fire = arr[idx]
            if fire:
                below1 += 1
            else:
                above0 -= 1
    # also try opposite polarity: "fire iff r < c"
    below0 = 0
    above1 = tot1
    best2 = (n + 1, None, None)
    for idx in range(n + 1):
        err = below0 + above1
        rlo = arr[idx - 1][0] if idx > 0 else arr[0][0] - 1e-9
        rhi = arr[idx][0] if idx < n else arr[-1][0] + 1e-9
        if err < best2[0]:
            best2 = (err, 0.5 * (rlo + rhi), rhi - rlo)
        if idx < n:
            r, fire = arr[idx]
            if not fire:
                below0 += 1
            else:
                above1 -= 1
    return best if best[0] <= best2[0] else best2


def fit_line(pts):
    """Fine 2D search for s minimizing boundary errors; refine."""
    best = (len(pts) + 1, None, None, None)
    lo, hi, step = 0.02, 0.40, 0.001
    for _ in range(4):
        si = lo
        local = (len(pts) + 1, None, None, None)
        while si <= hi:
            e, c, gap = best_c_and_margin(pts, si)
            if (e, -(gap or 0)) < (local[0], -(local[3] or 0)):
                local = (e, si, c, gap)
            si += step
        best = local
        lo, hi, step = best[1] - step, best[1] + step, step / 10
    return best  # (errors, s, c, gap)


def main():
    print("loading comb7 labels ...", flush=True)
    labeled = load()
    print(f"  {len(labeled)} labeled tie rows", flush=True)
    with Pool(8) as pool:
        data = pool.map(build, labeled, chunksize=2000)
    # dist=9 window, pivot pencil isolation (per h518 classify)
    strata = defaultdict(list)
    for (dist, low3, rud), XT, XD, mf, fire in data:
        if dist != 9 or not (0.656 <= mf < 0.938):
            continue
        # isolate the shared-pivot branch used in h518
        if low3 == 4 and XD < 1/3:
            continue
        if low3 == 6 and XD >= 1/3:
            continue
        if low3 in (4, 5, 6):
            strata[low3].append((XT, mf, fire))
    print(f"\n{'low3':>4} {'n':>8} {'fires':>7} {'frac':>6} {'errs':>6} "
          f"{'slope s':>12} {'pivot c':>12} {'1/s':>10}")
    fits = {}
    for low3 in (4, 5, 6):
        pts = strata[low3]
        n1 = sum(p[2] for p in pts)
        frac = n1 / max(1, len(pts))
        e, s, c, gap = fit_line(pts)
        if c is None:
            print(f"{low3:>4} {len(pts):>8} {n1:>7} {frac:>6.3f} "
                  f"{e:>6} pure/trivial split (s={s})")
            continue
        fits[low3] = (s, c)
        print(f"{low3:>4} {len(pts):>8} {n1:>7} {frac:>6.3f} "
              f"{e:>6} {s:>12.7f} {c:>12.7f} {1/s:>10.5f}")
    if set(fits) != {4, 5, 6}:
        print("\n[!] not all three pivot strata gave a clean line; "
              "inspect fractions above before closed-form step.")
        return

    # ---- ladder step: 1/s arithmetic in low3 ----
    inv = {k: 1.0 / v[0] for k, v in fits.items()}
    steps = [inv[5] - inv[4], inv[6] - inv[5]]
    step = sum(steps) / len(steps)
    print(f"\n1/s values: 4->{inv[4]:.5f} 5->{inv[5]:.5f} 6->{inv[6]:.5f}")
    print(f"ladder steps: {steps[0]:.5f}, {steps[1]:.5f}  mean={step:.6f}")
    # linear fit 1/s = A + B*low3
    xs = [4, 5, 6]
    ys = [inv[4], inv[5], inv[6]]
    xm, ym = sum(xs)/3, sum(ys)/3
    B = sum((x-xm)*(y-ym) for x, y in zip(xs, ys)) / sum((x-xm)**2 for x in xs)
    A = ym - B*xm
    print(f"1/s = {A:.5f} + {B:.6f}*low3   (B = ladder step)")

    # ---- pivot: weighted mean of the three c's ----
    piv = sum(c for _, c in fits.values()) / 3
    print(f"\npivot m0 (mean of 3 c) = {piv:.7f}")
    print(f"   m0^2 = {piv**2:.7f}   (1/2 + {piv**2-0.5:.7f})")
    print(f"   1/sqrt2 = {1/math.sqrt(2):.7f}   diff = {piv-1/math.sqrt(2):+.7f}")

    # ---- closed-form probes for the step B ----
    print("\n--- closed-form probes for ladder step B ---")
    cands = {
        "3": 3.0, "2*sqrt2*... ": 2*math.sqrt(2),
        "1/ln2 *2": 2/math.log(2), "e": math.e,
        "3*(1-1/32)": 3*(1-1/32), "log2(7.6)": math.log2(7.6),
        "1/(4*m0^3) form?": 1/(4*piv**3),
        "1/(2*m0-1)?": None,
    }
    for name, v in cands.items():
        if v is None:
            continue
        print(f"   {name:20} = {v:.6f}   |B-.| = {abs(B-v):.6f}")


if __name__ == "__main__":
    main()
