#!/usr/bin/env python3
"""h434: uniform product-rounding grid at the terminal reconstruction."""
from multiprocessing import Pool
exec(open("h431_enriched.py").read().split("if __name__")[0])

def rnd(prod, mode):
    sh = max(prod.bit_length() - 67, 0)
    kept = prod >> sh
    rem = prod & ((1 << sh) - 1)
    if not sh or not rem: return kept
    half = 1 << (sh - 1)
    if mode == "rn": return kept + (1 if (rem > half or (rem == half and kept & 1)) else 0)
    if mode == "aw": return kept + 1
    if mode == "od": return kept | 1
    return kept

def score_row(args):
    d, hws = args
    p = int(d["payload"])
    le2, re2 = int(d["le2"]), int(d["re2"])
    lsign, rsign = int(d["lsign"]), int(d["rsign"])
    pl = int(d["mul"], 16) * int(d["lf"], 16)
    pr = int(d["f4"], 16) * int(d["rf"], 16)
    out = []
    for lm in ("chop", "rn", "aw", "od"):
        lsv = rnd(pl, lm)
        for rm in ("chop", "rn", "aw", "od"):
            rsv = rnd(pr, rm)
            scale = min(le2, re2)
            if p: scale = min(scale, le2 - 8)
            acc = (-1 if lsign else 1) * (lsv << (le2 - scale)) \
                + (-1 if rsign else 1) * (rsv << (re2 - scale))
            if p: acc += (-1 if lsign else 1) * (p << (le2 - 8 - scale))
            c, e = chop67(acc, scale)
            out.append(0 if all(final_cos(c, e, m) == hws[m] for m in MODES) else 1)
    return out

if __name__ == "__main__":
    with Pool(8) as pool:
        res = pool.map(score_row, load(), chunksize=2000)
    names = [f"L_{a}/R_{b}" for a in ("chop","rn","aw","od") for b in ("chop","rn","aw","od")]
    totals = [sum(r[i] for r in res) for i in range(16)]
    for n, t in sorted(zip(names, totals), key=lambda x: x[1]):
        print(f"{n}: violations={t}")
