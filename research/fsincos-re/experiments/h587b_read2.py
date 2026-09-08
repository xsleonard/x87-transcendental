#!/usr/bin/env python3
"""h587b: deep read-window scan on the fixed h587-winner tree
(r4, nat, 14_23, dvec=3s, w=27 low-first).

State families over the final (S, C) words, boundary col
cs = rsh - 54:
  SC:  ((S >> cs+offs) & (2^ws-1), (C >> cs+offc) & (2^wc-1))
       ws in 3..7, offs in -6..2, wc in 2..6, offc in -4..2,
       ws+wc <= 9
  SUM: (((S + C) >> cs+offu) & (2^wu-1),)  wu in 2..8,
       offu in -6..2
Margin resolution res in {4096, 16384} (mb rescaled).
Unseen-state fallback = global (M1) threshold, not 0.
Reports train acc alongside held-out for the top configs.
"""
import json
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


def split_words(chunks):
    S = C = 0
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


ROWS = None
WORDS = None


def init_rows(r, w):
    global ROWS, WORDS
    ROWS = r
    WORDS = w


def fit_thr_hist(hist):
    if not hist:
        return 0
    cands = sorted(hist)
    cands.append(cands[-1] + 1)
    best = (-1, 0)
    for t in cands:
        acc = sum((n1 if mb >= t else n0)
                  for mb, (n0, n1) in hist.items())
        if acc > best[0]:
            best = (acc, t)
    return best[1]


def score(bytr, byte, gthr):
    ok = n = 0
    for st2, hist in byte.items():
        htr = bytr.get(st2)
        bt = fit_thr_hist(htr) if htr else gthr
        for mb, (n0, n1) in hist.items():
            ok += n1 if mb >= bt else n0
            n += n0 + n1
    return ok, n


def eval_cfg(cfg):
    fam = cfg[0]
    tot = {"tr": [0, 0], "te": [0, 0]}
    per = {}
    for key in ROWS:
        parts = ROWS[key]
        words = WORDS[key]
        hists = []
        ghist = defaultdict(lambda: [0, 0])
        for pi in (0, 1):
            by = defaultdict(lambda: defaultdict(lambda: [0, 0]))
            for row, (S, C) in zip(parts[pi], words[pi]):
                mb, fire, rsh = row
                cs = rsh - 2 * W
                if fam == "SC":
                    _, ws, offs, wc, offc, res = cfg
                    st2 = ((S >> max(cs + offs, 0))
                           & ((1 << ws) - 1),
                           (C >> max(cs + offc, 0))
                           & ((1 << wc) - 1))
                else:
                    _, wu, offu, res = cfg
                    st2 = (((S + C) >> max(cs + offu, 0))
                           & ((1 << wu) - 1),)
                mbr = mb if res == 4096 else \
                    (mb * res) // 4096
                by[st2][mbr][fire] += 1
                if pi == 0:
                    ghist[mbr][fire] += 1
            hists.append(by)
        gthr = fit_thr_hist(ghist)
        oktr, ntr = score(hists[0], hists[0], gthr)
        okte, nte = score(hists[0], hists[1], gthr)
        per[str(key)] = (okte, nte)
        tot["tr"][0] += oktr
        tot["tr"][1] += ntr
        tot["te"][0] += okte
        tot["te"][1] += nte
    return (cfg, tot["te"][0] / max(tot["te"][1], 1),
            tot["tr"][0] / max(tot["tr"][1], 1), per)


def load(stride):
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


def main():
    stride = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    rowsd = load(stride)
    slim = {}
    words = {}
    print("computing tree words...", flush=True)
    with Pool(15) as pool:
        for key, parts in rowsd.items():
            wparts = []
            sparts = []
            for part in parts:
                chunks = pool.map(
                    _chunks_row, part,
                    chunksize=max(1, len(part) // 60))
                wparts.append(chunks)
                sparts.append([(mb, fire, rsh)
                               for mb, fire, f4v, rfv, rsh
                               in part])
            words[key] = wparts
            slim[key] = sparts
            print(f"{key}: tr={len(sparts[0])} "
                  f"te={len(sparts[1])}", flush=True)
    cfgs = []
    for res in (4096, 16384):
        for ws in (3, 4, 5, 6, 7):
            for offs in range(-6, 3):
                for wc in (2, 3, 4, 5, 6):
                    for offc in range(-4, 3):
                        if ws + wc <= 9:
                            cfgs.append(("SC", ws, offs, wc,
                                         offc, res))
        for wu in range(2, 9):
            for offu in range(-6, 3):
                cfgs.append(("SUM", wu, offu, res))
    print(f"configs: {len(cfgs)}", flush=True)
    with Pool(15, initializer=init_rows,
              initargs=(slim, words)) as pool:
        res = pool.map(eval_cfg, cfgs,
                       chunksize=max(1, len(cfgs) // 60))
    res.sort(key=lambda r: -r[1])
    for cfg, accte, acctr, per in res[:25]:
        print(f"te {accte:.4f} tr {acctr:.4f}  {cfg}  {per}")
    top = [{"cfg": list(cfg), "acc": accte}
           for cfg, accte, acctr, per in res[:30]]
    json.dump(top, open("h587b_top.json", "w"), indent=1)
    print("wrote h587b_top.json")


def _chunks_row(row):
    mb, fire, f4v, rfv, rsh = row
    return split_words(booth4_chunks(f4v, rfv))


if __name__ == "__main__":
    main()
