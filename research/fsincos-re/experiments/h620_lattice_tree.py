#!/usr/bin/env python3
"""h620: the h490-class rerun on clean labels with the h613
comparator-lattice constraint — CAN A TREE-STATE READOUT
REPLACE THE ZONE TABLES?

Hypothesis: j is digit-selection on the redundant boundary
field of the B = f4*rf multiply: j = round(alpha * Q + beta),
Q = a window of the tree's resolved (or unresolved) words at
the retirement boundary, alpha GLOBAL (one number; lattice
prediction alpha ~ 3/(8 * 2^(w-6)) for a w-bit window ending
one bit above the boundary), beta per stratum-side only.

Trees (word-level (S,C) per h584/h608 machinery):
  T1 fr/27x3/next/nat_14_23 (M3 winner)
  T2 fr/27x3/drop/fb1_12_34 (h608 best-transfer)
  T3 rf/27x3/next/nat_14_23 (rf as multiplicand)
  T4 fr/radix8-hard3/seq    (never tried with hard multiple)
  T5 fr/27x3/next/seqi      (3:2 ladder)
  T6 fr/27x3/next/eo        (even/odd split)
Readouts: Q in {S+C, S, C}; windows w in {6, 10, 14, 18}
ending one bit above the boundary column.
Rows: h616 + h619 labeled sets (alias-robust J-intervals),
stratified subsample; train/held-out by m-hash bit 16.
Baselines: const-j per stratum-side; the current zone model.
Usage: h620_lattice_tree.py [MAXROWS]
"""
import json
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import E2M
from h453_chain_variants import (C6_1, C6_3, C6_5, C6_2, C6_4,
                                 C6_6, build_chain, mul_round)
from h598_jframe import jinterval

WIDTH = 200
MASK = (1 << WIDTH) - 1
DIG4 = {0: 0, 1: 1, 2: 1, 3: 2, 4: -2, 5: -1, 6: -1, 7: 0}
WS = (6, 10, 14, 18)
TREES = ("T1", "T2", "T3", "T4", "T5", "T6")
QKIND = ("SC", "S", "C")


def csa(a, b, c):
    return (a ^ b ^ c) & MASK, \
        (((a & b) | (a & c) | (b & c)) << 1) & MASK


def c42(a, b, c, d):
    s1, c1 = csa(a, b, c)
    return csa(s1, c1, d)


def booth4_rows(mcand, y, w, hot_next):
    y2 = (y & ((1 << w) - 1)) << 1
    rows = []
    pend = 0
    for i in range(0, max(y2.bit_length(), 1), 2):
        d = DIG4[(y2 >> i) & 7]
        row = 0
        if d > 0:
            row = (d * mcand << i) & MASK
        elif d < 0:
            row = ((((~((-d) * mcand)) & MASK) << i) & MASK)
        if hot_next:
            row |= pend
            pend = (1 << i) if d < 0 else 0
        rows.append(row)
    return rows


def booth8_rows(mcand, y):
    # radix-8, digits -4..4, hard 3x multiple; full multiplier
    y2 = y << 1
    rows = []
    pend = 0
    for i in range(0, max(y2.bit_length(), 1), 3):
        v = (y2 >> i) & 15
        d = (v >> 1) + (v & 1) - (8 if v >= 8 else 0) \
            + ((v >> 3) & 1) * 0
        # canonical radix-8 recode: d = -(b3)*4 + b2*2 + b1 + b0
        b0 = v & 1
        b1 = (v >> 1) & 1
        b2 = (v >> 2) & 1
        b3 = (v >> 3) & 1
        d = b0 + b1 + 2 * b2 - 4 * b3
        row = 0
        if d > 0:
            row = (d * mcand << i) & MASK
        elif d < 0:
            row = ((((~((-d) * mcand)) & MASK) << i) & MASK)
        row |= pend
        pend = (1 << i) if d < 0 else 0
        rows.append(row)
    return rows


G_NAT = [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 10, 11],
         [12, 13, 14, 15]]
G_FB1 = [[14, 15, 0, 1], [2, 3, 4, 5], [6, 7, 8, 9],
         [10, 11, 12, 13]]


