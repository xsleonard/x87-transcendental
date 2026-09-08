#!/usr/bin/env python3
"""h662t: matched-pair causal screen for the sc class (h479 spirit).

After the h662q-s null sweep, run the causal-variable screen the way
h479/h480 identified the tie gate's inputs — but as a matched
OBSERVATIONAL screen on the 148,871 sc-class-labeled comb7 region
rows: pin every known-relevant feature into a cell key, then test
each candidate hidden variable's within-cell association with the
sc class via Cochran-Mantel-Haenszel.

Pinned cell: (stratum(dist,low3,ce), side, th, crit, phw, pm cap12,
fire_cos, bit8, bitbs, coarse margin bucket).
Candidates (the h479/h480 causal set + analogs): f4_g, f4_b2, f4_b3
(fourth-power tail guards), r_g, r_b2 (right-product discard
guards), l_g, l_b2 (left-product discard guards), sq_g (square
guard-ish: sqlow parity bits).
A CMH hit here = candidate causal input of the sc gate; blind
validation then runs on comb9 sincos (captured in parallel).
Cache: h662t_vars.pkl.
"""
import math, os, pickle, sys
from collections import defaultdict
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)
from h578_margin_chunks import HARD_T

E2M = -66
CACHE = "h662t_vars.pkl"
NCACHE = "h662n_rows.pkl"
ZCACHE = "h662o_rows.pkl"


def work(args):
    mhex, sign, th, fc, Z, pm, w, phw, scale, S, B = args
    if sign == "up":
        cs = set(1 if z >= 1 else 0 for z in Z)
    else:
        cs = set(1 if z <= -1 else 0 for z in Z)
    if len(cs) != 1:
        return None
    cls = cs.pop()
    m = int(mhex, 16)
    mag0 = (0, E2M, m)
    sq = mul_round(mag0, mag0, 67, "chop")
    f4 = mul_round(sq, sq, 67, "chop")
    neg = build_chain(f4, C6_5, C6_3, C6_1, 67, 64, "rn",
                      False, False, False)
    pos = build_chain(f4, C6_6, C6_4, C6_2, 67, 64, "rn",
                      False, False, False)
    left = mul_round(sq, neg, 67, "chop")
    right = mul_round(f4, pos, 67, "chop")
    low3 = sq[2] & 7
    dist = abs(left[1] - right[1])
    ce = -73 if th == 0 else None  # placeholder, ce passed via n-cache
    f4_full = sq[2] * sq[2]
    s4 = f4_full.bit_length() - 67
    t4 = f4_full & ((1 << s4) - 1)
    L_full = sq[2] * neg[2]
    lsh = L_full.bit_length() - 67
    ldisc = L_full & ((1 << lsh) - 1)
    B_full = f4[2] * pos[2]
    rsh = B_full.bit_length() - 67
    rdisc = B_full & ((1 << rsh) - 1)

    f4_g = (t4 >> (s4 - 1)) & 1
    f4_b2 = (t4 >> (s4 - 2)) & 1 if s4 >= 2 else 0
    f4_b3 = (t4 >> (s4 - 3)) & 1 if s4 >= 3 else 0
    r_g = (rdisc >> (rsh - 1)) & 1
    r_b2 = (rdisc >> (rsh - 2)) & 1 if rsh >= 2 else 0
    l_g = (ldisc >> (lsh - 1)) & 1
    l_b2 = (ldisc >> (lsh - 2)) & 1 if lsh >= 2 else 0
    sq_g = (sq[2] >> 1) & 1

    # margin bucket (h592b recipe; raw where no HARD_T config)
    bshift = right[1] - scale
    F = rsh - bshift
    kf = w + F
    APf = S << F
    EU = (APf - B_full) >> kf
    Vlow = (APf - B_full) - (EU << kf)
    mag = S - B
    crit = (pm + phw) % 8 == 7 and pm in (7, 8)
    bs = w + 8 + ((8 - phw) % 8)
    bit8 = (mag >> (w + 8)) & 1
    bitbs = (mag >> bs) & 1
    return (mhex, sign, th, fc, cls, dist, low3, crit, phw,
            min(pm, 12), bit8, bitbs, (Vlow * 64 >> kf),
            (f4_g, f4_b2, f4_b3, r_g, r_b2, l_g, l_b2, sq_g))


