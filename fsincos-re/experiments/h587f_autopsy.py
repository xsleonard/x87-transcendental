#!/usr/bin/env python3
"""h587f: contradiction autopsy for the borrow census.

Q1 (proof statement): group rows by (strat, FULL APf_low, FULL
    S, FULL C) [winner tree].  Ceiling < 1.0 proves the gate
    reads state outside (terminal value + B redundant words).
    Also with left-tree words added (full).
Q2 (localization): within w=12 contradictory groups, pair rows
    with opposite bp; histogram the columns where their full S
    (and C) words differ — relative to the boundary (col 72) —
    against the same histogram for same-bp control pairs.
    Excess diff-rate at specific columns localizes the wrong-bit
    structure of our tree.
Usage: h587f_autopsy.py STRIDE
"""
import sys
from collections import defaultdict
from multiprocessing import Pool

WIDTH = 200
MASK = (1 << WIDTH) - 1
W = 27
DIG4 = {0: 0, 1: 1, 2: 1, 3: 2, 4: -2, 5: -1, 6: -1, 7: 0}
TARGETS = [((9, 1, -72), "up"), ((9, 2, -72), "up")]
GROUPING = [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 10, 11],
            [12, 13, 14, 15]]
PAIRING = ((0, 3), (1, 2))


def csa(a, b, c):
    return (a ^ b ^ c) & MASK, \
        (((a & b) | (a & c) | (b & c)) << 1) & MASK


def c42(a, b, c, d):
    s1, c1 = csa(a, b, c)
    return csa(s1, c1, d)


def booth4_chunks(mcand, mplier):
    nb = mplier.bit_length()
    out = []
    pos = 0
    while pos < nb:
        y = (mplier >> pos) & ((1 << W) - 1)
        y2 = y << 1
        rows = []
        pend = 0
        for i in range(0, max(y2.bit_length(), 1), 2):
            d = DIG4[(y2 >> i) & 7]
            row = 0
            if d > 0:
                row = (d * mcand << i) & MASK
            elif d < 0:
                row = ((((~((-d) * mcand)) & MASK) << i) & MASK)
            row |= pend
            pend = (1 << i) if d < 0 else 0
            rows.append(row)
        rows = rows[:14]
        while len(rows) < 14:
            rows.append(0)
        out.append(rows)
        pos += W
    return out


def split_words(mcand, mplier):
    S = C = 0
    chunks = booth4_chunks(mcand, mplier)
    last = len(chunks) - 1
    for ci, rows in enumerate(chunks):
        it = rows + [S, C]
        gs = [c42(it[g[0]], it[g[1]], it[g[2]], it[g[3]])
              for g in GROUPING]
        (i1, i2), (i3, i4) = PAIRING
        l2a = c42(gs[i1][0], gs[i1][1], gs[i2][0], gs[i2][1])
        l2b = c42(gs[i3][0], gs[i3][1], gs[i4][0], gs[i4][1])
        S, C = c42(l2a[0], l2a[1], l2b[0], l2b[1])
        if ci < last:
            S >>= W
            C >>= W
    return S, C


def row_words(args):
    f4v, rfv, sqv, negv = args
    return (split_words(f4v, rfv), split_words(sqv, negv))


