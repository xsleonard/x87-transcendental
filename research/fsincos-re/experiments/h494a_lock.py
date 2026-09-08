#!/usr/bin/env python3
"""h494a: refit the digit-selection tables on ALL current data and
LOCK them for fresh-data exactness validation.  Only strata with
full-data fit error < 2 percent are claimed.  Writes
h494_locked_tables.json."""
import json
from collections import defaultdict
from multiprocessing import Pool
from h493_curvefit import build
SC = 60
ONE = 1 << SC

def fit_all(args):
    cell, pts = args
    tw = [i * ONE // 12 for i in range(13)] + [ONE * 2]
    best = None
    for b1i in range(0, 13):
        for b2i in range(b1i, 13):
            b1, b2 = tw[b1i], tw[b2i]
            regs = [[], [], []]
            for XT, XD, XP, XE, fire in pts:
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
                    e = sum(1 for d, f in reg if (d >= lv) != f)
                    if e < be:
                        be, bl = e, li
                levels.append(bl)
                errs += be
            if best is None or errs < best[0]:
                best = (errs, b1i, b2i, levels)
    return cell, len(pts), best

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
            if len(pts) >= 500]
    with Pool(8) as pool:
        out = pool.map(fit_all, jobs, chunksize=1)
    tables = {}
    for cell, n, (errs, b1i, b2i, levels) in out:
        rate = errs / n
        claimed = rate < 0.02
        print(f"  {cell} n={n} fit-errs={errs} ({rate:.4f})"
              f"{'  CLAIMED' if claimed else ''}")
        if claimed:
            tables["|".join(str(x) for x in cell)] = {
                "b1": b1i, "b2": b2i, "levels": levels,
                "fit_errs": errs, "n": n}
    with open("h494_locked_tables.json", "w") as fh:
        json.dump(tables, fh, indent=1)
    print(f"\nlocked {len(tables)} strata tables -> "
          f"h494_locked_tables.json")

if __name__ == "__main__":
    main()
