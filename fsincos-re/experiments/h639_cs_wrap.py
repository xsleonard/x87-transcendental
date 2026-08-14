#!/usr/bin/env python3
"""h639: the carry-save low-field wrap model, evaluated per row.

The radix-8 Booth PP array of f4 = sq*sq: PP_i = d_i * sq * 8^i, negative
rows as two's complement (mod 2^66 the sign-extension/hot-one detail is
value-equivalent).  Exact low-field wrap count

    w_exact = (sum_i (PP_i mod 2^66)) >> 66        (tree-independent)

is the number of carries the low field REALLY sends into the retained
half.  A bounded predictor sees only the top W columns of each row:

    Y_W  = sum_i ((PP_i mod 2^66) >> (66-W))
    w_pred(W, cin) = (Y_W + cin) >> W

fire_model = sign of (w_pred - w_exact).  Tabulate against hardware fire
per d0 stratum; same machinery on the rprod = f2*p2 array for the XD bit.

Verdict rule: a real mechanism must approach the band error rate
(~0.0007) with FIXED (W, cin); chance-level tables reject the class.
"""
import os, pickle, sys
from collections import defaultdict, Counter
from multiprocessing import Pool

sys.path.insert(0, "/Users/steve/llm/x87-transcendental/fsincos-re/experiments")

ROWCACHE = "h638_rows.pkl"
OUT = "h639_wraps.pkl"
WGRID = (4, 6, 8, 10, 12, 16, 20)


def booth8(y, ndig):
    ds, prev = [], 0
    for i in range(ndig):
        trip = (y >> (3 * i)) & 7
        ds.append(trip + prev - (8 if trip >= 4 else 0))
        prev = (y >> (3 * i + 2)) & 1
    return ds


def lowfield(x, y, cut):
    """rows of the radix-8 array of x*y (y = multiplier), each mod 2^cut"""
    mask = (1 << cut) - 1
    rows = []
    for i, d in enumerate(booth8(y, 23)):
        if d == 0:
            continue
        v = (d * x) << (3 * i)
        rows.append(v & mask)   # python & of negative = two's complement mod
    return rows


def wraps(args):
    (mhex, fire, dist, sq, f2, p2, n2, s4, XT, sR, XD, mf) = args
    out = {}
    for tag, x, y, cut in (("f4", sq, sq, 66), ("rp", f2, p2, 67)):
        rows = lowfield(x, y, cut)
        tot = sum(rows)
        w_exact = tot >> cut
        # verify low-field identity: resolved low field == true product low
        prod = (x * y) & ((1 << cut) - 1)
        assert tot & ((1 << cut) - 1) == prod, (tag, mhex)
        ys = {}
        for W in WGRID:
            ys[W] = sum(r >> (cut - W) for r in rows)
        out[tag] = (w_exact, ys)
    return (sq & 7, s4, XT, XD, mf, fire, out)


def main():
    rows = pickle.load(open(ROWCACHE, "rb"))
    if os.path.exists(OUT):
        data = pickle.load(open(OUT, "rb"))
        print(f"loaded {len(data)} from {OUT}")
    else:
        with Pool(8) as pool:
            data = pool.map(wraps, rows, chunksize=500)
        pickle.dump(data, open(OUT, "wb"))
        print(f"computed {len(data)} rows (low-field identity verified)")

    d0f = lambda l3: l3 if l3 < 4 else l3 - 8

    # ---- 1. does w_exact itself carry the signal? ----
    print("\n=== fire vs w_exact(f4 array), s4=66 ===")
    tab = defaultdict(lambda: [0, 0])
    for low3, s4, XT, XD, mf, fire, out in data:
        if s4 != 66:
            continue
        tab[(d0f(low3), out["f4"][0])][fire] += 1
    for k in sorted(tab):
        c0, c1 = tab[k][0], tab[k][1]
        print(f"  d0={k[0]:+d} w={k[1]:>2}: clean {c0:>6} fire {c1:>6}  "
              f"p(fire)={c1/(c0+c1):.3f}")

    # ---- 2. bounded predictor grids ----
    print("\n=== w_pred(W,cin) - w_exact vs fire (f4 array, s4=66, d0<0) ===")
    best = []
    for W in WGRID:
        for cin in range(0, 4):
            # per-row delta; correlate [delta<0] and [delta>0] with fire
            agree_lo = agree_hi = tot = fires = 0
            per = defaultdict(lambda: [0, 0, 0, 0])
            for low3, s4, XT, XD, mf, fire, out in data:
                if s4 != 66 or d0f(low3) >= 0:
                    continue
                w_exact, ys = out["f4"]
                d = ((ys[W] + cin) >> W) - w_exact
                tot += 1; fires += fire
                agree_lo += (int(d < 0) == fire)
                agree_hi += (int(d > 0) == fire)
                p = per[d0f(low3)]
                p[0] += fire; p[1] += int(d < 0); p[2] += int(d > 0); p[3] += 1
            acc = max(agree_lo, agree_hi) / tot
            best.append((acc, W, cin, agree_lo / tot, agree_hi / tot))
    best.sort(reverse=True)
    print(f"  base rate p(fire)={fires/tot:.3f}; predict-never acc="
          f"{1-fires/tot:.3f}")
    for acc, W, cin, alo, ahi in best[:8]:
        print(f"  W={W:>2} cin={cin}: acc[d<0]={alo:.4f} acc[d>0]={ahi:.4f}")

    # ---- 3. XD bit from the rprod array? ----
    print("\n=== [XD>=1/3] vs rprod-array quantities (s4=66) ===")
    tab2 = defaultdict(lambda: [0, 0])
    for low3, s4, XT, XD, mf, fire, out in data:
        if s4 != 66:
            continue
        b = int(XD >= 1 / 3)
        tab2[("w_exact", out["rp"][0])][b] += 1
    for k in sorted(tab2):
        c0, c1 = tab2[k]
        print(f"  {k[0]} = {k[1]:>2}: b=0 {c0:>6}  b=1 {c1:>6}  "
              f"p(b)={c1/(c0+c1):.3f}")

    # ---- 4. joint: per (d0, w_exact) refit check of the linear law ----
    print("\n=== does w_exact split the (XT,m) boundary? "
          "mean XT and fire rate per (d0, w) ===")
    tab3 = defaultdict(list)
    for low3, s4, XT, XD, mf, fire, out in data:
        if s4 != 66 or d0f(low3) >= 0:
            continue
        tab3[(d0f(low3), out["f4"][0])].append((XT, mf, fire))
    for k in sorted(tab3):
        pts = tab3[k]
        if len(pts) < 500:
            continue
        fr = sum(p[2] for p in pts) / len(pts)
        mXT = sum(p[0] for p in pts) / len(pts)
        mmf = sum(p[1] for p in pts) / len(pts)
        print(f"  d0={k[0]:+d} w={k[1]:>2}: n={len(pts):>6} p(fire)={fr:.3f} "
              f"<XT>={mXT:.3f} <m>={mmf:.3f}")


if __name__ == "__main__":
    main()
