#!/usr/bin/env python3
"""h487f: per-cell step/interval sweep on wrapped (mod-1) sums:
frac(XE), frac(XT+XD), frac(XP+XD), frac(2XT+XD) -- the sub-ulp
remainder family (thresholds become intervals under offset motion,
matching the h486 interval/co-interval cells)."""
from collections import defaultdict
from multiprocessing import Pool
from h487b_fullprec import build_row, SC
from h484_cegis import load_labels

ONE = 1 << SC

def stepish(vals):
    byx = defaultdict(set)
    for x, o in vals:
        byx[x].add(o)
    if any(len(s) > 1 for s in byx.values()):
        return None
    xs = sorted(byx)
    seq = [next(iter(byx[x])) for x in xs]
    def mono(s):
        return all(s[i] <= s[i+1] for i in range(len(s)-1))
    if mono(seq):
        return "up"
    if mono([1-x for x in seq]):
        return "down"
    ones = [i for i, s in enumerate(seq) if s]
    if ones and ones == list(range(ones[0], ones[-1]+1)):
        return "interval"
    zeros = [i for i, s in enumerate(seq) if not s]
    if zeros and zeros == list(range(zeros[0], zeros[-1]+1)):
        return "co-interval"
    return None

COMPS = [
    ("frac(XE)", lambda q: (q["XE"]) % ONE),
    ("frac(XT+XD)", lambda q: (q["XT"] + q["XD"]) % ONE),
    ("frac(XP+XD)", lambda q: (q["XP"] + q["XD"]) % ONE),
    ("frac(2XT+XD)", lambda q: (2*q["XT"] + q["XD"]) % ONE),
    ("frac(XT+2XD)", lambda q: (q["XT"] + 2*q["XD"]) % ONE),
    ("frac(XT-XD)", lambda q: (q["XT"] - q["XD"]) % ONE),
    ("frac(XP-XD)", lambda q: (q["XP"] - q["XD"]) % ONE),
]

def main():
    rows = load_labels()
    with Pool(8) as pool:
        data = [r for r in pool.map(build_row, sorted(rows.items()),
                                    chunksize=50) if r]
    cells = defaultdict(list)
    for o, cell, q in data:
        cells[cell].append((o, q))
    solved = total = 0
    for cell in sorted(cells):
        rs_ = cells[cell]
        if len(rs_) < 8:
            continue
        n1 = sum(o for o, _ in rs_)
        if n1 == 0 or n1 == len(rs_):
            continue
        total += 1
        hits = []
        for name, fn in COMPS:
            r = stepish([(fn(q), o) for o, q in rs_])
            if r:
                hits.append(f"{name}:{r}")
        if hits:
            solved += 1
            print(f"  {cell} n={len(rs_)} f={n1}: " +
                  "; ".join(hits[:3]))
        else:
            print(f"  {cell} n={len(rs_)} f={n1}: none")
    print(f"\nsolved {solved}/{total}")

if __name__ == "__main__":
    main()
