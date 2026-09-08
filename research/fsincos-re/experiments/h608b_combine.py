#!/usr/bin/env python3
"""h608b: are the two best h608 trees carrying the SAME state?

Census on clean (9,1)/(9,2)@-72 up rows with the JOINT key
(stratum, S^A_w, C^A_w, S^B_w, C^B_w) for
  A = anchor  (fr, 27x3, next, shift, slot16/nat/14_23, adj)
  B = h608 best (fr, 27x3, drop, shift, slot16/fb1/12_34, adj)
vs each alone, w in {10, 14}.  If joint held-out ~= B alone,
B's gain subsumes A (one state, recoded); a further joint gain
WITH transfer means two distinct state fragments -> more to
mine in-class.  Same protocol as h608 (bit-16 m-hash, unseen ->
pred=b).
"""
from collections import defaultdict
from multiprocessing import Pool
from h608_tree_clean import booth_chunks, reduce_cfg

CFG_A = ("fr", "27x3", "next", "shift", ("slot16", "nat", "14_23"),
         "adj")
CFG_B = ("fr", "27x3", "drop", "shift", ("slot16", "fb1", "12_34"),
         "adj")
WS = (10, 14)


def words(args):
    f4v, rfv = args
    out = []
    for role, ck, hot, ret, shape, order in (CFG_A, CFG_B):
        chunks = booth_chunks(f4v, rfv, role, ck, hot)
        out.append(reduce_cfg(chunks, ret, shape, order))
    return out


def census(recs, name):
    for w in WS:
        tr = defaultdict(lambda: [0, 0])
        te = defaultdict(lambda: [0, 0, 0, 0])
        for gk_parts, half, bp, b in recs[w]:
            gk = gk_parts
            if half == 0:
                tr[gk][bp] += 1
            else:
                te[gk][bp * 2 + b] += 1
        ceil_ok = sum(max(c) for c in tr.values())
        ceil_n = sum(sum(c) for c in tr.values())
        ho = {1: [0, 0], 2: [0, 0]}
        unseen = 0
        for gk, (b00, b01, b10, b11) in te.items():
            low3 = gk[0]
            n = b00 + b01 + b10 + b11
            c = tr.get(gk)
            if c is None:
                unseen += n
                ok = b00 + b11
            elif c[0] >= c[1]:
                ok = b00 + b01
            else:
                ok = b10 + b11
            ho[low3][0] += ok
            ho[low3][1] += n
        hj = (ho[1][0] + ho[2][0]) / max(ho[1][1] + ho[2][1], 1)
        print(f"  {name} w={w}: groups {len(tr)} "
              f"ceil {ceil_ok / max(ceil_n, 1):.4f} "
              f"held-out {hj:.4f} "
              f"((9,1) {ho[1][0] / max(ho[1][1], 1):.4f} "
              f"(9,2) {ho[2][0] / max(ho[2][1], 1):.4f}) "
              f"unseen {unseen}", flush=True)


def main():
    rows = []
    for line in open("h592_band.tsv"):
        f = line.split()
        low3, fire = int(f[2]), int(f[6])
        f4v, rfv = int(f[7], 16), int(f[8], 16)
        kf, Vlow = int(f[10]), int(f[11], 16)
        B_low = (f4v * rfv) & ((1 << kf) - 1)
        APf_low = (Vlow + B_low) & ((1 << kf) - 1)
        b = 1 if APf_low < B_low else 0
        if fire and b == 0:
            continue
        bp = 0 if fire else b
        half = (int(f[0], 16) * 2654435761 >> 16) & 1
        rows.append((low3, half, f4v, rfv, kf, bp, b))
    print(f"rows: {len(rows)}", flush=True)
    with Pool(14) as pool:
        ws = pool.map(words, [(r[2], r[3]) for r in rows],
                      chunksize=2000)
    recs = {"A": {w: [] for w in WS}, "B": {w: [] for w in WS},
            "AB": {w: [] for w in WS}}
    for (low3, half, f4v, rfv, kf, bp, b), wd in zip(rows, ws):
        wins = {}
        for name, (S, C, col0) in zip("AB", wd):
            fb = kf - col0
            for w in WS:
                wins[(name, w)] = ((S >> (fb - w)) & ((1 << w) - 1),
                                   (C >> (fb - w)) & ((1 << w) - 1))
        for w in WS:
            recs["A"][w].append(((low3,) + wins[("A", w)],
                                 half, bp, b))
            recs["B"][w].append(((low3,) + wins[("B", w)],
                                 half, bp, b))
            recs["AB"][w].append(((low3,) + wins[("A", w)]
                                  + wins[("B", w)], half, bp, b))
    for name in ("A", "B", "AB"):
        census(recs[name], name)


if __name__ == "__main__":
    main()
