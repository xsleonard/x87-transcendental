#!/usr/bin/env python3
"""h628: the s4-relative forward test.

Finding (h627): the dist-9 pivot pencil's shared pivot is m=1/sqrt2, the
exact m^4=1/4 binade edge where f4=square^2 loses a bit and the s4 chop
boundary flips (s4: 67 below -> 66 above).  The boundary m = s(low3)*XT + c
has a low3-DEPENDENT slope in the hardware-normalized frame XT = t4/2^s4.

HYPOTHESIS: that low3 slope-pencil is an artifact of MERGING the two s4
sides.  If we split the pencil by s4 side, each side should collapse to a
SINGLE low3-independent boundary (the borrow is one threshold on the
discarded field; low3's apparent tilt = the 2x renormalization at the
flip).  If low3 dependence PERSISTS per side, low3 is a genuine input.

Caches built features to h628_feats.pkl so the analysis can be re-run fast.
"""
import sys, os, pickle
from collections import defaultdict
from multiprocessing import Pool
sys.path.insert(0, "/Users/steve/llm/x87-transcendental/fsincos-re/experiments")
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)

E2M = -66
SC = 60
TIES = "ties_comb4.txt"
PREFIX = "comb4"
CACHE = "h628_feats.pkl"


def feat(args):
    mhex, fire = args
    m = int(mhex, 16)
    mag = (0, E2M, m)
    square = mul_round(mag, mag, 67, "chop")
    fourth = mul_round(square, square, 67, "chop")
    neg = build_chain(fourth, C6_5, C6_3, C6_1, 67, 64, "rn", False, False, False)
    pos = build_chain(fourth, C6_6, C6_4, C6_2, 67, 64, "rn", False, False, False)
    left = mul_round(square, neg, 67, "chop")
    right = mul_round(fourth, pos, 67, "chop")
    low3 = square[2] & 7
    dist = abs(left[1] - right[1])
    f4 = square[2] * square[2]
    s4 = f4.bit_length() - 67
    t4 = f4 & ((1 << s4) - 1)
    XT = ((t4 << SC) >> s4) / 2**SC              # hardware-normalized [0,1)
    # s4-continuous ABSOLUTE discarded field: fixed 67-bit low cut of f4,
    # expressed in units of the coarse (s4=67) retained ulp.  Continuous
    # across the flip because the cut position is fixed in absolute bits.
    tabs = f4 & ((1 << 67) - 1)
    XTabs = tabs / 2**67
    rprod = fourth[2] * pos[2]
    sR = rprod.bit_length() - 67
    rdisc = rprod & ((1 << sR) - 1)
    XD = ((rdisc << SC) >> sR) / 2**SC
    return (dist, low3, s4, XT, XTabs, XD, m / 2**64, int(fire))


def load():
    rows, seen = [], set()
    for lineS in open(TIES):
        f = lineS.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        rows.append(f)
    inputs = sorted(f[0] for f in rows)
    order = {mm: i for i, mm in enumerate(inputs)}
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


def build_cache():
    labeled = load()
    print(f"  {len(labeled)} labeled rows; building features ...", flush=True)
    with Pool(8) as pool:
        data = pool.map(feat, labeled, chunksize=2000)
    with open(CACHE, "wb") as fh:
        pickle.dump(data, fh)
    return data


# ---- boundary line fit (fixed correct fitter from h627) ----
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
        loc = (len(pts) + 1, None, None)
        si = lo
        while si <= hi:
            e, c = best_c(pts, si)
            if e < loc[0]:
                loc = (e, si, c)
            si += step
        best = loc
        lo, hi, step = best[1] - step, best[1] + step, step / 10
    return best  # (errors, s, c)


def main():
    if os.path.exists(CACHE):
        print(f"loading cache {CACHE}")
        data = pickle.load(open(CACHE, "rb"))
    else:
        print("no cache; building (slow) ...")
        data = build_cache()
    # dist-9 pivot pencil, isolated XD branches (as h518)
    pencil = defaultdict(list)          # (low3, s4side) -> [(XT, m, fire)]
    pencil_abs = defaultdict(list)      # (low3, s4side) -> [(XTabs, m, fire)]
    merged = defaultdict(list)          # low3 -> merged over s4 (control)
    for dist, low3, s4, XT, XTabs, XD, m, fire in data:
        if dist != 9 or not (0.656 <= m < 0.938):
            continue
        if low3 == 4 and XD < 1/3:
            continue
        if low3 == 6 and XD >= 1/3:
            continue
        if low3 not in (4, 5, 6):
            continue
        side = "hi" if s4 == 66 else "lo"     # 66 = above pivot
        pencil[(low3, side)].append((XT, m, fire))
        pencil_abs[(low3, side)].append((XTabs, m, fire))
        merged[low3].append((XT, m, fire))

    print("\n=== CONTROL: merged over s4 (hardware-normalized XT) ===")
    print(f"{'low3':>4} {'n':>7} {'errs':>6} {'slope':>10} {'pivot c':>10}")
    for low3 in (4, 5, 6):
        e, s, c = fit(merged[low3])
        print(f"{low3:>4} {len(merged[low3]):>7} {e:>6} {s:>10.6f} {c:>10.6f}")

    for frame, tab in (("hardware-normalized XT", pencil),
                       ("s4-continuous absolute XTabs", pencil_abs)):
        print(f"\n=== SPLIT BY s4 SIDE, frame = {frame} ===")
        print(f"{'low3':>4} {'side':>4} {'n':>7} {'frac':>6} {'errs':>6} "
              f"{'slope':>10} {'pivot c':>10}")
        for side in ("lo", "hi"):
            for low3 in (4, 5, 6):
                pts = tab[(low3, side)]
                if len(pts) < 200:
                    print(f"{low3:>4} {side:>4} {len(pts):>7} (sparse)")
                    continue
                fr = sum(p[2] for p in pts) / len(pts)
                e, s, c = fit(pts)
                print(f"{low3:>4} {side:>4} {len(pts):>7} {fr:>6.3f} "
                      f"{e:>6} {s:>10.6f} {c:>10.6f}")
        print("  -> COLLAPSE test: are slope & pivot ~equal across low3 "
              "within each side?")


if __name__ == "__main__":
    main()
