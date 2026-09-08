#!/usr/bin/env python3
"""h528: structural model harness — redundant-consumption terminal.

HYPOTHESIS CLASS: the right product B = f4*rf reaches the terminal
subtract as an UNRESOLVED carry-save pair (S, C) from the multiplier's
reduction array; the terminal truncates S and C SEPARATELY at column
`co` (instead of resolving then chopping), losing/gaining the
inter-word carry of the dropped fields.  The fire (R-1) is that lost
unit propagating into the retained field at ties.

Config axes:
  recode:  booth2 (radix-4, negative PPs as complement + LSB
           correction bit in-array) | nobooth (radix-2 AND rows)
  mult:    which operand is recoded: pos (64b) | f4 (67b)
  topo:    seq_asc | seq_desc | tree3 | evenodd  (3:2 CSA orders)
  off:     truncation column co = rsh + off, off in {0,2,4,6,8}
  corr:    dropped-field compensation: none | plus1 (assume carry 1)

Prediction per tie row: B_hw = (S>>co + C>>co + corr) << co ... then
hw_M = A + P - B_hw at scanner alignment; fire_pred = (hw_M >> k) ==
R - 1.  Scored against sampled labeled comb ties (both windows).
A real mechanism must get BOTH classes right (>95/95); survivors go
to boundary-geometry reproduction.
"""
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)

E2M = -66


def booth2_pps(x, y, width):
    """radix-4 Booth PPs of x*y, y recoded; hardware-style: negative
    digits as one's complement + correction bit at the PP's LSB
    column; sign handled by two's complement within `width` bits."""
    mask = (1 << width) - 1
    pps = []
    y2 = y << 1
    nbits = y.bit_length() + 2
    for i in range(0, nbits, 2):
        trip = (y2 >> i) & 7
        d = {0: 0, 1: 1, 2: 1, 3: 2, 4: -2, 5: -1, 6: -1, 7: 0}[trip]
        if d == 0:
            pp = 0
        elif d > 0:
            pp = (x * d) << i
        else:
            pp = ((~(x * -d)) & mask) << i & mask
            pp = (pp | 0) & mask
            pp += 1 << i                    # correction bit in-array
        pps.append(pp & mask)
    return pps


def radix2_pps(x, y, width):
    mask = (1 << width) - 1
    return [((x << i) & mask) for i in range(y.bit_length())
            if (y >> i) & 1]


def csa(a, b, c, mask):
    s = a ^ b ^ c
    cy = ((a & b) | (a & c) | (b & c)) << 1
    return s & mask, cy & mask


def reduce_pps(pps, topo, mask):
    pps = [p for p in pps if p] or [0]
    if topo == "seq_desc":
        pps = pps[::-1]
    if topo in ("seq_asc", "seq_desc"):
        S, C = pps[0], 0
        for p in pps[1:]:
            S, C = csa(S, C, p, mask)
        return S, C
    if topo == "evenodd":
        Se, Ce = pps[0], 0
        for p in pps[2::2]:
            Se, Ce = csa(Se, Ce, p, mask)
        if len(pps) > 1:
            So, Co = pps[1], 0
            for p in pps[3::2]:
                So, Co = csa(So, Co, p, mask)
            S, C = csa(Se, Ce, So, mask)
            S, C2 = csa(S, C, Co, mask)
            return S, C2
        return Se, Ce
    # tree3: repeatedly compress groups of 3
    lvl = pps
    while len(lvl) > 2:
        nxt = []
        for i in range(0, len(lvl) - 2, 3):
            s, c = csa(lvl[i], lvl[i + 1], lvl[i + 2], mask)
            nxt.append(s)
            nxt.append(c)
        nxt.extend(lvl[len(lvl) - len(lvl) % 3:])
        lvl = nxt
    return (lvl + [0])[:2]


CONFIGS = []
for recode in ("booth2", "nobooth"):
    for mult in ("pos", "f4"):
        for topo in ("seq_asc", "seq_desc", "tree3", "evenodd"):
            for off in (0, 2, 4, 6, 8):
                for corr in (0, 1):
                    CONFIGS.append((recode, mult, topo, off, corr))


