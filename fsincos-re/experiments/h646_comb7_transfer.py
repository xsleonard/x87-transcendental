#!/usr/bin/env python3
"""h646: blind transfer of the lattice law to comb7 + theta census.

1. Derive the u-table (lattice thresholds per (dist, s4, side, low3,
   third)) from comb4 — the corpus the law was found on.
2. Apply it UNCHANGED to comb7 theta=0 rows (fresh corpus, captured
   independently, h529 era): transfer error count.  Memorization would
   transfer at chance; a real law transfers exactly.
3. Census the theta=+-1/+-2 comb7 rows in the same margin frame: exact
   per-stratum thresholds — does theta shift the lattice?
"""
import os, pickle, sys
from collections import defaultdict
from multiprocessing import Pool

sys.path.insert(0, "/Users/steve/llm/x87-transcendental/fsincos-re/experiments")
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)

E2M = -66
SC = 60
PIV = 0.70710678118654752
UNIT = 2**66
CACHE7 = "h646_rows.pkl"


def load(ties, prefix, with_theta):
    rows, seen = [], set()
    for lineS in open(ties):
        f = lineS.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        rows.append(f)
    inputs = sorted(f[0] for f in rows)
    order = {mm: i for i, mm in enumerate(inputs)}
    st = {md: open(f"{prefix}_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    out = []
    for f in rows:
        R, ce, i = int(f[7], 16), int(f[8]), order[f[0]]
        theta = int(f[9]) if with_theta else 0
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
            out.append((f[0], 0, theta))
        elif hw == fired:
            out.append((f[0], 1, theta))
    return out


def internals(args):
    mhex, fire, theta = args
    m = int(mhex, 16)
    mag = (0, E2M, m)
    square = mul_round(mag, mag, 67, "chop")
    fourth = mul_round(square, square, 67, "chop")
    neg = build_chain(fourth, C6_5, C6_3, C6_1, 67, 64, "rn", False, False, False)
    pos = build_chain(fourth, C6_6, C6_4, C6_2, 67, 64, "rn", False, False, False)
    left = mul_round(square, neg, 67, "chop")
    right = mul_round(fourth, pos, 67, "chop")
    dist = abs(left[1] - right[1])
    sq = square[2]
    f4 = sq * sq
    s4 = f4.bit_length() - 67
    t4 = f4 & ((1 << s4) - 1)
    sqlow = sq - (1 << 66)
    low3 = sq & 7
    M = low3 * sqlow - t4
    rprod = fourth[2] * pos[2]
    sR = rprod.bit_length() - 67
    rdisc = rprod & ((1 << sR) - 1)
    XD = ((rdisc << SC) >> sR) / 2**SC
    mf = m / 2**64
    side = "lo" if mf < PIV else "hi"
    third = 0 if XD < 1 / 3 else (1 if XD < 2 / 3 else 2)
    return (theta, dist, s4, side, low3, third, M, fire)


def census(strata, title):
    H = 2**66
    print(f"\n=== {title} ===")
    print(f"{'stratum':>28} {'n':>7} {'fires':>6} {'sep?':>4} "
          f"{'threshold interval / 2^66':>28}")
    for key in sorted(strata):
        cleans, fires = strata[key]
        n = len(cleans) + len(fires)
        if n < 80:
            continue
        if not fires:
            print(f"{str(key):>28} {n:>7} {0:>6} {'--':>4}   "
                  f"all-clean (T <= {min(cleans)/H:.4f})")
            continue
        if not cleans:
            print(f"{str(key):>28} {n:>7} {len(fires):>6} {'--':>4}   "
                  f"all-fire (T > {max(fires)/H:.4f})")
            continue
        hi_f, lo_c = max(fires), min(cleans)
        if hi_f < lo_c:
            print(f"{str(key):>28} {n:>7} {len(fires):>6} {'YES':>4}   "
                  f"({hi_f/H:.4f}, {lo_c/H:.4f}]")
        else:
            ms = sorted([(mm, 0) for mm in cleans] + [(mm, 1) for mm in fires])
            lo_cnt, hi_cnt = 0, len(fires)
            best = (n + 1, None)
            for i in range(n + 1):
                e = lo_cnt + hi_cnt
                if e < best[0]:
                    best = (e, ms[min(i, n - 1)][0])
                if i < n:
                    _, ff = ms[i]
                    lo_cnt += (1 - ff); hi_cnt -= ff
            print(f"{str(key):>28} {n:>7} {len(fires):>6} {'no':>4}   "
                  f"best T={best[1]/H:.4f} errs={best[0]} ({best[0]/n:.4f})")


def main():
    # ---- comb4 u-table ----
    print("deriving u-table from comb4 ...", flush=True)
    lab4 = load("ties_comb4.txt", "comb4", False)
    feats = pickle.load(open("h628_feats.pkl", "rb"))
    assert len(feats) == len(lab4)
    TH = {}
    s4strata = defaultdict(lambda: [[], []])
    for (mhex, fire, _), (dist, low3, s4, XT, XTabs, XD, mf, cfire) in zip(
            lab4, feats):
        m = int(mhex, 16)
        m2 = m * m
        sq = m2 >> (m2.bit_length() - 67)
        f4 = sq * sq
        t4 = f4 & ((1 << s4) - 1)
        M = low3 * (sq - (1 << 66)) - t4
        side = "lo" if mf < PIV else "hi"
        third = 0 if XD < 1 / 3 else (1 if XD < 2 / 3 else 2)
        s4strata[(dist, s4, side, low3, third)][fire].append(M)
    for key, (cleans, fires) in s4strata.items():
        if not fires:
            TH[key] = ("never", min(cleans) if cleans else 0)
        elif not cleans:
            TH[key] = ("T", (max(fires) // UNIT + 1) * UNIT)
        else:
            hi_f, lo_c = max(fires), min(cleans)
            cands = [k * UNIT for k in range(hi_f // UNIT - 1,
                                             lo_c // UNIT + 2)
                     if hi_f < k * UNIT <= lo_c]
            if cands:
                TH[key] = ("T", cands[0])
            else:
                best = (1 << 62, None)
                for k in range(min(hi_f, lo_c) // UNIT - 1,
                               max(hi_f, lo_c) // UNIT + 2):
                    T = k * UNIT
                    e = sum(1 for mm in fires if mm >= T) + \
                        sum(1 for mm in cleans if mm < T)
                    if e < best[0]:
                        best = (e, T)
                TH[key] = ("T", best[1])
    print(f"u-table: {len(TH)} strata")

    # ---- comb7 rows ----
    if os.path.exists(CACHE7):
        rows7 = pickle.load(open(CACHE7, "rb"))
        print(f"loaded {len(rows7)} comb7 rows from cache")
    else:
        lab7 = load("ties_comb7.txt", "comb7", True)
        print(f"comb7 labeled: {len(lab7)}; computing internals ...",
              flush=True)
        with Pool(8) as pool:
            rows7 = pool.map(internals, lab7, chunksize=1000)
        pickle.dump(rows7, open(CACHE7, "wb"))
        print(f"computed {len(rows7)}")

    # ---- transfer test on theta=0 ----
    nt = terr = notab = 0
    errdetail = defaultdict(int)
    newcells = defaultdict(lambda: [[], []])
    for theta, dist, s4, side, low3, third, M, fire in rows7:
        if theta != 0:
            continue
        key = (dist, s4, side, low3, third)
        nt += 1
        e = TH.get(key)
        if e is None:
            notab += 1
            newcells[key][fire].append(M)
            continue
        if e[0] == "never":
            pred = 0
        else:
            pred = int(M < e[1])
        if pred != fire:
            terr += 1
            errdetail[key] += 1
    print(f"\n=== TRANSFER (theta=0): {terr} errors / {nt - notab} rows "
          f"covered; {notab} rows in cells absent from comb4 ===")
    for k in sorted(errdetail):
        print(f"    {k}: {errdetail[k]}")
    if newcells:
        census(newcells, "theta=0 cells NOT in comb4 (fresh census)")

    # ---- theta neq 0 census ----
    for th in (-2, -1, 1, 2):
        strata = defaultdict(lambda: [[], []])
        for theta, dist, s4, side, low3, third, M, fire in rows7:
            if theta != th:
                continue
            strata[(dist, s4, side, low3, third)][fire].append(M)
        census(strata, f"comb7 theta={th:+d}")


if __name__ == "__main__":
    main()