def main():
    stride = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    rows = []
    cnt = defaultdict(int)
    for line in open("h587d_band.tsv"):
        f = line.split()
        key = ((int(f[1]), int(f[2]), int(f[3])), f[4])
        if key not in dict.fromkeys(TARGETS):
            continue
        cnt[key] += 1
        if (cnt[key] - 1) % stride:
            continue
        fire = int(f[6])
        f4v, rfv = int(f[7], 16), int(f[8], 16)
        kf, Vlow = int(f[10]), int(f[11], 16)
        sqv, negv = int(f[12], 16), int(f[13], 16)
        B_low = (f4v * rfv) & ((1 << kf) - 1)
        APf_low = (Vlow + B_low) & ((1 << kf) - 1)
        b = 1 if APf_low < B_low else 0
        if fire and b == 0:
            continue
        bp = 0 if fire else b
        rows.append((key, kf, APf_low, f4v, rfv, sqv, negv, b,
                     bp))
    print(f"rows: {len(rows)}", flush=True)
    with Pool(15) as pool:
        words = pool.map(row_words,
                         [(r[3], r[4], r[5], r[6])
                          for r in rows],
                         chunksize=1000)
    # Q1: full-key ceilings
    for name, keyf in (
            ("strat+APf_low(full)",
             lambda r, w: (r[0], r[2])),
            ("strat+APf+S+C(full,B)",
             lambda r, w: (r[0], r[2], w[0][0], w[0][1])),
            ("strat+APf+S+C+SL+CL(full)",
             lambda r, w: (r[0], r[2], w[0][0], w[0][1],
                           w[1][0], w[1][1]))):
        g = defaultdict(lambda: [0, 0])
        for r, w in zip(rows, words):
            g[keyf(r, w)][r[8]] += 1
        ok = sum(max(c) for c in g.values())
        n = sum(sum(c) for c in g.values())
        mixed = sum(1 for c in g.values() if c[0] and c[1])
        mixrows = sum(sum(c) for c in g.values()
                      if c[0] and c[1])
        print(f"Q1 {name}: groups={len(g)} ceil={ok / n:.5f} "
              f"mixed_groups={mixed} rows_in_mixed={mixrows}",
              flush=True)
    # Q2: column-diff histograms in w=12 contradictory groups
    w = 12
    groups = defaultdict(list)
    for i, (r, wd) in enumerate(zip(rows, words)):
        key, kf, APf_low, f4v, rfv, sqv, negv, b, bp = r
        S, C = wd[0]
        fb = kf - 54
        gk = (key,
              (APf_low >> (kf - w)) & ((1 << w) - 1),
              (S >> (fb - w)) & ((1 << w) - 1),
              (C >> (fb - w)) & ((1 << w) - 1))
        groups[gk].append(i)
    ncols = 60
    diff_ct = [0] * ncols
    ctrl_ct = [0] * ncols
    ndiff = nctrl = 0
    import random
    rng = random.Random(58705)
    for gk, idxs in groups.items():
        zeros = [i for i in idxs if rows[i][8] == 0]
        ones = [i for i in idxs if rows[i][8] == 1]
        if zeros and ones:
            pairs = [(rng.choice(zeros), rng.choice(ones))
                     for _ in range(min(len(zeros), len(ones),
                                        3))]
            tgt = (diff_ct, "d")
        elif len(idxs) >= 2:
            pairs = [tuple(rng.sample(idxs, 2))]
            tgt = (ctrl_ct, "c")
        else:
            continue
        for i, j in pairs:
            Si, Ci = words[i][0]
            Sj, Cj = words[j][0]
            kf = rows[i][1]
            fb = kf - 54
            dS = (Si ^ Sj) | (Ci ^ Cj)
            for col in range(ncols):
                # col index relative to boundary: fb-1-col
                # downward... use absolute frame col
                pass
            for fc in range(ncols):
                if (dS >> fc) & 1:
                    tgt[0][fc] += 1
            if tgt[1] == "d":
                ndiff += 1
            else:
                nctrl += 1
    print(f"\nQ2: contradiction pairs={ndiff}, control "
          f"pairs={nctrl}  (frame col 18 = boundary kf; "
          f"cols 0-17 = redundant field above retirement; "
          f"cols >=18 retained)")
    print(f"{'framecol':>8s} {'diffrate':>9s} {'ctrlrate':>9s}")
    for fc in range(ncols):
        dr = diff_ct[fc] / max(ndiff, 1)
        cr = ctrl_ct[fc] / max(nctrl, 1)
        if dr > 0.001 or cr > 0.001:
            print(f"{fc:8d} {dr:9.4f} {cr:9.4f}")


if __name__ == "__main__":
    main()
