#!/usr/bin/env python3
"""h648: close the u-table — structure printer + exhaustive formula search.

Reads h647_constraints.pkl: {(dist, s4, side, low3, third):
  ("pin", u) | ("le", u) | ("ge", u) | ("pinrange", lo, hi) | ("noisy",...)}

Part 1: aligned tables per (s4, side, dist) with thirds as columns, and
discrete difference maps.
Part 2: exhaustive search of integer formula families against every pin
and bound; families searched per (s4, side) block and globally:

    u = M0 * floor((A*L + B1*b1 + B2*b2 + C*d + D) / K)
        + E*(L%2) + F*b1 + G*b2 + H*d + I0

with small integer ranges.  A formula passes only if consistent with
EVERY pin/bound in its block.
"""
import pickle, sys
from collections import defaultdict
from itertools import product

CONS = pickle.load(open("h647_constraints.pkl", "rb"))


def cell_str(c):
    if c is None:
        return "     ."
    k = c[0]
    if k == "pin":
        return f"{c[1]:>6}"
    if k == "le":
        return f" <={c[1]:>3}"
    if k == "ge":
        return f" >={c[1]:>3}"
    if k == "pinrange":
        return f"{c[1]}..{c[2]}"
    return f" ~{c[1]}!"


def main():
    blocks = defaultdict(dict)
    for (d, s4, side, L, t), con in CONS.items():
        blocks[(s4, side)][(d, L, t)] = con

    # ---------------- Part 1: tables ----------------
    for (s4, side) in sorted(blocks):
        cells = blocks[(s4, side)]
        dists = sorted({k[0] for k in cells})
        print(f"\n===== BLOCK s4={s4} side={side} =====")
        for d in dists:
            print(f"  dist={d}:   third:    0      1      2")
            for L in range(8):
                row = [cells.get((d, L, t)) for t in range(3)]
                if all(r is None for r in row):
                    continue
                print(f"    low3={L}: " + " ".join(cell_str(r) for r in row))
        # difference maps over pins
        pins = {k: v[1] for k, v in cells.items()
                if v[0] == "pin" or (v[0] == "noisy" and v[2] <= 3)}
        dl = sorted({(k[0], k[2]) for k in pins})
        print("  d(u)/d(low3) at fixed (dist,third):")
        for (d, t) in dl:
            seq = [(L, pins[(d, L, t)]) for L in range(8)
                   if (d, L, t) in pins]
            if len(seq) >= 2:
                diffs = [(seq[i+1][0], seq[i+1][1] - seq[i][1],
                          seq[i+1][0] - seq[i][0])
                         for i in range(len(seq) - 1)]
                s = " ".join(f"L{a}:+{b}/{c}" if b >= 0 else f"L{a}:{b}/{c}"
                             for a, b, c in diffs)
                print(f"    dist={d} third={t}: {s}")
        print("  d(u)/d(third) at fixed (dist,low3):")
        for d in dists:
            for L in range(8):
                seq = [(t, pins[(d, L, t)]) for t in range(3)
                       if (d, L, t) in pins]
                if len(seq) >= 2:
                    diffs = [seq[i+1][1] - seq[i][1]
                             for i in range(len(seq) - 1)]
                    print(f"    dist={d} low3={L}: {diffs}")
        print("  d(u)/d(dist) at fixed (low3,third):")
        for L in range(8):
            for t in range(3):
                seq = [(d, pins[(d, L, t)]) for d in dists
                       if (d, L, t) in pins]
                if len(seq) >= 2:
                    diffs = [(seq[i+1][0], seq[i+1][1] - seq[i][1],
                              seq[i+1][0] - seq[i][0])
                             for i in range(len(seq) - 1)]
                    s = " ".join(f"d{a}:{b}/{c}" for a, b, c in diffs)
                    print(f"    low3={L} third={t}: {s}")

    # ---------------- Part 2: search ----------------
    def consistent(u, con):
        k = con[0]
        if k == "pin":
            return u == con[1]
        if k == "le":
            return u <= con[1]
        if k == "ge":
            return u >= con[1]
        if k == "pinrange":
            return con[1] <= u <= con[2]
        if k == "noisy" and con[2] <= 3:
            return u == con[1]      # boundary-row cells: effective pins
        return True

    print("\n===== FORMULA SEARCH per block =====")
    sys.stdout.flush()
    for (s4, side) in sorted(blocks):
        cells = blocks[(s4, side)]
        items = list(cells.items())
        hits = []
        for M0, K in product((1, 2), (1, 2, 3, 4)):
            for A in (1, 2):
                for B1, B2 in product(range(0, 5), repeat=2):
                    for C in range(-6, 1):
                        for E in (-1, 0, 1):
                            for D in range(-30, 31):
                                ok = True
                                for (d, L, t), con in items:
                                    b1 = 1 if t >= 1 else 0
                                    b2 = 1 if t >= 2 else 0
                                    u = M0 * ((A * L + B1 * b1 + B2 * b2
                                               + C * d + D) // K) \
                                        + E * (L % 2)
                                    if not consistent(u, con):
                                        ok = False
                                        break
                                if ok:
                                    hits.append((M0, K, A, B1, B2, C, E, D))
        print(f"block s4={s4} side={side}: {len(items)} constraints, "
              f"{len(hits)} formulas pass")
        for h in hits[:12]:
            M0, K, A, B1, B2, C, E, D = h
            print(f"   u = {M0}*floor(({A}L + {B1}b1 + {B2}b2 "
                  f"{C:+d}d {D:+d})/{K}) {E:+d}*(L%2)")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
