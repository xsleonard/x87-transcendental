#!/usr/bin/env python3
"""h517: the overlooked comb-1 dist=8 population (200,106 ties at
le2=-73, window [0.656,0.781)) — never analyzed; every prior pass
filtered dist==9.  h510-style: per (low3, XD twelfth) free-slope fit,
segment merge.  Also dist census guard for any other stowaways."""
from collections import defaultdict
from multiprocessing import Pool
from h500_plane_m import build, load_comb
from h510_xd_steps import fit_free


def one_stratum(args):
    (dist, low3), pts = args
    cells = defaultdict(list)
    for p in pts:
        cells[min(11, int(p[1] * 12))].append(p)
    out = [f"\n=== d{dist} low3={low3}  n={len(pts)} "
           f"fires={sum(p[3] for p in pts)}"]
    for k in sorted(cells):
        sub = cells[k]
        n, n1 = len(sub), sum(p[3] for p in sub)
        lo, hi = k / 12, (k + 1) / 12
        if n < 400 or min(n1, n - n1) < 25:
            tag = ("always" if n1 == n and n else
                   "never" if n1 == 0 else f"sparse({n1}/{n})")
            out.append(f"  XD[{lo:.3f},{hi:.3f}) n={n:6d} {tag}")
            continue
        emin, s, c, blo, bhi = fit_free(sub)
        if s is None:
            out.append(f"  XD[{lo:.3f},{hi:.3f}) n={n:6d} "
                       f"fires={n1:5d} never-fire-opt errs={emin}")
            continue
        out.append(f"  XD[{lo:.3f},{hi:.3f}) n={n:6d} fires={n1:5d} "
                   f"errs={emin:5d} ({emin/n:.4f}) s={s:.6f} "
                   f"1/s={1/s:7.3f} c={c:.6f} "
                   f"band=[{blo:.5f},{bhi:.5f}]")
    return "\n".join(out)


def main():
    rows = load_comb()
    with Pool(8) as pool:
        data = pool.map(build, rows, chunksize=1000)
    census = defaultdict(int)
    strata = defaultdict(list)
    for cell, XT, XD, mf, fire in data:
        census[cell[0]] += 1
        if cell[0] != 9:
            strata[(cell[0], cell[1])].append((XT, XD, mf, fire))
    print("comb-1 dist census:", dict(sorted(census.items())))
    jobs = sorted(strata.items())
    with Pool(8) as pool:
        for block in pool.imap(one_stratum, jobs, chunksize=1):
            print(block, flush=True)


if __name__ == "__main__":
    main()
