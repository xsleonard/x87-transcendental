#!/usr/bin/env python3
"""h662p: region-wide word-state corpus + h594B rerun with lattice.

h662o reframed the sc gate as the paired-producer offset z_sc; the
h594B word-state models (margin / SUM6 thresholds, 0.745 held-out)
were fit on the two h588 TARGETS strata only (21% of the h658
region).  Extend the h592b word extraction to ALL 177,550 region
rows and rerun the h594B held-out threshold models, with the h662
lattice features (crit, fire_cos, law bits) as key refinements.

Class labels (h594 discipline, side-dependent): up: [z >= 1] over
the full Z-set, dn: [z <= -1]; rows with mixed class dropped.
Margin: h578 HARD_T config where the stratum has one, raw Vlow
margin otherwise (the per-key threshold fit absorbs constants).
Cache: h662p_words.pkl.
"""
import os, pickle, sys
from collections import defaultdict
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)
from h578_margin_chunks import HARD_T
from h588_select import split_words, m3_state, fit_thr

E2M = -66
CACHE = "h662p_words.pkl"
ZCACHE = "h662o_rows.pkl"
NCACHE = "h662n_rows.pkl"


def work(args):
    (mhex, sign, th, fc, fs, w, phw, pm, scale, S, B, F, kf,
     APf, B_full, ce, Z) = args
    m = int(mhex, 16)
    mag0 = (0, E2M, m)
    sq = mul_round(mag0, mag0, 67, "chop")
    f4 = mul_round(sq, sq, 67, "chop")
    neg = build_chain(f4, C6_5, C6_3, C6_1, 67, 64, "rn",
                      False, False, False)
    pos = build_chain(f4, C6_6, C6_4, C6_2, 67, 64, "rn",
                      False, False, False)
    low3 = sq[2] & 7
    L_full = sq[2] * neg[2]
    lsh = L_full.bit_length() - 67
    ldisc = L_full & ((1 << lsh) - 1)
    rsh = B_full.bit_length() - 67
    rdisc = B_full & ((1 << rsh) - 1)
    left = mul_round(sq, neg, 67, "chop")
    right = mul_round(f4, pos, 67, "chop")
    dist = abs(left[1] - right[1])
    f4_full = sq[2] * sq[2]
    s4 = f4_full.bit_length() - 67
    t4 = f4_full & ((1 << s4) - 1)
    f4v, rfv = f4[2], pos[2]

    key = ((dist, low3, ce), sign == "up" and "up" or "dn")
    Vlow = (APf - B_full) - (((APf - B_full) >> kf) << kf)
    cfg = HARD_T.get(key, (0, 0, 0, 0, 0, 0, 0))
    sr, cr, sl, cl, st4, ct, cq = cfg
    T = cq * (1 << kf) >> 10
    if sr:
        T += sr * (rdisc << cr >> rsh)
    if sl:
        T += sl * (ldisc << cl >> lsh)
    if st4:
        T += st4 * (t4 << ct >> s4)
    if sign == "up":
        marg = Vlow - ((1 << kf) - T)
    else:
        marg = T - 1 - Vlow
    mb = marg * 4096 >> kf

    # class label from the full Z-set
    if sign == "up":
        cls = set(1 if z >= 1 else 0 for z in Z)
    else:
        cls = set(1 if z <= -1 else 0 for z in Z)
    if len(cls) != 1:
        return None
    scf = cls.pop()

    st3 = m3_state(f4v, rfv, rsh)
    Sw, Cw = split_words(f4v, rfv)
    fb = kf - 54
    wins = tuple(((Sw >> (fb - wd)) & ((1 << wd) - 1),
                  (Cw >> (fb - wd)) & ((1 << wd) - 1))
                 for wd in (8, 10, 12))

    mag = S - B
    crit = (pm + phw) % 8 == 7 and pm in (7, 8)
    bs = w + 8 + ((8 - phw) % 8)
    bit8 = (mag >> (w + 8)) & 1
    bitbs = (mag >> bs) & 1
    half = (m * 2654435761) & 1
    return (half, mb, scf, key, st3, wins, int(crit), fc,
            bit8, bitbs, phw, sign, th)


def held_out_thr(rows, keyf):
    tr = defaultdict(list)
    gl = defaultdict(int)
    for r in rows:
        if r[0] == 0:
            tr[keyf(r)].append((r[1], r[2]))
            gl[r[2]] += 1
    ths = {k: fit_thr(p) for k, p in tr.items()}
    gmaj = 1 if gl[1] >= gl[0] else 0
    ok = n = 0
    by_side = defaultdict(lambda: [0, 0])
    for r in rows:
        if r[0] != 1:
            continue
        t = ths.get(keyf(r))
        pred = gmaj if t is None else (1 if r[1] >= t else 0)
        good = pred == r[2]
        ok += good
        n += 1
        by_side[r[11]][good] += 1
    return ok / max(n, 1), n, by_side


