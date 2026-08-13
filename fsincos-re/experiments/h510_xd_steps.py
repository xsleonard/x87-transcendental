#!/usr/bin/env python3
"""h510: XD step map for dist=7/8 strata (comb-3).

Per (dist, low3): partition XD into twelfths, free-slope line fit per
twelfth (coarse 1/8192 then 1/65536 refine), then merge adjacent
twelfths whose lines agree.  Output: step positions (candidates 1/3,
1/2, 2/3, 5/6...) and per-segment (slope, intercept) — clean slopes
for the identity hunt (incl. the 1/(2*sqrt(2)) candidate).
"""
import math
from collections import defaultdict
from multiprocessing import Pool
from h509_d8_regions import built_comb3, best_c


def fit_free(pts):
    res = []
    for si in range(int(0.02 * 8192), int(0.40 * 8192) + 1, 4):
        s = si / 8192
        e, c = best_c(pts, s)
        res.append((e, s, c))
    res.sort()
    emin, sb, cb = res[0]
    if cb is None:
        return emin, None, None, None, None
    res2 = []
    for si in range(int((sb - 0.004) * 65536),
                    int((sb + 0.004) * 65536) + 1, 2):
        s = si / 65536
        e, c = best_c(pts, s)
        res2.append((e, s, c))
    res2.sort()
    emin, sb, cb = res2[0]
    band = sorted(s for e, s, c in res2 if e <= emin + 2)
    return emin, sb, cb, band[0], band[-1]


def one_stratum(args):
    (dist, low3), pts = args
    cells = defaultdict(list)
    for p in pts:
        k = min(11, int(p[1] * 12))
        cells[k].append(p)
    out = [f"\n=== d{dist} low3={low3}  n={len(pts)} "
           f"fires={sum(p[3] for p in pts)}"]
    segs = []
    for k in sorted(cells):
        sub = cells[k]
        n = len(sub)
        n1 = sum(p[3] for p in sub)
        lo, hi = k / 12, (k + 1) / 12
        if n < 400 or min(n1, n - n1) < 25:
            tag = ("always" if n1 == n and n else
                   "never" if n1 == 0 else f"sparse({n1}/{n})")
            out.append(f"  XD[{lo:.3f},{hi:.3f}) n={n:6d} {tag}")
            segs.append((k, tag, None, None, None))
            continue
        emin, s, c, blo, bhi = fit_free(sub)
        if s is None:
            out.append(f"  XD[{lo:.3f},{hi:.3f}) n={n:6d} "
                       f"fires={n1:5d} never-fire-opt errs={emin}")
            segs.append((k, "nfopt", None, None, None))
            continue
        out.append(f"  XD[{lo:.3f},{hi:.3f}) n={n:6d} fires={n1:5d} "
                   f"errs={emin:5d} ({emin/n:.4f}) s={s:.6f} "
                   f"1/s={1/s:7.3f} c={c:.6f} "
                   f"band=[{blo:.5f},{bhi:.5f}]")
        segs.append((k, "line", s, c, emin / n))
    # merge report
    merged = []
    for k, tag, s, c, r in segs:
        if merged and merged[-1][1] == tag and tag == "line" \
                and abs(merged[-1][2] - s) < 0.0025 \
                and abs(merged[-1][3] - c) < 0.0025:
            merged[-1][0].append(k)
            continue
        if merged and tag != "line" and merged[-1][1] == tag:
            merged[-1][0].append(k)
            continue
        merged.append([[k], tag, s, c])
    desc = []
    for ks, tag, s, c in merged:
        span = f"[{ks[0]/12:.3f},{(ks[-1]+1)/12:.3f})"
        if tag == "line":
            desc.append(f"{span}: s={s:.5f} c={c:.5f}")
        else:
            desc.append(f"{span}: {tag}")
    out.append("  SEGMENTS: " + " | ".join(desc))
    # irrational identity candidates for clean segment slopes
    for ks, tag, s, c in merged:
        if tag != "line":
            continue
        for name, val in [("1/(2sqrt2)", 1 / (2 * math.sqrt(2))),
                          ("1/sqrt2", 1 / math.sqrt(2)),
                          ("sqrt2/4", math.sqrt(2) / 4)]:
            if abs(s - val) < 0.0012:
                out.append(f"  IDENTITY? seg {ks} slope {s:.6f} "
                           f"~ {name} = {val:.6f}")
    return "\n".join(out)


def main():
    data = built_comb3()
    strata = defaultdict(list)
    for cell, XT, XD, mf, fire in data:
        dist, low3, rud = cell
        if dist in (7, 8):
            strata[(dist, low3)].append((XT, XD, mf, fire))
    jobs = [(k, v) for k, v in sorted(strata.items())
            if sum(p[3] for p in v) > 0]
    with Pool(8) as pool:
        for block in pool.imap(one_stratum, jobs, chunksize=1):
            print(block, flush=True)


if __name__ == "__main__":
    main()
