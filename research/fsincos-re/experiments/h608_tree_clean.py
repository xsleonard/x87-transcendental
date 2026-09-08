#!/usr/bin/env python3
"""h608: THE BIT-LEVEL TREE SEARCH ON CLEAN LABELS.

Objective: census transfer — group clean (9,1)/(9,2)@-72 up
band rows by (stratum, S_w, C_w) at the boundary (w in {10,
14}), majority fit on train half (bit-16 m-hash), score
held-out.  Winner-tree bar: 0.9468 @ w=10 (h591b; that number
used the bit-0 m-hash — the in-run anchor config is the
comparable bar here).

Unified space (everything the pre-correction searches tried
separately): role (fr, rf) x chunking (27x3, 27_37, 32x2) x
hot (next, drop) x ret (shift, addS) x reduction shape
(16-slot grouping{nat,fb1,spl} x pairing{3} | fblast | fbmid |
seqi | seqf | seqri | seqrf | eo) x PP order (adj, eo, rev).
slot16 shapes truncate to 14 PP rows (h584 convention): under
27_37/32x2 the wide chunk overflows 14 rows and the config is
value-broken; census transfer scores such trees on their own
(de)merits, as h584 did for w=32.

Rows: h592_band.tsv (clean alias-robust labels, blind rows
dropped).  bp = required borrow-prediction (up side: fire ->
bp=0 needs b=1; clean -> bp=b); unseen census group -> pred=b.
Anchor config = h584/h588 winner tree, bit-exact here:
(fr, 27x3, next, shift, (slot16, nat, 14_23), adj).
Usage: h608_tree_clean.py STRIDE [NPROC]
"""
import sys
from collections import defaultdict
from multiprocessing import Pool

WIDTH = 200
MASK = (1 << WIDTH) - 1
DIG4 = {0: 0, 1: 1, 2: 1, 3: 2, 4: -2, 5: -1, 6: -1, 7: 0}
CHUNKINGS = {"27x3": (27, 27, 27), "27_37": (27, 37),
             "32x2": (32, 32)}
GROUPINGS = {
    "nat": [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 10, 11],
            [12, 13, 14, 15]],
    "fb1": [[14, 15, 0, 1], [2, 3, 4, 5], [6, 7, 8, 9],
            [10, 11, 12, 13]],
    "spl": [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 10, 14],
            [11, 12, 13, 15]],
}
PAIRINGS = {"12_34": ((0, 1), (2, 3)),
            "13_24": ((0, 2), (1, 3)),
            "14_23": ((0, 3), (1, 2))}
SHAPES = ([("slot16", g, p) for g in GROUPINGS for p in PAIRINGS]
          + [("fblast",), ("fbmid",), ("seqi",), ("seqf",),
             ("seqri",), ("seqrf",), ("eo",)])
ORDERS = ("adj", "eo", "rev")
WS = (10, 14)
ANCHOR = ("fr", "27x3", "next", "shift",
          ("slot16", "nat", "14_23"), "adj")


def csa(a, b, c):
    return (a ^ b ^ c) & MASK, \
        (((a & b) | (a & c) | (b & c)) << 1) & MASK


def c42(a, b, c, d):
    s1, c1 = csa(a, b, c)
    return csa(s1, c1, d)


def booth_rows(mcand, mplier, lo, w, hot):
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
        if hot == "next":
            row |= pend
            pend = (1 << i) if d < 0 else 0
        rows.append(row)
    return rows


def order_rows(rows, order):
    if order == "eo":
        return rows[0::2] + rows[1::2]
    if order == "rev":
        return rows[::-1]
    return rows