def slot16(rows, S, C, grouping, pairing):
    it = (rows + [0] * 14)[:14] + [S, C]
    gs = [c42(it[g[0]], it[g[1]], it[g[2]], it[g[3]])
          for g in grouping]
    (i1, i2), (i3, i4) = pairing
    l2a = c42(gs[i1][0], gs[i1][1], gs[i2][0], gs[i2][1])
    l2b = c42(gs[i3][0], gs[i3][1], gs[i4][0], gs[i4][1])
    return c42(l2a[0], l2a[1], l2b[0], l2b[1])


def tree_words(tree, f4v, rfv):
    if tree == "T4":
        rows = booth8_rows(f4v, rfv)
        S = C = 0
        for r in rows:
            S, C = csa(S, C, r)
        return S, C, 0
    role_rf = tree == "T3"
    mcand, mplier = (rfv, f4v) if role_rf else (f4v, rfv)
    hot_next = tree != "T2"
    nb = mplier.bit_length()
    S = C = 0
    col0 = 0
    pos = 0
    while pos < nb:
        rows = booth4_rows(mcand, mplier >> pos, 27, hot_next)
        if tree == "T5":
            for r in rows:
                S, C = csa(S, C, r)
        elif tree == "T6":
            s1 = c1 = s2 = c2 = 0
            for r in rows[0::2]:
                s1, c1 = csa(s1, c1, r)
            for r in rows[1::2]:
                s2, c2 = csa(s2, c2, r)
            s, c = c42(s1, c1, s2, c2)
            S, C = c42(s, c, S, C)
        elif tree == "T2":
            S, C = slot16(rows, S, C, G_FB1,
                          ((0, 1), (2, 3)))
        else:
            S, C = slot16(rows, S, C, G_NAT,
                          ((0, 3), (1, 2)))
        pos += 27
        if pos < nb:
            S >>= 27
            C >>= 27
            col0 += 27
    return S, C, col0


def row_feats(args):
    m, key, theta, hw = args
    mag = (0, E2M, m)
    sq = mul_round(mag, mag, 67, "chop")
    f4 = mul_round(sq, sq, 67, "chop")
    neg = build_chain(f4, C6_5, C6_3, C6_1, 67, 64, "rn",
                      False, False, False)
    pos = build_chain(f4, C6_6, C6_4, C6_2, 67, 64, "rn",
                      False, False, False)
    B_full = f4[2] * pos[2]
    rsh = B_full.bit_length() - 67
    left = mul_round(sq, neg, 67, "chop")
    right = mul_round(f4, pos, 67, "chop")
    low3 = sq[2] & 7
    dist = abs(left[1] - right[1])
    payload = low3 + 8 - dist
    scale = min(left[1], right[1], left[1] - 8)
    A = left[2] << (left[1] - scale)
    P = payload << (left[1] - 8 - scale)
    M = A + P - (right[2] << (right[1] - scale))
    k = M.bit_length() - 67
    ce = scale + k
    bshift = right[1] - scale
    F = rsh - bshift
    kf = k + F
    APf = (A + P) << F
    EU = (APf - B_full) >> kf
    Vlow = (APf - B_full) - (EU << kf)
    ivs = []
    for z in (-2, -1, 0, 1, 2):
        refs = [final_cosine_result(-(EU + z), ce, md)
                for md in ROUNDING_MODES]
        if refs == hw:
            lo, hi = jinterval(Vlow, kf, pos[2], z)
            if lo <= hi:
                ivs.append((lo, hi))
    if not ivs:
        return None
    jlo = min(l for l, h in ivs)
    jhi = max(h for l, h in ivs)
    half = (m * 2654435761 >> 16) & 1
    qs = {}
    for tree in TREES:
        S, C, col0 = tree_words(tree, f4[2], pos[2])
        bb = rsh - col0  # boundary bit index in tree frame
        for kind, word in (("SC", S + C), ("S", S), ("C", C)):
            for w in WS:
                sh = bb + 1 - w
                if sh < 0:
                    sh = 0
                qs[(tree, kind, w)] = (word >> sh) & \
                    ((1 << (w + 2)) - 1)
    return (key, half, jlo, jhi, qs)


