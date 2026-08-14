#!/usr/bin/env python3
"""h641: exact integer thresholds for the low-field law.

h640 (corrected): in the integer frame the boundary separates with ZERO
errors per (d0,b) stratum and slope EXACTLY 1/low3:

    fire  <=>  low3 * sqlow  <  t4 + u*2^66 + C
    sqlow = sq - 2^66,  t4 = f4 mod 2^66 = sqlow^2 mod 2^66 (identity!)

The fm-frame "band" (the h619c/h625 0.25 percent irreducible residue in
THIS window) is a frame artifact: it disappears in sqlow coordinates.

This script drops fitting entirely: per (low3, third) stratum compute the
margin M = low3*sqlow - t4 and find the EXACT feasible threshold interval
(perfect separation: max M over fires < min M over cleans, fire iff
M < T).  Report intervals in 2^65 halves to expose the u/b structure, and
verify the t4 identity.
"""
import pickle
from collections import defaultdict

ROWCACHE = "h638_rows.pkl"
UNIT = 2**66


def main():
    rows = pickle.load(open(ROWCACHE, "rb"))
    strata = defaultdict(lambda: [[], []])   # (low3, third) -> [cleanM, fireM]
    nver = 0
    for (mhex, fire, dist, sq, f2, p2, n2, s4, XT, sR, XD, mf) in rows:
        if s4 != 66:
            continue
        low3 = sq & 7
        sqlow = sq - UNIT
        t4 = (sq * sq) & (UNIT - 1)
        assert t4 == (sqlow * sqlow) & (UNIT - 1)
        nver += 1
        third = 0 if XD < 1 / 3 else (1 if XD < 2 / 3 else 2)
        M = low3 * sqlow - t4
        strata[(low3, third)][fire].append(M)
    print(f"t4 == sqlow^2 mod 2^66 verified on {nver} rows\n")

    print(f"{'low3':>4} {'third':>5} {'n':>7} {'fires':>6} "
          f"{'sep?':>5} {'T interval / 2^65':>28} {'width/2^65':>11}")
    for (low3, third) in sorted(strata):
        cleans, fires = strata[(low3, third)]
        n = len(cleans) + len(fires)
        if not fires:
            # all clean: T <= min clean M
            lim = min(cleans) / 2**65
            print(f"{low3:>4} {third:>5} {n:>7} {0:>6} {'--':>5} "
                  f"{'T <= %.4f' % lim:>28}")
            continue
        if not cleans:
            lim = max(fires) / 2**65
            print(f"{low3:>4} {third:>5} {n:>7} {len(fires):>6} {'--':>5} "
                  f"{'T > %.4f' % lim:>28}")
            continue
        hi_fire = max(fires)
        lo_clean = min(cleans)
        sep = hi_fire < lo_clean
        if sep:
            a, bnd = hi_fire / 2**65, lo_clean / 2**65
            print(f"{low3:>4} {third:>5} {n:>7} {len(fires):>6} {'YES':>5} "
                  f"{'(%.4f, %.4f]' % (a, bnd):>28} {bnd-a:>11.5f}")
        else:
            # count minimal errors at best T
            ms = sorted([(m, 0) for m in cleans] + [(m, 1) for m in fires])
            tot1 = len(fires)
            lo_cnt, hi_cnt = 0, tot1
            best = (n + 1, None)
            for i in range(n + 1):
                e = lo_cnt + hi_cnt
                if e < best[0]:
                    best = (e, ms[min(i, n - 1)][0])
                if i < n:
                    _, f = ms[i]
                    lo_cnt += (1 - f); hi_cnt -= f
            print(f"{low3:>4} {third:>5} {n:>7} {len(fires):>6} {'no':>5} "
                  f"best T={best[1]/2**65:>10.4f} errs={best[0]}")


if __name__ == "__main__":
    main()