def tower(pairs):
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
    kind = shape[0]
    if kind == "slot16":
        _, gname, pname = shape
        it = (rows + [0] * 14)[:14] + [S, C]
        gs = [c42(it[g[0]], it[g[1]], it[g[2]], it[g[3]])
              for g in GROUPINGS[gname]]
        (i1, i2), (i3, i4) = PAIRINGS[pname]
        l2a = c42(gs[i1][0], gs[i1][1], gs[i2][0], gs[i2][1])
        l2b = c42(gs[i3][0], gs[i3][1], gs[i4][0], gs[i4][1])
        return c42(l2a[0], l2a[1], l2b[0], l2b[1])
    if kind in ("fblast", "fbmid"):
        rr = rows + [0] * ((-len(rows)) % 4)
        pairs = [c42(rr[i], rr[i + 1], rr[i + 2], rr[i + 3])
                 for i in range(0, len(rr), 4)]
        if kind == "fbmid":
            pairs.append((S, C))
            return tower(pairs)
        s, c = tower(pairs)
        return c42(s, c, S, C)
    if kind in ("seqi", "seqri"):
        rr = rows[::-1] if kind == "seqri" else rows
        s, c = S, C
        for r in rr:
            s, c = csa(s, c, r)
        return s, c
    if kind in ("seqf", "seqrf"):
        rr = rows[::-1] if kind == "seqrf" else rows
        s = c = 0
        for r in rr:
            s, c = csa(s, c, r)
        return c42(s, c, S, C)
    if kind == "eo":
        s1 = c1 = s2 = c2 = 0
        for r in rows[0::2]:
            s1, c1 = csa(s1, c1, r)
        for r in rows[1::2]:
            s2, c2 = csa(s2, c2, r)
        s, c = c42(s1, c1, s2, c2)
        return c42(s, c, S, C)
    raise ValueError(shape)


def booth_chunks(f4v, rfv, role, ck, hot):
    mcand, mplier = (f4v, rfv) if role == "fr" else (rfv, f4v)
    widths = CHUNKINGS[ck]
    nb = mplier.bit_length()
    chunks = []
    pos = 0
    wi = 0
    while pos < nb:
        w = widths[wi] if wi < len(widths) else widths[-1]
        chunks.append((booth_rows(mcand, mplier, pos, w, hot), w))
        pos += w
        wi += 1
    return chunks


def reduce_cfg(chunks, ret, shape, order):
    S = C = 0
    col0 = 0
    last = len(chunks) - 1
    for ci, (rows, w) in enumerate(chunks):
        S, C = reduce_shape(order_rows(rows, order), S, C, shape)
        if ci < last:
            if ret == "addS":
                wm = (1 << w) - 1
                cout = ((S & wm) + (C & wm)) >> w
                S = ((S >> w) + cout) & MASK
            else:
                S >>= w
            C >>= w
            col0 += w
    return S, C, col0


ROWS = None


def init_rows(r):
    global ROWS
    ROWS = r


def eval_job(args):
    role, ck, hot, ret, shape = args
    # census accumulators per (order, w):
    #   train: gk -> [n_bp0, n_bp1]
    #   test:  gk -> [bp0_b0, bp0_b1, bp1_b0, bp1_b1]
    acc = {(o, w): (defaultdict(lambda: [0, 0]),
                    defaultdict(lambda: [0, 0, 0, 0]))
           for o in ORDERS for w in WS}
    for low3, half, f4v, rfv, kf, bp, b in ROWS:
        chunks = booth_chunks(f4v, rfv, role, ck, hot)
        for o in ORDERS:
            S, C, col0 = reduce_cfg(chunks, ret, shape, o)
            fb = kf - col0
            for w in WS:
                if fb - w < 0:
                    continue
                sk = (S >> (fb - w)) & ((1 << w) - 1)
                cw = (C >> (fb - w)) & ((1 << w) - 1)
                gk = low3 | sk << 4 | cw << (4 + w)
                tr, te = acc[(o, w)]
                if half == 0:
                    tr[gk][bp] += 1
                else:
                    te[gk][bp * 2 + b] += 1
    out = []
    for o in ORDERS:
        res = {}
        for w in WS:
            tr, te = acc[(o, w)]
            ceil_ok = sum(max(c) for c in tr.values())
            ceil_n = sum(sum(c) for c in tr.values())
            ho = {1: [0, 0], 2: [0, 0]}
            unseen = 0
            for gk, (b00, b01, b10, b11) in te.items():
                low3 = gk & 15
                n = b00 + b01 + b10 + b11
                c = tr.get(gk)
                if c is None:
                    unseen += n
                    ok = b00 + b11  # pred = b
                elif c[0] >= c[1]:
                    ok = b00 + b01  # pred bp = 0
                else:
                    ok = b10 + b11  # pred bp = 1
                ho[low3][0] += ok
                ho[low3][1] += n
            hj = (ho[1][0] + ho[2][0]) / max(ho[1][1] + ho[2][1], 1)
            res[w] = (len(tr), ceil_ok / max(ceil_n, 1), hj,
                      ho[1][0] / max(ho[1][1], 1),
                      ho[2][0] / max(ho[2][1], 1), unseen)
        out.append(((role, ck, hot, ret, shape, o), res))
    return out


