#!/usr/bin/env python3
"""h643: the mirrored-frame law on the s4=67 side.

On s4=67 the square sits just BELOW the 2^67 binade: sq = 2^67 - sqhi
with sqhi small.  Identities: t4 = f4 mod 2^67 = sqhi^2 mod 2^67, and
sqhi mod 8 = (8 - low3) mod 8.  Candidate: the SAME law in the mirrored
variable:

    M' = (sqhi mod 8) * sqhi - (sqhi^2 mod 2^67)
    fire <=> M' < u * 2^67 (or 2^66 lattice)

Census of exact thresholds per (dist, low3, third) over all s4=67 rows,
margins reported in 2^66 units.
"""
import pickle, sys
from collections import defaultdict

sys.path.insert(0, "/Users/steve/llm/x87-transcendental/fsincos-re/experiments")
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result

TIES = "ties_comb4.txt"
PREFIX = "comb4"
FEATCACHE = "h628_feats.pkl"


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
    strata = defaultdict(lambda: [[], []])
    for (mhex, fire), (dist, low3, s4, XT, XTabs, XD, mf, cfire) in zip(
            labeled, feats):
        if s4 != 67:
            continue
        m = int(mhex, 16)
        m2 = m * m
        sq = m2 >> (m2.bit_length() - 67)
        f4 = sq * sq
        assert f4.bit_length() - 67 == 67
        t4 = f4 & ((1 << 67) - 1)
        sqhi = (1 << 67) - sq
        h3 = sqhi & 7
        assert h3 == (8 - low3) % 8
        assert t4 == (sqhi * sqhi) & ((1 << 67) - 1)
        M = h3 * sqhi - t4
        third = 0 if XD < 1 / 3 else (1 if XD < 2 / 3 else 2)
        strata[(dist, h3, third)][int(fire)].append(M)

    H = 2**66
    print("mirrored margins; thresholds in 2^66 units "
          "(h3 = sqhi mod 8 = 8-low3)\n")
    print(f"{'dist':>4} {'h3':>3} {'third':>5} {'n':>7} {'fires':>6} "
          f"{'sep?':>4} {'threshold interval / 2^66':>30}")
    for key in sorted(strata):
        dist, h3, third = key
        cleans, fires = strata[key]
        n = len(cleans) + len(fires)
        if n < 100:
            continue
        if not fires:
            print(f"{dist:>4} {h3:>3} {third:>5} {n:>7} {0:>6} {'--':>4}   "
                  f"all-clean (T <= {min(cleans)/H:.4f})")
            continue
        if not cleans:
            print(f"{dist:>4} {h3:>3} {third:>5} {n:>7} {len(fires):>6} "
                  f"{'--':>4}   all-fire (T > {max(fires)/H:.4f})")
            continue
        hi_f, lo_c = max(fires), min(cleans)
        if hi_f < lo_c:
            print(f"{dist:>4} {h3:>3} {third:>5} {n:>7} {len(fires):>6} "
                  f"{'YES':>4}   ({hi_f/H:.4f}, {lo_c/H:.4f}]")
        else:
            ms = sorted([(mm, 0) for mm in cleans] + [(mm, 1) for mm in fires])
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
            print(f"{dist:>4} {h3:>3} {third:>5} {n:>7} {len(fires):>6} "
                  f"{'no':>4}   best T={best[1]/H:.4f} errs={best[0]} "
                  f"({best[0]/n:.4f})")


if __name__ == "__main__":
    main()
