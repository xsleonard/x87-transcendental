#!/usr/bin/env python3
"""Validate the C scanner against the Python forward() on the same
range: identical tie sets and identical per-tie fields required."""
from multiprocessing import Pool
from h479a_construct import forward

START = 0x9500000000000000
COUNT = 3_000_000

def scan(args):
    s, c = args
    out = []
    for m in range(s, s + c):
        r = forward(m)
        if r is not None:
            out.append(r)
    return out

def main():
    step = COUNT // 8
    with Pool(8) as pool:
        blocks = pool.map(scan, [(START + i * step,
                                  step if i < 7 else COUNT - 7 * step)
                                 for i in range(8)])
    py = {}
    for b in blocks:
        for r in b:
            py[int(r["m"], 16)] = r
    c_rows = {}
    for line in open("h491_val.txt"):
        f = line.split()
        c_rows[int(f[0], 16)] = f
    print(f"python ties: {len(py)}, C ties: {len(c_rows)}")
    only_py = sorted(set(py) - set(c_rows))
    only_c = sorted(set(c_rows) - set(py))
    print(f"only-python: {len(only_py)}, only-C: {len(only_c)}")
    for m in only_py[:5]:
        print(f"  py-only {m:016x} cell={py[m]['cell']}")
    for m in only_c[:5]:
        print(f"  c-only  {m:016x} {c_rows[m][1:6]}")
    both = sorted(set(py) & set(c_rows))
    mism = 0
    for m in both:
        r, f = py[m], c_rows[m]
        cell_c = (int(f[1]), int(f[2]), int(f[3]), int(f[4]))
        if tuple(r["cell"]) != cell_c:
            mism += 1
            if mism <= 3:
                print(f"  field mismatch {m:016x}: py {r['cell']} "
                      f"vs C {cell_c}")
    print(f"common: {len(both)}, field mismatches: {mism}")

if __name__ == "__main__":
    main()
