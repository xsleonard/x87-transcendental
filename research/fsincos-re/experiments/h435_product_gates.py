#!/usr/bin/env python3
"""h435: learn per-product increment gates G_R, G_L."""
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
    def feats(prod, kept, other_low3):
        sh = max(prod.bit_length() - 67, 0)
        rem = prod & ((1 << sh) - 1)
        half = 1 << (sh - 1) if sh else 0
        top8 = (rem >> (sh - 8)) if sh >= 8 else rem << (8 - sh)
        return (sh, 1 if rem > half else 0, 1 if rem == half else 0,
                int(top8) & 0xFF, kept & 7, other_low3,
                1 if (rem & (half - 1)) else 0 if half else 0)
    fR = feats(pr := f4 * rf, rs, f4 & 7) + (rf & 7,)
    fL = feats(pl := mul * lf, ls, mul & 7) + (lf & 7,)
    # labels: 1 must-fire, 0 must-not, -1 dontcare
    lR = 1 if (not base and rup) else (0 if (base and not rup) else -1)
    lL = 1 if (not base and lup) else (0 if (base and not lup) else -1)
    return fR, lR, fL, lL

if __name__ == "__main__":
    with Pool(8) as pool:
        rows = pool.map(build_lbl, load(), chunksize=2000)
    for tag, idx in (("G_R", (0, 1)), ("G_L", (2, 3))):
        pos = Counter(); neg = Counter()
        for r in rows:
            f, l = r[idx[0]], r[idx[1]]
            if l == 1: pos[f] += 1
            elif l == 0: neg[f] += 1
        conflicts = set(pos) & set(neg)
        print(f"{tag}: must-fire rows={sum(pos.values())} ({len(pos)} uniq) "
              f"must-not rows={sum(neg.values())} ({len(neg)} uniq) "
              f"CONFLICTING feature-vectors={len(conflicts)} "
              f"(rows {sum(pos[c]+neg[c] for c in conflicts)})")
        if not conflicts:
            print(f"  {tag} SEPARABLE over product-local features!")
            for f in sorted(pos)[:6]: print("   fire:", f)
