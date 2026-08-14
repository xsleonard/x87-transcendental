#!/usr/bin/env python3
"""h662r: the redundant-pair carry-predict lattice for the sc class.

h662q: arrangement x anchor value-frame scan is NULL (12 frames, 0
extreme cells).  Standing mechanism class (h488 idea #1 + Shirriff
prior): the paired schedule consumes the f4*rf product's REDUNDANT
(S, C) form through a carry-PREDICT into the retained bits (low
bits never summed); z_sc = the predict error — a function of the
propagate structure of S^C below the retention column.

Use the h588-winner recoding (split_words, W=27 radix-4) as the
(S, C) model.  Verify alignment (S+C vs B_full<<1), then census the
sc class over:
  A. c_true = true carry into the retention column from below
  B. prun = run of ones in p = S^C downward from the boundary
     (the carry-chain span feeding the boundary), x block phase
     of the run END in absolute (scale-anchored) coordinates
  C. grun/zrun variants (generate g = S&C run, zero run)
Cache: h662r_red.pkl = (mhex, sign, th, fc, cls, rsh, Sw, Cw,
B_full, scale, re, w, phw, pm)
"""
import os, pickle, sys
from collections import defaultdict
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)
from h588_select import split_words

E2M = -66
CACHE = "h662r_red.pkl"
NCACHE = "h662n_rows.pkl"
ZCACHE = "h662o_rows.pkl"


def work(args):
    mhex, sign, th, fc, Z, pm, w, phw, scale = args
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
    pos = build_chain(f4, C6_6, C6_4, C6_2, 67, 64, "rn",
                      False, False, False)
    right = mul_round(f4, pos, 67, "chop")
    B_full = f4[2] * pos[2]
    rsh = B_full.bit_length() - 67
    Sw, Cw = split_words(f4[2], pos[2])
    al = 53
    return (mhex, sign, th, fc, cls, rsh, Sw, Cw, B_full, scale,
            right[1], w, phw, pm, al)


def main():
    if os.path.exists(CACHE):
        rows = pickle.load(open(CACHE, "rb"))
        print(f"{len(rows)} rows from cache", flush=True)
    else:
        nrows = pickle.load(open(NCACHE, "rb"))
        zmap = pickle.load(open(ZCACHE, "rb"))
        jobs = [(o[0], o[1], o[2], o[3], zmap[o[0]], o[6], o[7],
                 o[8], o[9]) for o in nrows]
        print(f"{len(jobs)} region rows; redundant pairs ...",
              flush=True)
        with Pool(8) as pool:
            rows = pool.map(work, jobs, chunksize=500)
        rows = [r for r in rows if r is not None]
        pickle.dump(rows, open(CACHE, "wb"))
        print(f"cached {len(rows)}", flush=True)

    # split_words is a 3-chunk iterative multiplier on y2 = 2*rfv,
    # discarding 27 bits after each of the first two chunks:
    # S + C ~= B_full >> 53 with lossy low ends.  Verify: resolved
    # tops must agree well above the boundary.
    agree = defaultdict(int)
    for r in rows[:2000]:
        rsh, Sw, Cw, B_full = r[5], r[6], r[7], r[8]
        top = (Sw + Cw) >> (rsh - 53 + 8)
        ref = B_full >> (rsh + 8)
        agree[top - ref] += 1
    print(f"alignment check (top-above-boundary delta, 2000 rows): "
          f"{dict(sorted(agree.items()))}")

    # boundary column in (S,C) coordinates: retention keeps
    # B = B_full >> rsh; with S+C ~= B_full >> 53 the boundary col
    # is jb = rsh - 53.
    print("\ncensus vs sc class:")
    tA = defaultdict(lambda: [0, 0])
    tB = defaultdict(lambda: [0, 0])
    tC = defaultdict(lambda: [0, 0])
    tD = defaultdict(lambda: [0, 0])
    for (mhex, sign, th, fc, cls, rsh, Sw, Cw, B_full, scale, re,
         w, phw, pm, al) in rows:
        jb = rsh - 53
        if jb <= 0:
            continue
        low = (1 << jb) - 1
        c_true = ((Sw & low) + (Cw & low)) >> jb
        p = Sw ^ Cw
        g = Sw & Cw
        prun = 0
        while jb - 1 - prun >= 0 and (p >> (jb - 1 - prun)) & 1:
            prun += 1
        grun = 0
        while jb - 1 - grun >= 0 and (g >> (jb - 1 - grun)) & 1:
            grun += 1
        # absolute phase of the boundary: B bit 0 sits at absolute
        # scale + (re - scale) - ... B = B_full >> rsh aligned so
        # that B << (re - scale) lines up with mag: absolute column
        # of B_full bit jb = scale + (re - scale) - ... use re - rsh
        # anchor variants directly:
        ph1 = (re - rsh + jb) % 8          # abs col of jb via re
        ph2 = (jb - prun) % 8              # run-end col, raw
        ph3 = (re - rsh + jb - prun) % 8   # run-end col, abs
        tA[(sign, c_true)][cls] += 1
        tB[(sign, min(prun, 16), ph3)][cls] += 1
        tC[(sign, min(grun, 16))][cls] += 1
        tD[(sign, min(prun, 16), ph2)][cls] += 1

    def show(tag, t, floor=100):
        print(f"\n[{tag}]")
        flagged = 0
        for k in sorted(t, key=str):
            c0, c1 = t[k]
            n = c0 + c1
            if n < floor:
                continue
            r = c1 / n
            mark = "  *EXTREME*" if r <= 0.03 or r >= 0.97 else ""
            if mark:
                flagged += 1
            print(f"  {k}: n={n:6d} rate={r:.4f}{mark}")
        print(f"  extreme cells: {flagged}")

    show("A: true carry into boundary", tA)
    show("B: (prun, abs run-end phase)", tB)
    show("C: generate run", tC)
    show("D: (prun, raw run-end phase)", tD)


if __name__ == "__main__":
    main()