def main():
    maxrows = int(sys.argv[1]) if len(sys.argv) > 1 else 80000
    rows = []
    locked = json.load(open("h616_locked.json"))
    st6 = {md: open(f"h616_{md}_status.txt").read()
           .splitlines() for md in ROUNDING_MODES}
    for i, rec in enumerate(locked):
        hw = [int(st6[md][i].split()[2], 16)
              for md in ROUNDING_MODES]
        rows.append((int(rec["m"], 16), tuple(rec["key"]),
                     rec["theta"], hw))
    recs = json.load(open("h619_rows.json"))
    st9 = {md: open(f"h619_{md}_status.txt").read()
           .splitlines() for md in ROUNDING_MODES}
    for i, rec in enumerate(recs):
        t = [st9[md][i].split() for md in ROUNDING_MODES]
        if any(x[0] != "OK" for x in t):
            continue
        rows.append((int(rec["m"], 16), tuple(rec["key"]),
                     rec["theta"], [int(x[2], 16) for x in t]))
    # stratified subsample
    per = defaultdict(int)
    sel = []
    for r in sorted(rows, key=lambda r: (r[0] * 2654435761)
                    & 0xFFFFFFFF):
        cell = (r[1], r[2])
        cap = maxrows // 300
        if per[cell] >= cap:
            continue
        per[cell] += 1
        sel.append(r)
        if len(sel) >= maxrows:
            break
    print(f"rows: {len(sel)} of {len(rows)}", flush=True)
    with Pool(14) as pool:
        fs = pool.map(row_feats, sel, chunksize=100)
    fs = [f for f in fs if f is not None]
    print(f"usable: {len(fs)}", flush=True)
    # baseline: const-j per stratum-side
    tr_j = defaultdict(lambda: defaultdict(int))
    for key, half, jlo, jhi, qs in fs:
        if half == 0:
            for j in range(jlo, jhi + 1):
                tr_j[key][j] += 1
    bstj = {k: max(v, key=v.get) for k, v in tr_j.items()}
    ok = n = 0
    for key, half, jlo, jhi, qs in fs:
        if half == 1:
            n += 1
            ok += jlo <= bstj.get(key, 0) <= jhi
    print(f"baseline const-j/stratum held-out: "
          f"{ok / max(n, 1):.4f} (n={n})", flush=True)
    # readout fits
    results = []
    for tree in TREES:
        for kind in QKIND:
            for w in WS:
                qk = (tree, kind, w)
                a0 = 3.0 / (8.0 * (1 << (w - 6)))
                best = (-1, None)
                for mult in (0.0, 0.25, 0.5, 0.75, 1.0, 1.25,
                             1.5, 2.0, 3.0, -0.25, -0.5, -0.75,
                             -1.0, -1.25, -1.5, -2.0, -3.0):
                    alpha = a0 * mult
                    # per-stratum beta by stabbing on train
                    ev = defaultdict(list)
                    for key, half, jlo, jhi, qs in fs:
                        if half:
                            continue
                        x = alpha * qs[qk]
                        ev[key].append((jlo - 0.5 - x, 1))
                        ev[key].append((jhi + 0.5 - x, -1))
                    betas = {}
                    for key, e in ev.items():
                        e.sort()
                        cur, bc, bb = 0, -1, 0.0
                        for p, d in e:
                            cur += d
                            if cur > bc:
                                bc, bb = cur, p + 1e-9
                        betas[key] = bb
                    ok2 = n2 = 0
                    for key, half, jlo, jhi, qs in fs:
                        if not half:
                            continue
                        n2 += 1
                        j = round(alpha * qs[qk] +
                                  betas.get(key, 0))
                        ok2 += jlo <= j <= jhi
                    acc = ok2 / max(n2, 1)
                    if acc > best[0]:
                        best = (acc, mult)
                results.append((best[0], tree, kind, w,
                                best[1]))
                print(f"  {tree}/{kind}/w={w}: held-out "
                      f"{best[0]:.4f} (alpha mult {best[1]})",
                      flush=True)
    results.sort(reverse=True)
    print("\nTOP 10:")
    for acc, tree, kind, w, mult in results[:10]:
        print(f"  {acc:.4f}  {tree}/{kind}/w={w} "
              f"alpha={mult}*lattice")


if __name__ == "__main__":
    main()
