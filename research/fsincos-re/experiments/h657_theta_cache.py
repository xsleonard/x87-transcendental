#!/usr/bin/env python3
"""h657: theta!=0 row caches for the theta-ladder campaign.

comb7 + comb8 theta!=0 rows, THREE-WAY labels (R-1 fire_dn / R clean /
R+1 fire_up — the up-fires live at theta<0 and were invisible to the
two-way labeler).  Stores exact integers needed for the derivative-
correction test: M, sqlow, xd60, sR.

Cache: h657_<corpus>.pkl rows =
  (theta, dist, s4, side, L, xd60, sR, label, M, sqlow)
  label: 0 clean, 1 fire_dn (R-1), 2 fire_up (R+1)
"""
import os, pickle, sys
from multiprocessing import Pool

sys.path.insert(0, "/Users/steve/llm/x87-transcendental/fsincos-re/experiments")
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)

E2M = -66
PIV = 0.70710678118654752


def load3(ties, prefix):
    rows, seen = [], set()
    for lineS in open(ties):
        f = lineS.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        rows.append(f)
    inputs = sorted(f[0] for f in rows)
    order = {mm: i for i, mm in enumerate(inputs)}
    st = {md: open(f"{prefix}_{md}_status.txt").read().splitlines()
          for md in ROUNDING_MODES}
    out = []
    nother = 0
    for f in rows:
        theta = int(f[9])
        if theta == 0:
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
        clean = [final_cosine_result(-R, ce, md) for md in ROUNDING_MODES]
        dn = [final_cosine_result(-(R - 1), ce, md) for md in ROUNDING_MODES]
        up = [final_cosine_result(-(R + 1), ce, md) for md in ROUNDING_MODES]
        if hw == clean:
            out.append((f[0], 0, theta))
        elif hw == dn:
            out.append((f[0], 1, theta))
        elif hw == up:
            out.append((f[0], 2, theta))
        else:
            nother += 1
    print(f"  {prefix}: {len(out)} labeled theta!=0, {nother} OTHER",
          flush=True)
    return out


def internals(args):
    mhex, label, theta = args
    m = int(mhex, 16)
    mag = (0, E2M, m)
    square = mul_round(mag, mag, 67, "chop")
    fourth = mul_round(square, square, 67, "chop")
    neg = build_chain(fourth, C6_5, C6_3, C6_1, 67, 64, "rn", False, False, False)
    pos = build_chain(fourth, C6_6, C6_4, C6_2, 67, 64, "rn", False, False, False)
    left = mul_round(square, neg, 67, "chop")
    right = mul_round(fourth, pos, 67, "chop")
    dist = abs(left[1] - right[1])
    sq = square[2]
    f4 = sq * sq
    s4 = f4.bit_length() - 67
    t4 = f4 & ((1 << s4) - 1)
    sqlow = sq - (1 << 66)
    M = (sq & 7) * sqlow - t4
    rprod = fourth[2] * pos[2]
    sR = rprod.bit_length() - 67
    rdisc = rprod & ((1 << sR) - 1)
    xd60 = (rdisc << 60) >> sR
    side = 0 if m / 2**64 < PIV else 1
    return (theta, dist, s4, side, sq & 7, xd60, sR, label, M, sqlow)


def main():
    for name in ("comb7", "comb8"):
        cache = f"h657_{name}.pkl"
        if os.path.exists(cache):
            print(f"{cache} exists")
            continue
        lab = load3(f"ties_{name}.txt", name)
        with Pool(8) as pool:
            rows = pool.map(internals, lab, chunksize=1000)
        pickle.dump(rows, open(cache, "wb"))
        print(f"{name}: {len(rows)} cached", flush=True)


if __name__ == "__main__":
    main()
