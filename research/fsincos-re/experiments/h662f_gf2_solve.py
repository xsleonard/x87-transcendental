#!/usr/bin/env python3
"""h662f: theta ladder — GF(2) parity solve for the block-edge coin.

h662e: 71 identical-window groups (S,B over [w-8, w+16)), members
differing outside the window, agree 71/71 on the coin — it is a
function of those 48 bits (+ discrete context).  Every hand statistic
is flat marginally and pairwise => parity-type function is the prime
suspect.  A single GF(2) linear solve tests ALL 2^48 parities at once:
build rows = window bits + context one-hots + constant, RHS = fire;
Gaussian-eliminate; if the coin is an affine parity of the inputs the
system is CONSISTENT on all 205k rows.

Fallback baseline: depth-limited greedy tree accuracy (held-out) to
catch non-parity but low-complexity structure.
"""
import pickle
import numpy as np
from collections import defaultdict

CACHE = "h662e_rows.pkl"
LO, HI = 10, 18          # window [w-LO, w+HI)


def main():
    out = pickle.load(open(CACHE, "rb"))
    crit = [o for o in out if (o[3] + o[5]) % 8 == 7 and o[3] in (7, 8)]
    print(f"critical rows: {len(crit)}", flush=True)

    rows = []
    for sign, th, fire, pm_up, w, phw, scale, S, B in crit:
        sw = ((S << LO) >> w) & ((1 << (LO + HI)) - 1)
        bw = ((B << LO) >> w) & ((1 << (LO + HI)) - 1)
        bits = [(sw >> i) & 1 for i in range(LO + HI)] \
             + [(bw >> i) & 1 for i in range(LO + HI)] \
             + [int(sign == "dn"), th & 1, pm_up & 1,
                phw & 1, (phw >> 1) & 1, (phw >> 2) & 1,
                scale & 1, 1]
        rows.append((bits, fire))
    F = len(rows[0][0])
    print(f"features: {F}", flush=True)

    X = np.array([r[0] for r in rows], dtype=np.uint8)
    y = np.array([r[1] for r in rows], dtype=np.uint8)

    # GF(2) Gaussian elimination for a consistent affine parity
    # augmented rows as python ints for speed
    aug = [(int("".join(map(str, X[i][::-1])), 2) << 1) | int(y[i])
           for i in range(len(y))]
    # eliminate
    pivots = {}
    inconsistent = 0
    for v in aug:
        for p in sorted(pivots, reverse=True):
            if (v >> (p + 1)) & 1:
                v ^= pivots[p]
        if v > 1:
            p = v.bit_length() - 2      # highest feature bit
            pivots[p] = v
        elif v == 1:
            inconsistent += 1
    print(f"\nGF(2) solve: rank {len(pivots)}, "
          f"INCONSISTENT rows: {inconsistent}")
    if inconsistent == 0:
        # extract one solution: back-substitute free vars = 0
        sol = 0
        for p in sorted(pivots):
            v = pivots[p]
            rhs = v & 1
            acc = rhs
            for q in range(p):
                if (v >> (q + 1)) & 1 and (sol >> q) & 1:
                    acc ^= 1
            if acc:
                sol |= 1 << p
        pred = ((X @ np.array([(sol >> i) & 1 for i in range(F)],
                              dtype=np.uint8)) & 1)
        acc = (pred == y).mean()
        print(f"PARITY FOUND — verify accuracy {acc:.6f}")
        print("mask bits set:",
              [i for i in range(F) if (sol >> i) & 1])
    else:
        print("not a pure parity of these inputs "
              f"({inconsistent}/{len(y)} conflict rows)")

    # tree baseline: greedy information-gain splits, depth 6, held-out
    idx = np.arange(len(y))
    rng = np.random.default_rng(1)
    rng.shuffle(idx)
    half = len(y) // 2
    tr, te = idx[:half], idx[half:]

    def entropy(p):
        if p in (0, 1):
            return 0.0
        return -p * np.log2(p) - (1 - p) * np.log2(1 - p)

    def build(node_idx, depth):
        ys = y[node_idx]
        p = ys.mean()
        if depth == 0 or p in (0, 1) or len(node_idx) < 100:
            return int(p >= 0.5)
        base = entropy(p)
        best = (0.0, None)
        for f in range(F):
            xs = X[node_idx, f]
            p1 = xs.mean()
            if p1 in (0, 1):
                continue
            e = (p1 * entropy(ys[xs == 1].mean())
                 + (1 - p1) * entropy(ys[xs == 0].mean()))
            g = base - e
            if g > best[0]:
                best = (g, f)
        if best[1] is None:
            return int(p >= 0.5)
        f = best[1]
        return (f, build(node_idx[X[node_idx, f] == 0], depth - 1),
                build(node_idx[X[node_idx, f] == 1], depth - 1))

    def apply(tree, i):
        while isinstance(tree, tuple):
            f, l, r = tree
            tree = r if X[i, f] else l
        return tree

    tree = build(tr, 6)
    accte = np.mean([apply(tree, i) == y[i] for i in te])
    print(f"\ntree baseline (depth 6) held-out accuracy: {accte:.4f}")


if __name__ == "__main__":
    main()