def main():
    stride = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    nproc = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    rows = []
    imposs = 0
    nline = 0
    for line in open("h592_band.tsv"):
        nline += 1
        if (nline - 1) % stride:
            continue
        f = line.split()
        low3, fire = int(f[2]), int(f[6])
        f4v, rfv = int(f[7], 16), int(f[8], 16)
        kf, Vlow = int(f[10]), int(f[11], 16)
        B_low = (f4v * rfv) & ((1 << kf) - 1)
        APf_low = (Vlow + B_low) & ((1 << kf) - 1)
        b = 1 if APf_low < B_low else 0
        if fire and b == 0:
            imposs += 1
            continue
        bp = 0 if fire else b
        m = int(f[0], 16)
        half = (m * 2654435761 >> 16) & 1
        rows.append((low3, half, f4v, rfv, kf, bp, b))
    ntr = sum(1 for r in rows if r[1] == 0)
    print(f"rows: {len(rows)} (stride {stride}; train {ntr} "
          f"test {len(rows) - ntr}; impossible b=0 fires "
          f"{imposs})", flush=True)
    jobs = [(role, ck, hot, ret, shape)
            for role in ("fr", "rf") for ck in CHUNKINGS
            for hot in ("next", "drop") for ret in ("shift", "addS")
            for shape in SHAPES]
    print(f"jobs: {len(jobs)} x {len(ORDERS)} orders = "
          f"{len(jobs) * len(ORDERS)} configs", flush=True)
    results = []
    with Pool(nproc, initializer=init_rows,
              initargs=(rows,)) as pool:
        for i, out in enumerate(
                pool.imap_unordered(eval_job, jobs)):
            results.extend(out)
            if (i + 1) % 24 == 0:
                print(f"  ...{i + 1}/{len(jobs)} jobs",
                      flush=True)
    with open("h608_results.tsv", "w") as f:
        for cfg, res in results:
            cells = []
            for w in WS:
                if w not in res:
                    continue
                g, ce, hj, h1, h2, un = res[w]
                cells.append(f"{w} {g} {ce:.4f} {hj:.4f} "
                             f"{h1:.4f} {h2:.4f} {un}")
            f.write(f"{cfg!r}\t" + "\t".join(cells) + "\n")
    def fmt(cfg, res):
        s = f"{cfg}"
        for w in WS:
            if w in res:
                g, ce, hj, h1, h2, un = res[w]
                s += (f"\n    w={w}: groups {g} ceil {ce:.4f} "
                      f"held-out {hj:.4f} ((9,1) {h1:.4f} "
                      f"(9,2) {h2:.4f}) unseen {un}")
        return s
    anchor = [r for c, r in results if c == ANCHOR]
    if anchor:
        print("\nANCHOR (h584/h588 winner tree):")
        print("  " + fmt(ANCHOR, anchor[0]))
    results.sort(key=lambda cr: -cr[1].get(10, (0, 0, 0))[2])
    print("\nTOP 25 by joint held-out @ w=10:")
    for cfg, res in results[:25]:
        print("  " + fmt(cfg, res))
    best14 = sorted(results,
                    key=lambda cr: -cr[1].get(14, (0, 0, 0))[2])
    print("\nTOP 10 by joint held-out @ w=14:")
    for cfg, res in best14[:10]:
        print("  " + fmt(cfg, res))


if __name__ == "__main__":
    main()
