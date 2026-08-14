#!/usr/bin/env python3
"""h647: master u-table census across ALL tie corpora.

Goal: close the u-table's closed form.  Assemble, for every cell
(dist, s4, side, low3, third), the exact lattice threshold (pinned) or
bound, merging comb2/3/4/5/6/7/8.  comb5 (fm ~ 0.50, dists 9/10) and
comb6 (fm ~ 0.94, dists 7/10) add (s4, side) families comb4 never had.

Margins M = low3*sqlow - t4 with sqlow = sq - 2^66, t4 = f4 mod 2^s4.
Threshold lattice expected at u * 2^66.  Writes h647_constraints.pkl:
{cell: ("pin", u) | ("le", u) | ("ge", u) | ("none", lo_halfopen...)}.
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

CORPORA = [
    ("comb3", "ties_comb3.txt", False),
    ("comb5", "ties_comb5.txt", False),
    ("comb6", "ties_comb6.txt", False),
    ("comb8", "ties_comb8.txt", True),
]


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
    M = (sq & 7) * (sq - (1 << 66)) - t4
    rprod = fourth[2] * pos[2]
    sR = rprod.bit_length() - 67
    rdisc = rprod & ((1 << sR) - 1)
    XD = ((rdisc << SC) >> sR) / 2**SC
    mf = m / 2**64
    side = "lo" if mf < PIV else "hi"
    third = 0 if XD < 1 / 3 else (1 if XD < 2 / 3 else 2)
    return (theta, dist, s4, side, sq & 7, third, M, fire)


def get_corpus(name, ties, with_theta):
    cache = f"h647_{name}.pkl"
    if os.path.exists(cache):
        return pickle.load(open(cache, "rb"))
    lab = load(ties, name, with_theta)
    print(f"{name}: {len(lab)} labeled; internals ...", flush=True)
    with Pool(8) as pool:
        rows = pool.map(internals, lab, chunksize=1000)
    pickle.dump(rows, open(cache, "wb"))
    return rows


def main():
    allrows = []
    for name, ties, wt in CORPORA:
        rows = get_corpus(name, ties, wt)
        n0 = sum(1 for r in rows if r[0] == 0)
        print(f"{name}: {len(rows)} rows ({n0} theta=0)", flush=True)
        allrows.extend((name,) + r for r in rows)
    # comb7 from its cache (same tuple layout)
    rows7 = pickle.load(open("h646_rows.pkl", "rb"))
    allrows.extend(("comb7",) + r for r in rows7)
    print(f"comb7: {len(rows7)} rows")
    # comb4 via h628 feats + label pass
    lab4 = load("ties_comb4.txt", "comb4", False)
    feats = pickle.load(open("h628_feats.pkl", "rb"))
    for (mhex, fire, _), (dist, low3, s4, XT, XTabs, XD, mf, cf) in zip(
            lab4, feats):
        m = int(mhex, 16)
        m2 = m * m
        sq = m2 >> (m2.bit_length() - 67)
        f4 = sq * sq
        t4 = f4 & ((1 << s4) - 1)
        M = low3 * (sq - (1 << 66)) - t4
        side = "lo" if mf < PIV else "hi"
        third = 0 if XD < 1 / 3 else (1 if XD < 2 / 3 else 2)
        allrows.append(("comb4", 0, dist, s4, side, low3, third, M, fire))
    print(f"total rows: {len(allrows)}")

    strata = defaultdict(lambda: [[], []])
    for src, theta, dist, s4, side, low3, third, M, fire in allrows:
        if theta != 0:
            continue
        strata[(dist, s4, side, low3, third)][fire].append(M)

    cons = {}
    print(f"\n{'cell':>26} {'n':>8} {'fires':>7}  constraint")
    for key in sorted(strata):
        cleans, fires = strata[key]
        n = len(cleans) + len(fires)
        if n < 60:
            continue
        if not fires:
            b = min(cleans)
            u_le = -(-b // UNIT) - 1 if b % UNIT == 0 else b // UNIT
            # T <= b  =>  u*2^66 <= b  => u <= floor(b/2^66)
            u_le = b // UNIT
            cons[key] = ("le", u_le)
            print(f"{str(key):>26} {n:>8} {0:>7}  u <= {u_le}  "
                  f"(minclean {b/UNIT:.4f})")
            continue
        if not cleans:
            t = max(fires)
            u_ge = t // UNIT + 1
            cons[key] = ("ge", u_ge)
            print(f"{str(key):>26} {n:>8} {len(fires):>7}  u >= {u_ge}  "
                  f"(maxfire {t/UNIT:.4f})")
            continue
        hi_f, lo_c = max(fires), min(cleans)
        cands = [k for k in range(hi_f // UNIT - 1, lo_c // UNIT + 2)
                 if hi_f < k * UNIT <= lo_c]
        if hi_f < lo_c and len(cands) == 1:
            cons[key] = ("pin", cands[0])
            print(f"{str(key):>26} {n:>8} {len(fires):>7}  u = {cands[0]}  "
                  f"({hi_f/UNIT:.4f}, {lo_c/UNIT:.4f}]")
        elif hi_f < lo_c and cands:
            cons[key] = ("pinrange", cands[0], cands[-1])
            print(f"{str(key):>26} {n:>8} {len(fires):>7}  u in {cands}")
        else:
            best = (n + 1, None)
            for k in range(min(hi_f, lo_c) // UNIT - 1,
                           max(hi_f, lo_c) // UNIT + 2):
                T = k * UNIT
                e = sum(1 for mm in fires if mm >= T) + \
                    sum(1 for mm in cleans if mm < T)
                if e < best[0]:
                    best = (e, k)
            frac = best[0] / n
            cons[key] = ("noisy", best[1], best[0], n)
            print(f"{str(key):>26} {n:>8} {len(fires):>7}  ~u={best[1]} "
                  f"errs={best[0]} ({frac:.4f})  NOT SEPARABLE")
    pickle.dump(cons, open("h647_constraints.pkl", "wb"))
    print(f"\n{len(cons)} cells -> h647_constraints.pkl")


if __name__ == "__main__":
    main()
