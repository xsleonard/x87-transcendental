#!/usr/bin/env python3
"""h492d: per-stratum linear-boundary angle sweep at scale.
For each (dist, low3, le2, rud) stratum: project points onto
u = cos(a)*XT + sin(a)*XD over 49 angles, best step errors per
angle; report min-error angle and residual rate.  Near-zero
residual at some angle => the gate is linear in (XT, XD) per
stratum and the h487 non-separability was small-sample noise."""
import math
from collections import defaultdict
from multiprocessing import Pool
from h492c_le2_threshold import build, step_errs

ANGLES = [i * math.pi / 96 for i in range(-24, 73)]

def fit_stratum(args):
    cell, pts = args
    n1 = sum(p[3] for p in pts)
    best = (n1 if n1 < len(pts) - n1 else len(pts) - n1, None)
    for a in ANGLES:
        ca, sa = math.cos(a), math.sin(a)
        vals = [(ca * p[0] + sa * p[1], p[3]) for p in pts]
        e, _ = step_errs(vals)
        if e < best[0]:
            best = (e, a)
    return cell, len(pts), n1, best

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
    for cell, XT, XD, XE, fire in data:
        strata[cell].append((XT, XD, XE, fire))
    jobs = [(c, pts) for c, pts in strata.items()
            if len(pts) >= 500 and
            0 < sum(p[3] for p in pts) < len(pts)]
    with Pool(8) as pool:
        out = pool.map(fit_stratum, jobs, chunksize=1)
    tot = err = 0
    print(f"{'stratum':24s} {'n':>6s} {'fires':>6s} {'best-err':>8s} "
          f"{'rate':>7s} {'angle-deg':>9s}")
    for cell, n, n1, (e, a) in sorted(out):
        tot += n
        err += e
        adeg = f"{math.degrees(a):7.1f}" if a is not None else "   n/a"
        print(f"{str(cell):24s} {n:6d} {n1:6d} {e:8d} {e/n:7.3f} "
              f"{adeg}")
    print(f"\ntotal {tot} rows, linear-boundary errors {err} "
          f"(acc {1 - err/tot:.4f})")

if __name__ == "__main__":
    main()
