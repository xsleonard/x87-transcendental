#!/usr/bin/env python3
"""h662q: the sc lattice hunt — arrangement x anchor frame scan.

The paired lane is deterministic on the same values (h526: 0 flips /
89k) yet independent of standalone — the schedule changes the
ARRANGEMENT, not the values (h488).  h490's surviving signal: a
two-column truncation shift between schedules.  h662 found the
standalone coin by the block-phase frame scan; rerun that hunt for
the sc class over candidate terminal arrangements:

  arrangements (same mag = A+P-B, different subtract operand pair
  => different propagate mask):
    r1: (A+P) - B        [standalone control]
    r2: A - (B-P)        [payload pre-merged into B]
  anchors (block alignment):
    (scale+w)%8 [standalone], le%8, re%8, (le-scale)%8,
    (re-scale)%8, scale%8

Census per frame: sc-class rate over (sign, pm', ph') cells; flag
extreme cells (<=0.03 / >=0.97, n>=100).  The h662b signature =
mostly-pure lattice + few coin cells.  Class labels = h662p (side-
dependent [z>=1]/[z<=-1] over full Z-sets, mixed dropped).
Cache: h662q_comp.pkl = (mhex, sign, th, fc, cls, A, P, Bres,
scale, le, re).
"""
import os, pickle, sys
from collections import defaultdict
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)

E2M = -66
CACHE = "h662q_comp.pkl"
NCACHE = "h662n_rows.pkl"
ZCACHE = "h662o_rows.pkl"


def work(args):
    mhex, sign, th, fc, Z = args
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
    product = sq[2] * neg[2]
    shift = max(product.bit_length() - 67, 0)
    discarded = product & ((1 << shift) - 1) if shift > 0 else 0
    ud = (discarded << 3) >> shift if shift > 0 else 0
    u5d = (discarded << 5) >> shift if shift > 0 else 0
    B_full = f4[2] * pos[2]
    rsh = max(B_full.bit_length() - 67, 0)
    rdisc = B_full & ((1 << rsh) - 1) if rsh > 0 else 0
    rud = (rdisc << 1) >> rsh if rsh > 0 else 0
    active = 1 if (low3 and (ud or (dist == 7 and u5d))) else 0
    payload = low3 + 8 - dist if active else 0
    if active and dist == 10 and low3 == 6 and rud:
        lane_shift = (left[1] - 8) - right[1]
        lane = (right[2] >> lane_shift) if lane_shift >= 0 \
            else (right[2] << -lane_shift)
        lp8 = lane & 0xFF
        d8 = (lp8 - payload) & 0xFF
        if d8 >= 128:
            d8 -= 256
        if d8 == -2:
            payload = lp8
    if active and dist == 8 and low3 == 7 and ud >= 3:
        lane_shift = (left[1] - 8) - right[1]
        lane = (right[2] >> lane_shift) if lane_shift >= 0 \
            else (right[2] << -lane_shift)
        lp8 = lane & 0xFF
        d8 = (lp8 - payload) & 0xFF
        if d8 >= 128:
            d8 -= 256
        if d8 == 0:
            payload -= 1
    scale = min(left[1], right[1])
    if payload and left[1] - 8 < scale:
        scale = left[1] - 8
    A = left[2] << (left[1] - scale)
    Bres = right[2] << (right[1] - scale)
    P = (payload << (left[1] - 8 - scale)) if payload else 0
    if A + P - Bres <= 0:
        return None
    return (mhex, sign, th, fc, cls, A, P, Bres, scale,
            left[1], right[1])


def pmrun(X, Y, w):
    pmask = ~(X ^ Y)
    r = 0
    j = w
    while (pmask >> j) & 1:
        r += 1
        j += 1
    return min(r, 24)


def main():
    if os.path.exists(CACHE):
        rows = pickle.load(open(CACHE, "rb"))
        print(f"{len(rows)} rows from cache", flush=True)
    else:
        nrows = pickle.load(open(NCACHE, "rb"))
        zmap = pickle.load(open(ZCACHE, "rb"))
        jobs = [(o[0], o[1], o[2], o[3], zmap[o[0]]) for o in nrows]
        print(f"{len(jobs)} region rows; components ...", flush=True)
        with Pool(8) as pool:
            rows = pool.map(work, jobs, chunksize=500)
        rows = [r for r in rows if r is not None]
        pickle.dump(rows, open(CACHE, "wb"))
        print(f"cached {len(rows)} class-observable", flush=True)

    ARR = {
        "r1:(A+P)-B": lambda A, P, B: (A + P, B),
        "r2:A-(B-P)": lambda A, P, B: (A, B - P),
    }
    ANC = {
        "scale+w": lambda scale, le, re, w: (scale + w) % 8,
        "le": lambda scale, le, re, w: le % 8,
        "re": lambda scale, le, re, w: re % 8,
        "le-scale": lambda scale, le, re, w: (le - scale) % 8,
        "re-scale": lambda scale, le, re, w: (re - scale) % 8,
        "scale": lambda scale, le, re, w: scale % 8,
    }

    summary = []
    for aname, afn in ARR.items():
        # precompute per-row (pm, w) for this arrangement
        pre = []
        for (mhex, sign, th, fc, cls, A, P, B, scale, le, re) in rows:
            X, Y = afn(A, P, B)
            mag = X - Y
            w = mag.bit_length() - 67
            if w <= 0:
                pre.append(None)
                continue
            pre.append((pmrun(X, Y, w), w))
        for hname, hfn in ANC.items():
            t = defaultdict(lambda: [0, 0])
            for row, pw in zip(rows, pre):
                if pw is None:
                    continue
                (mhex, sign, th, fc, cls, A, P, B, scale, le,
                 re) = row
                pm, w = pw
                ph = hfn(scale, le, re, w)
                t[(sign, pm, ph)][cls] += 1
            ext_cells = ext_rows = tot = 0
            det = []
            for k, (c0, c1) in t.items():
                n = c0 + c1
                if n < 100:
                    continue
                tot += n
                r = c1 / n
                if r <= 0.03 or r >= 0.97:
                    ext_cells += 1
                    ext_rows += n
                    det.append((k, n, r))
            summary.append((ext_rows / max(tot, 1), ext_cells,
                            aname, hname, det))
    summary.sort(reverse=True)
    print("\nframe scan (extreme-cell row coverage):")
    for cov, cells, aname, hname, det in summary:
        print(f"  {aname:12s} x {hname:9s}: extreme cells {cells:3d} "
              f"covering {cov:.3f} of rows")
    best = summary[0]
    print(f"\nbest frame {best[2]} x {best[3]} extreme cells:")
    for k, n, r in sorted(best[4], key=str)[:40]:
        print(f"  {k}: n={n} rate={r:.4f}")

    # detail table for the best frame: full lattice
    aname, hname = best[2], best[3]
    afn, hfn = ARR[aname], ANC[hname]
    t = defaultdict(lambda: [0, 0])
    for (mhex, sign, th, fc, cls, A, P, B, scale, le, re) in rows:
        X, Y = afn(A, P, B)
        mag = X - Y
        w = mag.bit_length() - 67
        if w <= 0:
            continue
        pm = pmrun(X, Y, w)
        ph = hfn(scale, le, re, w)
        t[(sign, pm, ph)][cls] += 1
    print(f"\nfull lattice for {aname} x {hname} [n>=100]:")
    for k in sorted(t, key=str):
        c0, c1 = t[k]
        n = c0 + c1
        if n < 100:
            continue
        print(f"  {k}: n={n:6d} rate={c1/n:.4f}")


if __name__ == "__main__":
    main()
