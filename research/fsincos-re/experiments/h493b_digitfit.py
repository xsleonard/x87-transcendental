#!/usr/bin/env python3
"""h493b: digit-selection model fit.  Per stratum, boundary =
piecewise-constant theta_D over XT regions, breakpoints and levels
constrained to the twelfths grid (SRT-style selection constants).
Model: XT breakpoints (b1 <= b2) from {0..12}/12, levels (t0,t1,t2)
from {0..12}/12 with sentinel 13 = never-fire in that region.
Grid-search on train half, exactness on test half.  Also prints the
fitted constants per stratum to expose the selection table."""
import random
from collections import defaultdict
from multiprocessing import Pool
from h493_curvefit import build
SC = 60
ONE = 1 << SC

def fit_stratum(args):
    cell, pts = args
    rnd = random.Random(hash(cell) & 0xffff)
    train, test = [], []
    for p in pts:
        (train if rnd.random() < 0.5 else test).append(p)
    best = None
    tw = [i * ONE // 12 for i in range(13)] + [ONE * 2]
    for b1i in range(0, 13, 1):
        for b2i in range(b1i, 13, 1):
            b1, b2 = tw[b1i], tw[b2i]
            # partition train by region, pick best level per region
            regs = [[], [], []]
            for XT, XD, XP, XE, fire in train:
                r = 0 if XT < b1 else (1 if XT < b2 else 2)
                regs[r].append((XD, fire))
            levels = []
            errs = 0
            for reg in regs:
                if not reg:
                    levels.append(13)
                    continue
                bl, be = 13, sum(f for _, f in reg)
                for li in range(0, 14):
                    lv = tw[li] if li < 13 else ONE * 2
                    e = sum(1 for d, f in reg
                            if (d >= lv) != f)
                    if e < be:
                        be, bl = e, li
                levels.append(bl)
                errs += be
            if best is None or errs < best[0]:
                best = (errs, b1i, b2i, tuple(levels))
    errs, b1i, b2i, levels = best
    te = 0
    tn = 0
    tw2 = [i * ONE // 12 for i in range(13)] + [ONE * 2]
    for XT, XD, XP, XE, fire in test:
        r = 0 if XT < tw2[b1i] else (1 if XT < tw2[b2i] else 2)
        lv = tw2[levels[r]] if levels[r] < 13 else ONE * 2
        te += ((XD >= lv) != fire)
        tn += 1
    return cell, len(pts), errs, len(train), te, tn, b1i, b2i, levels

def main():
    rows = []
    with open("h491_mapdata.tsv") as fh:
        fh.readline()
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if f[7] in ("CLEAN", "FIRE"):
                rows.append((f[0], f[7] == "FIRE"))
    with Pool(8) as pool:
        data = pool.map(build, rows, chunksize=500)
    strata = defaultdict(list)
    for cell, XT, XD, XP, XE, fire in data:
        strata[cell].append((XT, XD, XP, XE, fire))
    jobs = [(c, pts) for c, pts in sorted(strata.items())
            if len(pts) >= 500
            and 0 < sum(p[-1] for p in pts) < len(pts)]
    with Pool(8) as pool:
        out = pool.map(fit_stratum, jobs, chunksize=1)
    tot = terr = 0
    print(f"{'stratum':22s} {'n':>6s} {'train-err':>9s} "
          f"{'test-err':>8s} {'test-acc':>8s}  b1/12 b2/12 levels/12")
    for cell, n, errs, ntr, te, tn, b1i, b2i, levels in out:
        tot += tn
        terr += te
        print(f"{str(cell):22s} {n:6d} {errs:9d} {te:8d} "
              f"{1 - te/tn:8.4f}  {b1i:5d} {b2i:5d} {levels}")
    print(f"\nTOTAL holdout: {terr}/{tot} errors "
          f"(acc {1 - terr/tot:.4f})")

if __name__ == "__main__":
    main()