def row_features(mhex):
    m = int(mhex, 16)
    mag = (0, E2M, m)
    sq = mul_round(mag, mag, 67, "chop")
    f4 = mul_round(sq, sq, 67, "chop")
    neg = build_chain(f4, C6_5, C6_3, C6_1, 67, 64, "rn",
                      False, False, False)
    pos = build_chain(f4, C6_6, C6_4, C6_2, 67, 64, "rn",
                      False, False, False)
    left = mul_round(sq, neg, 67, "chop")
    right = mul_round(f4, pos, 67, "chop")
    low3 = sq[2] & 7
    dist = abs(left[1] - right[1])
    payload = low3 + 8 - dist
    scale = min(left[1], right[1], left[1] - 8)
    A = left[2] << (left[1] - scale)
    P = payload << (left[1] - 8 - scale)
    Bres = right[2] << (right[1] - scale)
    M = A + P - Bres
    k = M.bit_length() - 67
    R = M >> k
    B_full = f4[2] * pos[2]
    rsh = B_full.bit_length() - 67
    return (f4[2], pos[2], B_full, rsh, A, P, M, k, R,
            right[1] - scale, dist, low3)


def score_chunk(args):
    rows, configs = args
    width = 140
    mask = (1 << width) - 1
    res = {cfg: [0, 0, 0, 0] for cfg in configs}   # cc cf fc ff
    for mhex, fire in rows:
        (f4s, poss, B_full, rsh, A, P, M, k, R, bshift,
         dist, low3) = row_features(mhex)
        pp_cache = {}
        for cfg in configs:
            recode, mult, topo, off, corr = cfg
            key = (recode, mult, topo)
            if key not in pp_cache:
                x, y = ((poss, f4s) if mult == "f4"
                        else (f4s, poss))
                pps = (booth2_pps(x, y, width) if recode == "booth2"
                       else radix2_pps(x, y, width))
                pp_cache[key] = reduce_pps(pps, topo, mask)
            S, C = pp_cache[key]
            co = rsh + off
            if co <= 0:
                continue
            B_hw67 = (S >> co) + (C >> co) + corr
            # bring to the resolved-chop column rsh
            B_hw = B_hw67 >> (rsh - co) if co < rsh \
                else B_hw67 << (co - rsh)
            hw_M = A + P - (B_hw << bshift)
            v = hw_M >> k
            p = 0 if v == R else (1 if v == R - 1 else -1)
            if fire:
                res[cfg][3 if p == 1 else 2] += 1
            else:
                res[cfg][0 if p == 0 else 1] += 1
    return res


def main():
    # sample labeled ties from combs 1 and 3
    samples = []
    for ties, statpre, stride in (("ties_comb.txt", "comb", 250),
                                  ("ties_comb3.txt", "comb3", 600)):
        rows = []
        seen = set()
        for line in open(ties):
            f = line.split()
            if f[0] in seen:
                continue
            seen.add(f[0])
            rows.append(f)
        inputs = sorted(f[0] for f in rows)
        order = {m: i for i, m in enumerate(inputs)}
        st = {md: open(f"{statpre}_{md}_status.txt").read()
              .splitlines() for md in ROUNDING_MODES}
        for j, f in enumerate(rows):
            if j % stride:
                continue
            R, ce, i = int(f[7], 16), int(f[8]), order[f[0]]
            hw, bad = [], False
            for md in ROUNDING_MODES:
                t = st[md][i].split()
                if t[0] != "OK":
                    bad = True
                    break
                hw.append(int(t[2], 16))
            if bad:
                continue
            clean = [final_cosine_result(-R, ce, md)
                     for md in ROUNDING_MODES]
            fired = [final_cosine_result(-(R - 1), ce, md)
                     for md in ROUNDING_MODES]
            if hw == clean:
                samples.append((f[0], 0))
            elif hw == fired:
                samples.append((f[0], 1))
    n1 = sum(s[1] for s in samples)
    print(f"sampled {len(samples)} labeled ties ({n1} fires)")
    chunks = [samples[i::8] for i in range(8)]
    with Pool(8) as pool:
        parts = pool.map(score_chunk,
                         [(ch, CONFIGS) for ch in chunks])
    agg = {cfg: [0, 0, 0, 0] for cfg in CONFIGS}
    for part in parts:
        for cfg, v in part.items():
            for i in range(4):
                agg[cfg][i] += v[i]
    scored = []
    for cfg, (cc, cf, fc, ff) in agg.items():
        ncl, nfi = cc + cf, fc + ff
        if ncl == 0 or nfi == 0:
            continue
        clean_acc = cc / ncl
        fire_acc = ff / nfi
        scored.append((min(clean_acc, fire_acc), clean_acc,
                       fire_acc, cfg))
    scored.sort(reverse=True)
    print(f"\n{'config':44s} {'clean_acc':>9s} {'fire_acc':>8s}")
    for minacc, ca, fa, cfg in scored[:25]:
        print(f"{str(cfg):44s} {ca:9.4f} {fa:8.4f}")
    print("\nbaseline (never-fire): clean 1.000 fire 0.000")


if __name__ == "__main__":
    main()