def main():
    if os.path.exists(CACHE):
        rows = pickle.load(open(CACHE, "rb"))
        print(f"{len(rows)} word rows from cache", flush=True)
    else:
        nrows = pickle.load(open(NCACHE, "rb"))
        zmap = pickle.load(open(ZCACHE, "rb"))
        jobs = []
        for o in nrows:
            (mhex, sign, th, fc, fs, z1, pm, w, phw, scale, S, B,
             F, kf, APf, B_full, ce) = o
            jobs.append((mhex, sign, th, fc, fs, w, phw, pm, scale,
                         S, B, F, kf, APf, B_full, ce, zmap[mhex]))
        print(f"{len(jobs)} region rows; words ...", flush=True)
        with Pool(8) as pool:
            rows = pool.map(work, jobs, chunksize=500)
        dropped = sum(1 for r in rows if r is None)
        rows = [r for r in rows if r is not None]
        pickle.dump(rows, open(CACHE, "wb"))
        print(f"cached {len(rows)} (dropped {dropped} class-mixed)",
              flush=True)

    base = sum(r[2] for r in rows) / len(rows)
    nup = sum(1 for r in rows if r[11] == "up")
    bup = sum(r[2] for r in rows if r[11] == "up") / max(nup, 1)
    ndn = len(rows) - nup
    bdn = sum(r[2] for r in rows if r[11] == "dn") / max(ndn, 1)
    print(f"\nclass-observable rows: {len(rows)}  "
          f"base {base:.4f} (dn {bdn:.4f} n={ndn}, "
          f"up {bup:.4f} n={nup})")

    models = (
        ("margin-only (key)", lambda r: r[3]),
        ("key+SUM6", lambda r: (r[3], r[4])),
        ("key+crit", lambda r: (r[3], r[6])),
        ("key+SUM6+crit", lambda r: (r[3], r[4], r[6])),
        ("key+crit+fc", lambda r: (r[3], r[6], r[7])),
        ("key+SUM6+crit+fc", lambda r: (r[3], r[4], r[6], r[7])),
        ("key+crit+fc+law", lambda r: (r[3], r[6], r[7], r[8],
                                       r[9], r[10])),
        ("key+SUM6+crit+fc+law", lambda r: (r[3], r[4], r[6],
                                            r[7], r[8], r[9],
                                            r[10])),
    )
    print("\nh594B held-out threshold models (split-half):")
    for name, keyf in models:
        acc, n, by_side = held_out_thr(rows, keyf)
        parts = "  ".join(
            f"{s}:{g[1]/(g[0]+g[1]):.4f}" for s, g in
            sorted(by_side.items()))
        print(f"  {name:24s}: {acc:.4f} (n={n})  [{parts}]",
              flush=True)

    print("\nwindow census (h594C) with and without lattice:")
    print(f"{'model':>28s} {'groups':>8s} {'ceil':>7s} "
          f"{'heldout':>8s} {'unseen':>7s}")
    for wi, wd in enumerate((8, 10, 12)):
        for tag, gk in (
                (f"(key,win{wd})",
                 lambda r, wi=wi: (r[3],) + r[5][wi]),
                (f"(key,crit,fc,win{wd})",
                 lambda r, wi=wi: (r[3], r[6], r[7]) + r[5][wi])):
            gtr = defaultdict(lambda: [0, 0])
            te = []
            for r in rows:
                g = gk(r)
                if r[0] == 0:
                    gtr[g][r[2]] += 1
                else:
                    te.append((g, r[2]))
            ceil_ok = sum(max(c) for c in gtr.values())
            ceil_n = sum(sum(c) for c in gtr.values())
            gmaj = 1 if sum(c[1] for c in gtr.values()) >= \
                sum(c[0] for c in gtr.values()) else 0
            ho = unseen = 0
            for g, scf in te:
                c = gtr.get(g)
                if c is None:
                    pred = gmaj
                    unseen += 1
                else:
                    pred = 0 if c[0] >= c[1] else 1
                ho += pred == scf
            print(f"{tag:>28s} {len(gtr):8d} "
                  f"{ceil_ok / max(ceil_n, 1):7.4f} "
                  f"{ho / max(len(te), 1):8.4f} {unseen:7d}",
                  flush=True)


if __name__ == "__main__":
    main()
