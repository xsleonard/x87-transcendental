#!/usr/bin/env python3
"""h587e: STRUCTURAL tree-shape scan, census-ceiling objective.

h587c/d proved: for the h584-winner tree, no function of (strat,
APf, S, C windows above retirement) exceeds ~0.906 in-sample —
the words themselves are wrong.  Scan the never-tried structure
axes:
  chunking: 3-pass 27/27/10 (Rtot=54) | 2-pass 27/37 (Rtot=27)
            | 2-pass 32/32 (Rtot=32)   [low chunk first]
  shape:    h584   16-slot, fb level-1 (control; needs <=14 rows)
            fblast 4:2 tower over PPs, fb pair merged at the END
            fbmid  fb pair merged after tower level 1
            seqi   3:2 ladder, (S,C) initialized with fb pair
            seqf   3:2 ladder over PPs, fb merged at the end
            seqri  seqi with row order reversed
            seqrf  seqf with row order reversed
            eo     even rows laddered, odd rows laddered, merge,
                   then fb
  assign:   PP order before reduction: adj | eo | rev
Objective per config: borrow-census ceiling + held-out at
w in {10, 14}, key = (strat, APf_w, S_w, C_w) at the boundary
col kf - Rtot.  The right tree shows BOTH high ceiling and high
transfer.  Usage: h587e_scan.py STRIDE
"""
import sys
from collections import defaultdict
from multiprocessing import Pool

WIDTH = 200
MASK = (1 << WIDTH) - 1
DIG4 = {0: 0, 1: 1, 2: 1, 3: 2, 4: -2, 5: -1, 6: -1, 7: 0}
TARGETS = [((9, 1, -72), "up"), ((9, 2, -72), "up")]
CHUNKINGS = {"27x3": (27, 27, 10), "27_37": (27, 37),
             "32x2": (32, 32)}
SHAPES = ("h584", "fblast", "fbmid", "seqi", "seqf", "seqri",
          "seqrf", "eo")
ASSIGNS = ("adj", "eo", "rev")


def csa(a, b, c):
    return (a ^ b ^ c) & MASK, \
        (((a & b) | (a & c) | (b & c)) << 1) & MASK


def c42(a, b, c, d):
    s1, c1 = csa(a, b, c)
    return csa(s1, c1, d)


def booth_rows_chunk(mcand, mplier, lo, w):
    y = (mplier >> lo) & ((1 << w) - 1)
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
    return rows  # pend dropped (h584 convention, proven inert)


def order_rows(rows, assign):
    if assign == "eo":
        return rows[0::2] + rows[1::2]
    if assign == "rev":
        return rows[::-1]
    return rows


def tower_pairs(pairs):
    """Combine (s,c) pairs pairwise with 4:2 until one remains."""
    while len(pairs) > 1:
        nxt = []
        for i in range(0, len(pairs) - 1, 2):
            nxt.append(c42(pairs[i][0], pairs[i][1],
                           pairs[i + 1][0], pairs[i + 1][1]))
        if len(pairs) % 2:
            nxt.append(pairs[-1])
        pairs = nxt
    return pairs[0]


def reduce_shape(rows, S, C, shape):
    if shape == "h584":
        it = (rows + [0] * 14)[:14] + [S, C]
        gs = [c42(it[0], it[1], it[2], it[3]),
              c42(it[4], it[5], it[6], it[7]),
              c42(it[8], it[9], it[10], it[11]),
              c42(it[12], it[13], it[14], it[15])]
        l2a = c42(gs[0][0], gs[0][1], gs[3][0], gs[3][1])
        l2b = c42(gs[1][0], gs[1][1], gs[2][0], gs[2][1])
        return c42(l2a[0], l2a[1], l2b[0], l2b[1])
    if shape in ("fblast", "fbmid"):
        rr = rows + [0] * ((-len(rows)) % 4)
        pairs = [c42(rr[i], rr[i + 1], rr[i + 2], rr[i + 3])
                 for i in range(0, len(rr), 4)]
        if shape == "fbmid":
            pairs.append((S, C))
            return tower_pairs(pairs)
        s, c = tower_pairs(pairs)
        return c42(s, c, S, C)
    if shape in ("seqi", "seqri"):
        rr = rows[::-1] if shape == "seqri" else rows
        s, c = S, C
        for r in rr:
            s, c = csa(s, c, r)
        return s, c
    if shape in ("seqf", "seqrf"):
        rr = rows[::-1] if shape == "seqrf" else rows
        s = c = 0
        for r in rr:
            s, c = csa(s, c, r)
        return c42(s, c, S, C)
    if shape == "eo":
        s1 = c1 = s2 = c2 = 0
        for r in rows[0::2]:
            s1, c1 = csa(s1, c1, r)
        for r in rows[1::2]:
            s2, c2 = csa(s2, c2, r)
        s, c = c42(s1, c1, s2, c2)
        return c42(s, c, S, C)
    raise ValueError(shape)