VNAMES = ("f4_g", "f4_b2", "f4_b3", "r_g", "r_b2", "l_g", "l_b2",
          "sq_g")


def main():
    if os.path.exists(CACHE):
        rows = pickle.load(open(CACHE, "rb"))
        print(f"{len(rows)} rows from cache", flush=True)
    else:
        nrows = pickle.load(open(NCACHE, "rb"))
        zmap = pickle.load(open(ZCACHE, "rb"))
        jobs = [(o[0], o[1], o[2], o[3], zmap[o[0]], o[6], o[7],
                 o[8], o[9], o[10], o[11]) for o in nrows]
        print(f"{len(jobs)} region rows; variables ...", flush=True)
        with Pool(8) as pool:
            rows = pool.map(work, jobs, chunksize=500)
        rows = [r for r in rows if r is not None]
        pickle.dump(rows, open(CACHE, "wb"))
        print(f"cached {len(rows)}", flush=True)

    # CMH per candidate variable over pinned cells
    print("\nCMH screen (pinned cells, min arm 3):")
    results = []
    for vi, vn in enumerate(VNAMES):
        cells = defaultdict(lambda: [[0, 0], [0, 0]])
        for (mhex, sign, th, fc, cls, dist, low3, crit, phw, pm,
             bit8, bitbs, mb64, vs) in rows:
            key = (sign, th, dist, low3, crit, phw, pm, fc, bit8,
                   bitbs, mb64)
            cells[key][vs[vi]][cls] += 1
        num = den = 0.0
        used = pairs = 0
        for tab in cells.values():
            (a0, b0), (a1, b1) = tab
            n0 = a0 + b0
            n1 = a1 + b1
            n = n0 + n1
            if n0 < 3 or n1 < 3:
                continue
            used += 1
            pairs += min(n0, n1)
            m1 = b0 + b1
            ea1 = n1 * m1 / n
            va = n1 * n0 * m1 * (n - m1) / (n * n * (n - 1))
            num += b1 - ea1
            den += va
        z = num / math.sqrt(den) if den > 0 else 0.0
        results.append((abs(z), z, vn, used, pairs))
        print(f"  {vn:6s}: CMH z = {z:+6.2f}  (cells {used}, "
              f"matched mass {pairs})", flush=True)

    results.sort(reverse=True)
    best = results[0]
    print(f"\ntop variable: {best[2]} z={best[1]:+.2f}")
    # top cells for the winner
    vi = VNAMES.index(best[2])
    cells = defaultdict(lambda: [[0, 0], [0, 0]])
    for (mhex, sign, th, fc, cls, dist, low3, crit, phw, pm,
         bit8, bitbs, mb64, vs) in rows:
        key = (sign, th, dist, low3, crit, phw, pm, fc, bit8,
               bitbs, mb64)
        cells[key][vs[vi]][cls] += 1
    scored = []
    for key, tab in cells.items():
        (a0, b0), (a1, b1) = tab
        n0, n1 = a0 + b0, a1 + b1
        if n0 < 10 or n1 < 10:
            continue
        r0, r1 = b0 / n0, b1 / n1
        scored.append((abs(r1 - r0), key, n0, r0, n1, r1))
    scored.sort(reverse=True)
    print(f"top cells for {best[2]}:")
    for d, key, n0, r0, n1, r1 in scored[:12]:
        print(f"  {key}: v0 n={n0} rate={r0:.3f} | v1 n={n1} "
              f"rate={r1:.3f}  (delta {d:.3f})")


if __name__ == "__main__":
    main()
