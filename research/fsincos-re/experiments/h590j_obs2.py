#!/usr/bin/env python3
"""h590j: census of CLASS-observability (no alias crossing the
d>=1 boundary) for near-threshold fresh rows, by R mod 8."""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import qrow3

def check(args):
    mhex, ce = args
    if ce != -72:
        return None
    (m, R, A, P, B_full, rsh, rd, lsh, ld, s4, t4, bsh, k,
     dist, low3) = qrow3(mhex)
    if dist != 9 or low3 not in (1, 2):
        return None
    refs = {d: tuple(final_cosine_result(-(R + d), ce, md)
                     for md in ROUNDING_MODES)
            for d in range(-3, 4)}
    ok = True
    for d in range(-3, 1):
        for d2 in range(1, 4):
            if refs[d] == refs[d2]:
                ok = False
    return (low3, R & 7, 1 if ok else 0)

def main():
    fresh = []
    seen = set()
    for line in open("ties_h585.txt"):
        f = line.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        if int(f[9]) > 0 or int(f[1]) != 9 or \
                int(f[2]) not in (1, 2):
            continue
        fresh.append((f[0], int(f[8])))
    with Pool(15) as pool:
        res = pool.map(check, fresh[:20000], chunksize=200)
    tab = defaultdict(lambda: [0, 0])
    for r in res:
        if r is None:
            continue
        low3, r8, ok = r
        tab[(low3, r8)][ok] += 1
    print("class-observability by (low3, R mod 8):")
    for k in sorted(tab):
        c = tab[k]
        n = c[0] + c[1]
        print(f"  {k}: n={n} observable={c[1]} "
              f"({c[1] / n:.3f})")

if __name__ == "__main__":
    main()
