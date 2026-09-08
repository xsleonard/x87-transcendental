#!/usr/bin/env python3
"""h587c: BORROW-PREDICTOR CONSISTENCY CENSUS.

Mechanism form: terminal = APf - B with B in redundant (S, C)
form from the candidate tree; hardware borrow at column kf is
PREDICTED from a bounded window of the three addends above
column kf-w.  Fires = prediction errors:
  b  = true borrow = [APf_low < B_low]  (all mod 2^kf)
  up side: fire(req2=+1) <=> bp = b - 1  (needs b=1; a b=0 fire
           REFUTES the pure borrow-prediction class -> counted)
  clean:   bp = b
For each window width w (<= kf-54, the redundant field), group
rows by (stratum, APf window bits, S window bits, C window bits)
and ask whether required-bp is a function of the group:
  - in-sample ceiling (majority per group)
  - held-out accuracy (majority fit on train half, m-hash split;
    unseen group -> predict bp = b heuristic i.e. clean)
  - optional sticky bit: OR of all (S|C) bits below the window
Trees: the h584/h586 winner (nat, 14_23) and fb1/12_34.
Usage: h587c_census.py STRIDE
"""
import sys
from collections import defaultdict
from multiprocessing import Pool

WIDTH = 200
MASK = (1 << WIDTH) - 1
W = 27
DIG4 = {0: 0, 1: 1, 2: 1, 3: 2, 4: -2, 5: -1, 6: -1, 7: 0}
TARGETS = [((9, 1, -72), "up"), ((9, 2, -72), "up")]
GROUPINGS = {
    "nat": [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 10, 11],
            [12, 13, 14, 15]],
    "fb1": [[14, 15, 0, 1], [2, 3, 4, 5], [6, 7, 8, 9],
            [10, 11, 12, 13]],
}
PAIRINGS = {"12_34": ((0, 1), (2, 3)),
            "14_23": ((0, 3), (1, 2))}
TREES = [("nat", "14_23"), ("fb1", "12_34")]


def csa(a, b, c):
    return (a ^ b ^ c) & MASK, \
        (((a & b) | (a & c) | (b & c)) << 1) & MASK


def c42(a, b, c, d):
    s1, c1 = csa(a, b, c)
    return csa(s1, c1, d)


def booth4_chunks(f4v, rfv):
    nb = rfv.bit_length()
    out = []
    pos = 0
    while pos < nb:
        y = (rfv >> pos) & ((1 << W) - 1)
        y2 = y << 1
        rows = []
        pend = 0
        for i in range(0, max(y2.bit_length(), 1), 2):
            d = DIG4[(y2 >> i) & 7]
            row = 0
            if d > 0:
                row = (d * f4v << i) & MASK
            elif d < 0:
                row = ((((~((-d) * f4v)) & MASK) << i) & MASK)
            row |= pend
            pend = (1 << i) if d < 0 else 0
            rows.append(row)
        rows = rows[:14]
        while len(rows) < 14:
            rows.append(0)
        out.append(rows)
        pos += W
    return out


def split_words(chunks, grouping, pairing):
    S = C = 0
    last = len(chunks) - 1
    for ci, rows in enumerate(chunks):
        it = rows + [S, C]
        gs = [c42(it[g[0]], it[g[1]], it[g[2]], it[g[3]])
              for g in grouping]
        (i1, i2), (i3, i4) = pairing
        l2a = c42(gs[i1][0], gs[i1][1], gs[i2][0], gs[i2][1])
        l2b = c42(gs[i3][0], gs[i3][1], gs[i4][0], gs[i4][1])
        S, C = c42(l2a[0], l2a[1], l2b[0], l2b[1])
        if ci < last:
            S >>= W
            C >>= W
    return S, C


def row_words(args):
    f4v, rfv = args
    out = []
    for gname, pname in TREES:
        out.append(split_words(booth4_chunks(f4v, rfv),
                               GROUPINGS[gname],
                               PAIRINGS[pname]))
    return out


def main():
    stride = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    rows = []
    cnt = defaultdict(int)
    for line in open("h587c_band.tsv"):
        f = line.split()
        key = ((int(f[1]), int(f[2]), int(f[3])), f[4])
        if key not in dict.fromkeys(TARGETS):
            continue
        cnt[key] += 1
        if (cnt[key] - 1) % stride:
            continue
        rows.append((f[0], key, int(f[5]), int(f[6]),
                     int(f[7], 16), int(f[8], 16), int(f[9]),
                     int(f[10]), int(f[11], 16)))
    print(f"rows: {len(rows)}", flush=True)
    with Pool(15) as pool:
        words = pool.map(row_words,
                         [(r[4], r[5]) for r in rows],
                         chunksize=2000)
    # required bp + frames
    recs = []
    imposs = 0
    for r, wds in zip(rows, words):
        mhex, key, mb, fire, f4v, rfv, rsh, kf, Vlow = r
        B_low = (f4v * rfv) & ((1 << kf) - 1)
        APf_low = (Vlow + B_low) & ((1 << kf) - 1)
        b = 1 if APf_low < B_low else 0
        side = key[1]
        if side == "up":
            if fire:
                if b == 0:
                    imposs += 1
                    continue
                bp = 0
            else:
                bp = b
        else:
            bp = b + 1 if fire else b
        m = int(mhex, 16)
        half = (m * 2654435761) & 1
        recs.append((key, half, kf, APf_low, wds, b, bp))
    print(f"impossible rows (b=0 fire, up side): {imposs} "
          f"/ {len(rows)}", flush=True)
    for ti, (gname, pname) in enumerate(TREES):
        print(f"\n=== tree {gname}/{pname} ===")
        print(f"{'w':>3s} {'sticky':>6s} {'groups':>8s} "
              f"{'ceil':>7s} {'heldout':>8s} {'unseen':>7s}")
        for w in (4, 6, 8, 10, 12, 14, 16, 18):
            for sticky in (0, 1):
                gtr = defaultdict(lambda: [0, 0])
                rows_te = []
                for key, half, kf, APf_low, wds, b, bp in recs:
                    S, C = wds[ti]
                    fb = kf - 54
                    if fb - w < 0:
                        continue
                    ak = (APf_low >> (kf - w)) & ((1 << w) - 1)
                    sk = (S >> (fb - w)) & ((1 << w) - 1)
                    ck = (C >> (fb - w)) & ((1 << w) - 1)
                    st = 0
                    if sticky:
                        below = (1 << (fb - w)) - 1
                        st = 1 if ((S | C) & below) else 0
                    gk = (key, ak, sk, ck, st)
                    if half == 0:
                        gtr[gk][bp] += 1
                    rows_te.append((gk, bp, b, half))
                ceil_ok = ceil_n = 0
                ho_ok = ho_n = unseen = 0
                for gk, cnts in gtr.items():
                    ceil_ok += max(cnts)
                    ceil_n += sum(cnts)
                for gk, bp, b, half in rows_te:
                    if half == 0:
                        continue
                    cnts = gtr.get(gk)
                    if cnts is None:
                        pred = b
                        unseen += 1
                    else:
                        pred = 0 if cnts[0] >= cnts[1] else 1
                    ho_ok += 1 if pred == bp else 0
                    ho_n += 1
                print(f"{w:3d} {sticky:6d} {len(gtr):8d} "
                      f"{ceil_ok / max(ceil_n, 1):7.4f} "
                      f"{ho_ok / max(ho_n, 1):8.4f} "
                      f"{unseen:7d}", flush=True)


if __name__ == "__main__":
    main()
