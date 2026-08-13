#!/usr/bin/env python3
"""h498: per-(stratum, m_top8) block purity census.  If fire rate is
block-constant (pure 0/1 in most blocks, mixed only at block
boundaries or in few blocks), the gate = lookup on m's top byte per
stratum + residual texture.  Reports purity, the block table shape,
and whether mixed blocks cluster at block edges."""
from collections import defaultdict
from multiprocessing import Pool
from h497_transition import load_rows, build

def main():
    rows = load_rows()
    with Pool(8) as pool:
        data = pool.map(build, rows, chunksize=500)
    blocks = defaultdict(lambda: [0, 0])
    for s, m, fr, iv, fire in data:
        b = m >> 56                       # top 8 bits of m
        c = blocks[(s, b)]
        c[0] += 1
        c[1] += fire
    strata = defaultdict(dict)
    for (s, b), (n, f) in blocks.items():
        if n >= 40:
            strata[s][b] = (n, f)
    pure = mixed = 0
    prows = mrows = 0
    for s in sorted(strata):
        bl = strata[s]
        line = []
        for b in sorted(bl):
            n, f = bl[b]
            r = f / n
            if r <= 0.02 or r >= 0.98:
                pure += 1
                prows += n
                line.append("0" if r <= 0.02 else "#")
            else:
                mixed += 1
                mrows += n
                line.append("x")
        print(f"  {s}: blocks {min(bl):02x}-{max(bl):02x} "
              f"[{''.join(line)}]")
    print(f"\npure blocks {pure} ({prows} rows), mixed {mixed} "
          f"({mrows} rows) -> block-pure fraction "
          f"{prows/(prows+mrows):.4f}")

    # finer: are mixed blocks resolved at m_top10?
    blocks10 = defaultdict(lambda: [0, 0])
    for s, m, fr, iv, fire in data:
        b8 = m >> 56
        if (s, b8) in blocks and blocks[(s, b8)][0] >= 40:
            n, f = blocks[(s, b8)]
            r = f / n
            if 0.02 < r < 0.98:
                b10 = m >> 54
                c = blocks10[(s, b10)]
                c[0] += 1
                c[1] += fire
    p10 = m10 = pr = mr = 0
    for (s, b), (n, f) in blocks10.items():
        if n < 25:
            continue
        r = f / n
        if r <= 0.02 or r >= 0.98:
            p10 += 1
            pr += n
        else:
            m10 += 1
            mr += n
    print(f"within mixed-8 blocks at top-10 bits: pure {p10} "
          f"({pr} rows), mixed {m10} ({mr} rows)")

if __name__ == "__main__":
    main()
