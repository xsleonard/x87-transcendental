#!/usr/bin/env python3
"""h436: relabel (R-priority) and extract compact G_R/G_L trees."""
from collections import Counter
from multiprocessing import Pool
exec(open("h431_enriched.py").read().split("if __name__")[0])

def build_lbl(args):
    d, hws = args
    p = int(d["payload"])
    le2, re2 = int(d["le2"]), int(d["re2"])
    ls, rs = int(d["ls"], 16), int(d["rs"], 16)
    lsign, rsign = int(d["lsign"]), int(d["rsign"])
    mul, lf = int(d["mul"], 16), int(d["lf"], 16)
    f4, rf = int(d["f4"], 16), int(d["rf"], 16)
    def ok(lsv, rsv):
        scale = min(le2, re2)
        if p: scale = min(scale, le2 - 8)
        acc = (-1 if lsign else 1) * (lsv << (le2 - scale)) \
            + (-1 if rsign else 1) * (rsv << (re2 - scale))
        if p: acc += (-1 if lsign else 1) * (p << (le2 - 8 - scale))
        c, e = chop67(acc, scale)
        return all(final_cos(c, e, m) == hws[m] for m in MODES)
    base, rup, lup = ok(ls, rs), ok(ls, rs + 1), ok(ls + 1, rs)
    def feats(prod, kept, m3, o3):
        sh = max(prod.bit_length() - 67, 0)
        rem = prod & ((1 << sh) - 1)
        half = 1 << (sh - 1) if sh else 0
        top8 = (rem >> (sh - 8)) if sh >= 8 else rem << (8 - sh)
        return (sh, 1 if rem > half else 0, 1 if rem == half else 0,
                int(top8) & 0xFF, kept & 7, m3,
                (1 if (rem & (half - 1)) else 0) if half else 0, o3)
    fR = feats(f4 * rf, rs, f4 & 7, rf & 7)
    fL = feats(mul * lf, ls, mul & 7, lf & 7)
    lR = 1 if (not base and rup) else (0 if (base and not rup) else -1)
    lL = 1 if (not base and lup and not rup) else (0 if (base and not lup) else -1)
    return fR, lR, fL, lL

FN = ("sh","gt_half","eq_half","disc_top8","kept3","m3","sticky","o3")
def tree(rows, depth, path):
    pos = [r for r in rows if r[1] == 1]
    neg = [r for r in rows if r[1] == 0]
    if not pos: return [(path, "NOFIRE", len(rows))]
    if not neg: return [(path, "FIRE", len(rows))]
    if depth == 0: return None
    best = None
    for fi in range(8):
        for v in sorted({r[0][fi] for r in rows})[1:]:
            lo = [r for r in rows if r[0][fi] < v]
            hi = [r for r in rows if r[0][fi] >= v]
            mix = sum(1 for part in (lo, hi)
                      if {r[1] for r in part} >= {0, 1})
            sc = (mix, -min(len(lo), len(hi)))
            if best is None or sc < best[0]:
                best = (sc, fi, v, lo, hi)
    _, fi, v, lo, hi = best
    rl = tree(lo, depth - 1, path + [f"{FN[fi]}<{v}"])
    rh = tree(hi, depth - 1, path + [f"{FN[fi]}>={v}"])
    if rl is None or rh is None: return None
    return rl + rh

if __name__ == "__main__":
    with Pool(8) as pool:
        rows = pool.map(build_lbl, load(), chunksize=2000)
    for tag, i0, i1 in (("G_R", 0, 1), ("G_L", 2, 3)):
        lab = [(r[i0], r[i1]) for r in rows if r[i1] >= 0]
        pos = Counter(f for f, l in lab if l == 1)
        neg = Counter(f for f, l in lab if l == 0)
        confl = set(pos) & set(neg)
        print(f"{tag}: fire={sum(pos.values())} not={sum(neg.values())} conflicts={len(confl)}")
        if confl: continue
        uniq = [(f, 1) for f in pos] + [(f, 0) for f in neg]
        for depth in (2, 3, 4, 5, 6):
            t = tree(uniq, depth, [])
            if t:
                fires = [x for x in t if x[1] == "FIRE"]
                print(f"  depth {depth}: {len(t)} leaves, {len(fires)} FIRE leaves")
                for path, k, n in t:
                    if k == "FIRE":
                        print(f"    FIRE ({n} vecs): {' & '.join(path)}")
                break
