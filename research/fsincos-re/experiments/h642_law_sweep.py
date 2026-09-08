#!/usr/bin/env python3
"""h642: sweep the h641 integer law across the WHOLE comb4 corpus.

The dist-9 window law (zero free parameters, 338,172/338,172):

    sqlow = sq - 2^66,  t4 = sqlow^2 mod 2^66
    b = [XD >= 1/3],  u = ceil((low3-4+b)/2) - 1
    fire  <=>  low3*sqlow < t4 + u*2^66

Here: evaluate margins M = low3*sqlow - t4 on EVERY labeled comb4 row
(all dists, both s4 sides) using the h628 feature cache for
(dist, s4, XD, fire) and recomputing sq directly from m (one multiply).
Per (dist, s4, low3, third): exact separation threshold interval, in
2^65 halves.  If thresholds land on multiples of 2^66 everywhere with a
dist-dependent u-map, the entire zone-table surface collapses.
"""
import pickle, sys
from collections import defaultdict

sys.path.insert(0, "/Users/steve/llm/x87-transcendental/fsincos-re/experiments")
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result

TIES = "ties_comb4.txt"
PREFIX = "comb4"
FEATCACHE = "h628_feats.pkl"
UNIT = 2**66


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


def main():
    labeled = load()
    feats = pickle.load(open(FEATCACHE, "rb"))
    assert len(feats) == len(labeled)
    print(f"{len(labeled)} labeled rows")

    strata = defaultdict(lambda: [[], []])
    for (mhex, fire), (dist, low3, s4, XT, XTabs, XD, mf, cfire) in zip(
            labeled, feats):
        assert int(fire) == cfire
        m = int(mhex, 16)
        m2 = m * m
        sq = m2 >> (m2.bit_length() - 67)
        assert (sq & 7) == low3, mhex
        sqlow = sq - UNIT
        f4 = sq * sq
        assert f4.bit_length() - 67 == s4
        t4 = f4 & ((1 << s4) - 1)         # actual discard at this s4
        third = 0 if XD < 1 / 3 else (1 if XD < 2 / 3 else 2)
        M = low3 * sqlow - t4
        strata[(dist, s4, low3, third)][int(fire)].append(M)

    # census of dists
    dn = defaultdict(int)
    for (dist, s4, low3, third), (c, f) in strata.items():
        dn[(dist, s4)] += len(c) + len(f)
    print("\nrows per (dist, s4):")
    for k in sorted(dn):
        print(f"  dist={k[0]} s4={k[1]}: {dn[k]}")

    print(f"\n{'dist':>4} {'s4':>3} {'low3':>4} {'third':>5} {'n':>7} "
          f"{'fires':>6} {'sep?':>4} {'threshold interval / 2^65':>30}")
    for key in sorted(strata):
        dist, s4, low3, third = key
        cleans, fires = strata[key]
        n = len(cleans) + len(fires)
        if n < 100:
            continue
        H = 2**65
        if not fires:
            print(f"{dist:>4} {s4:>3} {low3:>4} {third:>5} {n:>7} {0:>6} "
                  f"{'--':>4}   all-clean (T <= {min(cleans)/H:.4f})")
            continue
        if not cleans:
            print(f"{dist:>4} {s4:>3} {low3:>4} {third:>5} {n:>7} "
                  f"{len(fires):>6} {'--':>4}   all-fire (T > {max(fires)/H:.4f})")
            continue
        hi_f, lo_c = max(fires), min(cleans)
        if hi_f < lo_c:
            print(f"{dist:>4} {s4:>3} {low3:>4} {third:>5} {n:>7} "
                  f"{len(fires):>6} {'YES':>4}   ({hi_f/H:.4f}, {lo_c/H:.4f}]")
        else:
            ms = sorted([(m, 0) for m in cleans] + [(m, 1) for m in fires])
            tot1 = len(fires)
            lo_cnt, hi_cnt = 0, tot1
            best = (n + 1, None)
            for i in range(n + 1):
                e = lo_cnt + hi_cnt
                if e < best[0]:
                    best = (e, ms[min(i, n - 1)][0])
                if i < n:
                    _, ff = ms[i]
                    lo_cnt += (1 - ff); hi_cnt -= ff
            print(f"{dist:>4} {s4:>3} {low3:>4} {third:>5} {n:>7} "
                  f"{len(fires):>6} {'no':>4}   best T={best[1]/H:.4f} "
                  f"errs={best[0]} ({best[0]/n:.4f})")


if __name__ == "__main__":
    main()