def split_words(f4v, rfv, chunking, shape, assign):
    S = C = 0
    pos = 0
    nb = rfv.bit_length()
    widths = CHUNKINGS[chunking]
    for ci, w in enumerate(widths):
        rows = booth_rows_chunk(f4v, rfv, pos, w)
        if shape == "h584" and len(rows) > 14:
            return None
        rows = order_rows(rows, assign)
        S, C = reduce_shape(rows, S, C, shape)
        pos += w
        if ci + 1 < len(widths):
            S >>= w
            C >>= w
    return S, C


ROWS = None


def init_rows(r):
    global ROWS
    ROWS = r


def eval_cfg(cfg):
    chunking, shape, assign = cfg
    Rtot = sum(CHUNKINGS[chunking][:-1])
    out = []
    for w in (10, 14):
        gtr = defaultdict(lambda: [0, 0])
        te = []
        for (key, half, kf, APf_low, f4v, rfv, b,
             bp) in ROWS:
            wds = split_words(f4v, rfv, chunking, shape, assign)
            if wds is None:
                return cfg, None
            S, C = wds
            fb = kf - Rtot
            if fb - w < 0:
                continue
            gk = (key,
                  (APf_low >> (kf - w)) & ((1 << w) - 1),
                  (S >> (fb - w)) & ((1 << w) - 1),
                  (C >> (fb - w)) & ((1 << w) - 1))
            if half == 0:
                gtr[gk][bp] += 1
            else:
                te.append((gk, bp, b))
        ceil_ok = sum(max(c) for c in gtr.values())
        ceil_n = sum(sum(c) for c in gtr.values())
        ho_ok = unseen = 0
        for gk, bp, b in te:
            c = gtr.get(gk)
            if c is None:
                pred = b
                unseen += 1
            else:
                pred = 0 if c[0] >= c[1] else 1
            ho_ok += 1 if pred == bp else 0
        out.append((w, len(gtr), ceil_ok / max(ceil_n, 1),
                    ho_ok / max(len(te), 1), unseen))
    return cfg, out


def main():
    stride = int(sys.argv[1]) if len(sys.argv) > 1 else 4
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
        mhex = f[0]
        fire = int(f[6])
        f4v, rfv = int(f[7], 16), int(f[8], 16)
        kf, Vlow = int(f[10]), int(f[11], 16)
        B_low = (f4v * rfv) & ((1 << kf) - 1)
        APf_low = (Vlow + B_low) & ((1 << kf) - 1)
        b = 1 if APf_low < B_low else 0
        if fire and b == 0:
            continue
        bp = 0 if fire else b
        m = int(mhex, 16)
        half = (m * 2654435761) & 1
        rows.append((key, half, kf, APf_low, f4v, rfv, b, bp))
    print(f"rows: {len(rows)}", flush=True)
    cfgs = [(ck, sh, a) for ck in CHUNKINGS for sh in SHAPES
            for a in ASSIGNS]
    # dedupe: assign irrelevant for h584 control beyond adj
    cfgs = [c for c in cfgs
            if not (c[1] == "h584" and c[2] != "adj")]
    print(f"configs: {len(cfgs)}", flush=True)
    with Pool(15, initializer=init_rows,
              initargs=(rows,)) as pool:
        res = pool.map(eval_cfg, cfgs, chunksize=1)
    scored = []
    for cfg, out in res:
        if out is None:
            print(f"skip {cfg} (rows>14 for h584 shape)")
            continue
        scored.append((out[0][3], cfg, out))
    scored.sort(reverse=True)
    print(f"\n{'config':30s} {'w':>3s} {'groups':>7s} "
          f"{'ceil':>7s} {'heldout':>8s} {'unseen':>7s}")
    for _, cfg, out in scored:
        for w, g, ce, ho, us in out:
            print(f"{str(cfg):30s} {w:3d} {g:7d} {ce:7.4f} "
                  f"{ho:8.4f} {us:7d}")


if __name__ == "__main__":
    main()
