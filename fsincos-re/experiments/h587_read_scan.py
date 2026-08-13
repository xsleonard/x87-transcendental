#!/usr/bin/env python3
"""h587: escalation after the h586 plateau — vary what h584/h586
held fixed:
  READ WINDOW: state = (S >> (cs+offs)) & (2^ws-1),
               (C >> (cs+offc)) & (2^wc-1)
               ws,wc in {1,2,3}; offs in {-2..1}; offc in {-2..2}
               (h584 == ws=1,offs=0,wc=1,offc=1)
  COMPRESSOR:  c42 = csa(csa(a,b,c),d)  (h584/h586)
               h42 = true 4:2 cell with horizontal cout chain:
                     x=a^b^c; cin=maj(a,b,c)<<1;
                     S=x^d^cin; C=((x&d)|(~x&cin))<<1
  ROWGEN:      r4 = radix-4 Booth (h584)   r8 = radix-8 Booth
               (digits -4..4, x3 hard multiple, overlap 1 bit)
Fixed: role fr, w=27 low-first, dvec=(3,)*7 (d = 4th input),
lasthot=drop, ret=shift (all proven inert in h586).
Modes:
  selftest              verify h42 value-conservation + r8 rows
  scan STRIDE           stage A: (rowgen, comp, gname, pname) x
                        read grid, joint objective
Uses h586_band.tsv.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
import random

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
    "spl": [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 10, 14],
            [11, 12, 13, 15]],
}
PAIRINGS = {"12_34": ((0, 1), (2, 3)),
            "13_24": ((0, 2), (1, 3)),
            "14_23": ((0, 3), (1, 2))}


def csa(a, b, c):
    return (a ^ b ^ c) & MASK, \
        (((a & b) | (a & c) | (b & c)) << 1) & MASK


def c42(a, b, c, d):
    s1, c1 = csa(a, b, c)
    return csa(s1, c1, d)


def h42(a, b, c, d):
    x = a ^ b ^ c
    cin = (((a & b) | (a & c) | (b & c)) << 1) & MASK
    S = (x ^ d ^ cin) & MASK
    xd = x ^ d
    C = ((((xd & cin) | ((~xd) & d)) << 1)) & MASK
    return S, C


COMPS = {"c42": c42, "h42": h42}


def booth4_chunks(f4v, rfv):
    nb = rfv.bit_length()
    out = []
    pos = 0
    while pos < nb:
        y = (rfv >> pos) & ((1 << W) - 1)
        y2 = y << 1
        nb2 = max(y2.bit_length(), 1)
        rows = []
        pend = 0
        for i in range(0, nb2, 2):
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


def booth8_chunks(f4v, rfv):
    """radix-8 Booth: 4-bit windows step 3, digits -4..4; hot-one
    merged into next row (same convention as r4)."""
    nb = rfv.bit_length()
    out = []
    pos = 0
    while pos < nb:
        y = (rfv >> pos) & ((1 << W) - 1)
        y2 = y << 1
        nb2 = max(y2.bit_length(), 1)
        rows = []
        pend = 0
        for i in range(0, nb2, 3):
            w4 = (y2 >> i) & 15
            # radix-8 digit from 4-bit window w4 = (b3 b2 b1 b0):
            # value = -4*b3 + 2*b2 + b1 + b0
            b3, b2, b1, b0 = (w4 >> 3) & 1, (w4 >> 2) & 1, \
                (w4 >> 1) & 1, w4 & 1
            d = -4 * b3 + 2 * b2 + b1 + b0
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


ROWGENS = {"r4": booth4_chunks, "r8": booth8_chunks}


def split_words(chunks, comp, grouping, pairing):
    f = COMPS[comp]
    S = C = 0
    last = len(chunks) - 1
    for ci, rows in enumerate(chunks):
        it = rows + [S, C]
        gs = [f(it[g[0]], it[g[1]], it[g[2]], it[g[3]])
              for g in grouping]
        (i1, i2), (i3, i4) = pairing
        l2a = f(gs[i1][0], gs[i1][1], gs[i2][0], gs[i2][1])
        l2b = f(gs[i3][0], gs[i3][1], gs[i4][0], gs[i4][1])
        S, C = f(l2a[0], l2a[1], l2b[0], l2b[1])
        if ci < last:
            S >>= W
            C >>= W
    return S, C


ROWS = None
CACHE = {"key": None, "data": None}


def init_rows(r):
    global ROWS
    ROWS = r


def get_words(key, rowgen, comp, gname, pname):
    """Cache final (S, C) words per row for a full tree config;
    read variants then reuse them for free."""
    ck = (key, rowgen, comp, gname, pname)
    if CACHE["key"] != ck:
        tr, te = ROWS[key]
        gen = ROWGENS[rowgen]
        grouping = GROUPINGS[gname]
        pairing = PAIRINGS[pname]
        CACHE["data"] = [
            [split_words(gen(f4v, rfv), comp, grouping, pairing)
             for mb, fire, f4v, rfv, rsh in part]
            for part in (tr, te)]
        CACHE["key"] = ck
    return CACHE["data"]


def fit_score(bytr, byte):
    ok = n = 0
    for st2, hist in byte.items():
        htr = bytr.get(st2)
        if htr:
            cands = sorted(htr)
            cands.append(cands[-1] + 1)
            best = (-1, 0)
            for t in cands:
                acc = sum((n1 if mb >= t else n0)
                          for mb, (n0, n1) in htr.items())
                if acc > best[0]:
                    best = (acc, t)
            bt = best[1]
        else:
            bt = 0
        for mb, (n0, n1) in hist.items():
            ok += n1 if mb >= bt else n0
            n += n0 + n1
    return ok, n


def eval_cfg(cfg):
    rowgen, comp, gname, pname, ws, offs, wc, offc = cfg
    ms, mc = (1 << ws) - 1, (1 << wc) - 1
    tot_ok = tot_n = 0
    per = {}
    for key in ROWS:
        wtr, wte = get_words(key, rowgen, comp, gname, pname)
        tr, te = ROWS[key]
        hists = []
        for part, wl in ((tr, wtr), (te, wte)):
            by = defaultdict(lambda: defaultdict(lambda: [0, 0]))
            for row, (S, C) in zip(part, wl):
                mb, fire, f4v, rfv, rsh = row
                cs = rsh - 2 * W
                st2 = ((S >> max(cs + offs, 0)) & ms,
                       (C >> max(cs + offc, 0)) & mc)
                by[st2][mb][fire] += 1
            hists.append(by)
        ok, n = fit_score(hists[0], hists[1])
        per[str(key)] = (ok, n)
        tot_ok += ok
        tot_n += n
    return cfg, tot_ok / max(tot_n, 1), per


def load_rows(stride):
    rowsd = defaultdict(lambda: ([], []))
    cnt = defaultdict(int)
    for line in open("h586_band.tsv"):
        f = line.split()
        key = ((int(f[1]), int(f[2]), int(f[3])), f[4])
        if key not in dict.fromkeys(TARGETS):
            continue
        cnt[key] += 1
        if (cnt[key] - 1) % stride:
            continue
        m = int(f[0], 16)
        half = (m * 2654435761) & 1
        rowsd[key][half].append(
            (int(f[5]), int(f[6]), int(f[7], 16), int(f[8], 16),
             int(f[9])))
    return dict(rowsd)


def selftest():
    rng = random.Random(58701)
    for _ in range(500):
        a, b, c, d = (rng.getrandbits(150) for _ in range(4))
        for name, f in COMPS.items():
            S, C = f(a, b, c, d)
            assert (S + C) % (1 << WIDTH) == \
                (a + b + c + d) % (1 << WIDTH), name
    # r8 rows must sum to the product (single chunk, no pend loss)
    for _ in range(200):
        x = rng.getrandbits(67)
        y = rng.getrandbits(24)
        rows = []
        pend = 0
        y2 = y << 1
        for i in range(0, max(y2.bit_length(), 1), 3):
            w4 = (y2 >> i) & 15
            b3, b2, b1, b0 = (w4 >> 3) & 1, (w4 >> 2) & 1, \
                (w4 >> 1) & 1, w4 & 1
            dd = -4 * b3 + 2 * b2 + b1 + b0
            row = 0
            if dd > 0:
                row = (dd * x << i) & MASK
            elif dd < 0:
                row = ((((~((-dd) * x)) & MASK) << i) & MASK)
            row |= pend
            pend = (1 << i) if dd < 0 else 0
            rows.append(row)
        tot = (sum(rows) + pend) % (1 << WIDTH)
        assert tot == (x * y) % (1 << WIDTH), (x, y)
    print("selftest OK")


def main_scan(stride):
    rowsd = load_rows(stride)
    for key, (tr, te) in rowsd.items():
        print(f"{key}: tr={len(tr)} te={len(te)}", flush=True)
    cfgs = []
    reads = []
    for ws in (1, 2, 3):
        for offs in (-2, -1, 0, 1):
            for wc in (1, 2, 3):
                for offc in (-2, -1, 0, 1, 2):
                    reads.append((ws, offs, wc, offc))
    for rowgen in ("r4", "r8"):
        for comp in ("c42", "h42"):
            for gname in GROUPINGS:
                for pname in PAIRINGS:
                    for rd in reads:
                        cfgs.append((rowgen, comp, gname, pname)
                                    + rd)
    # sort so tree-word cache is reused across read variants
    cfgs.sort()
    print(f"configs: {len(cfgs)}", flush=True)
    with Pool(15, initializer=init_rows,
              initargs=(rowsd,)) as pool:
        res = pool.map(eval_cfg, cfgs,
                       chunksize=max(1, len(cfgs) // 60))
    res.sort(key=lambda r: -r[1])
    for cfg, acc, per in res[:25]:
        print(f"{acc:.4f}  {cfg}  {per}")
    import json
    top = [{"cfg": list(cfg), "acc": acc}
           for cfg, acc, per in res[:40]]
    json.dump(top, open("h587_top.json", "w"), indent=1)
    print("wrote h587_top.json")


if __name__ == "__main__":
    if sys.argv[1] == "selftest":
        selftest()
    else:
        main_scan(int(sys.argv[2]) if len(sys.argv) > 2 else 8)
