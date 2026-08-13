#!/usr/bin/env python3
"""h486: close the CEGIS holes — per-cell arbitrary-threshold sweeps,
interval tests, and parity forms; plus empirical 2D maps of the gate.

For each mixed cell and each windowed quantity u:
  (a) exact threshold: sorting rows by u, is fire = [u >= theta] for
      some theta?  (labels must be 0...0 1...1 after sort, either
      direction)
  (b) exact interval: fire = [theta1 <= u < theta2]?
  (c) parity: fire = u&1, (u>>1)&1, popcount(u)&1 (and complements)
Then ASCII maps: fire rate over (T4 x D4) nibbles for the six
biggest cells and pooled.  Local only; data = 1,310 labeled rows.
"""
import json
from collections import defaultdict
from multiprocessing import Pool
from h484_cegis import load_labels, quantities

def build_row(item):
    mhex, o = item
    if o == 2:
        return None
    cell, payload, q = quantities(mhex)
    return (o, cell, q)

def main():
    rows = load_labels()
    with Pool(8) as pool:
        data = [r for r in pool.map(build_row, sorted(rows.items()),
                                    chunksize=50) if r]
    print(f"rows: {len(data)}")
    QN = sorted(data[0][2])
    cells = defaultdict(list)
    for o, cell, q in data:
        cells[cell].append((o, q))

    def thr_exact(vals):
        # vals: list (u, o) -> exact threshold either direction?
        vals = sorted(vals)
        labs = [o for _, o in vals]
        # ascending 0->1
        asc = all(labs[i] <= labs[i+1] or vals[i][0] == vals[i+1][0]
                  for i in range(len(labs)-1))
        # need consistency for equal u values
        byu = defaultdict(set)
        for u, o in vals:
            byu[u].add(o)
        if any(len(s) > 1 for s in byu.values()):
            return None
        us = sorted(byu)
        seq = [next(iter(byu[u])) for u in us]
        def is_step(s):
            return all(s[i] <= s[i+1] for i in range(len(s)-1))
        if is_step(seq):
            return "up"
        if is_step([1-x for x in seq]):
            return "down"
        # interval
        ones = [i for i, x in enumerate(seq) if x == 1]
        if ones and ones == list(range(ones[0], ones[-1]+1)):
            return "interval"
        zeros = [i for i, x in enumerate(seq) if x == 0]
        if zeros and zeros == list(range(zeros[0], zeros[-1]+1)):
            return "co-interval"
        return None

    print("\n=== per-cell exact threshold/interval/parity search ===")
    solved = defaultdict(list)
    for cell in sorted(cells):
        rs_ = cells[cell]
        if len(rs_) < 8:
            continue
        n1 = sum(o for o, _ in rs_)
        if n1 == 0 or n1 == len(rs_):
            continue
        hits = []
        for name in QN:
            r = thr_exact([(q[name], o) for o, q in rs_])
            if r:
                hits.append(f"{name}:{r}")
            for bit in (0, 1):
                if all(((q[name] >> bit) & 1) == o for o, q in rs_):
                    hits.append(f"{name}.bit{bit}")
                if all(((q[name] >> bit) & 1) == 1 - o
                       for o, q in rs_):
                    hits.append(f"~{name}.bit{bit}")
            if all(bin(q[name]).count("1") % 2 == o for o, q in rs_):
                hits.append(f"{name}.parity")
            if all(bin(q[name]).count("1") % 2 == 1 - o
                   for o, q in rs_):
                hits.append(f"~{name}.parity")
        status = "; ".join(hits[:4]) if hits else "none"
        if hits:
            solved[cell] = hits
        print(f"  {cell} n={len(rs_)} fires={n1}: {status}")
    print(f"\ncells with any exact form: {len(solved)}")

    print("\n=== fire-rate maps: T4 nibble (rows) x D4 nibble (cols) "
          "===")
    big = sorted(cells, key=lambda c: -len(cells[c]))[:4]
    for cell in big + ["POOLED"]:
        if cell == "POOLED":
            rs_ = [x for c in cells.values() for x in c]
        else:
            rs_ = cells[cell]
        grid = defaultdict(lambda: [0, 0])
        for o, q in rs_:
            gkey = (q["T4"], q["D4"])
            grid[gkey][0] += 1
            grid[gkey][1] += o
        print(f"\n{cell} (n={len(rs_)}):")
        hdr = "    " + " ".join(f"D={d:2d}" for d in range(16))
        print(hdr)
        for t in range(16):
            cells_str = []
            for dd in range(16):
                tot, f = grid[(t, dd)]
                cells_str.append(" .. " if not tot else
                                 f"{f/tot:4.2f}"[:4])
            print(f"T{t:2d} " + " ".join(cells_str))

if __name__ == "__main__":
    main()
