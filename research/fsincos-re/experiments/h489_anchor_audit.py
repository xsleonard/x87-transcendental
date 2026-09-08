#!/usr/bin/env python3
"""h489: alignment-convention audit — the 'no gate at all' hypothesis.

If the hardware accumulator is FIXED-POINT (LSB at an absolute weight
E0) rather than value-normalized, rows whose magnitude sits high lose
extra low bits: retained = M >> p with p = max(k, E0 - scale), and the
observed 'fires' are ordinary truncation (R - (R mod 2^(p-k))),
which the architectural rounding maps to the same results we label
R-1 (and the R-2-ambiguous cases h478 exposed).  Anchor families:
  A: p = E0 - scale          (absolute weight; varies within cells)
  B: p = re2 - scale + c     (right-operand LSB anchored)
  C: p = k + c               (uniform widening; control)
For each anchor, predict hardware exactly on all 1,310 labeled rows
(prediction: truncate at p, then architectural rounding) and count
exact matches.  A perfect anchor => the borrow-bit was a coordinate
artifact.  Run from /tmp/stageA.
"""
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)
from h484_cegis import load_labels
E2M = -66

def build_row(item):
    mhex, o = item
    if o == 2:
        return None
    m = int(mhex, 16)
    mag = (0, E2M, m)
    square = mul_round(mag, mag, 67, "chop")
    fourth = mul_round(square, square, 67, "chop")
    negative = build_chain(fourth, C6_5, C6_3, C6_1, 67, 64, "rn",
                           False, False, False)
    positive = build_chain(fourth, C6_6, C6_4, C6_2, 67, 64, "rn",
                           False, False, False)
    left = mul_round(square, negative, 67, "chop")
    right = mul_round(fourth, positive, 67, "chop")
    low3 = square[2] & 7
    dist = abs(left[1] - right[1])
    payload = low3 + 8 - dist
    scale = min(left[1], right[1])
    if payload and left[1] - 8 < scale:
        scale = left[1] - 8
    M = (left[2] << (left[1]-scale)) + (payload << (left[1]-8-scale)) \
        - (right[2] << (right[1]-scale))
    k = M.bit_length() - 67
    return (o, M, k, scale, left[1], right[1])

def main():
    rows = load_labels()
    with Pool(8) as pool:
        data = [r for r in pool.map(build_row, sorted(rows.items()),
                                    chunksize=50) if r]
    n = len(data)
    fires = sum(d[0] for d in data)
    print(f"rows: {n}, fires: {fires} (never-fire model matches "
          f"{n - fires})")
    # observed hardware value: R if clean else R-1 (tie rows)
    # prediction under anchor: truncate M at p, compare architectural
    # results in all modes with hardware's (R or R-1 outcome).

    def arch(corr_mag, corr_e):
        return tuple(final_cosine_result(-corr_mag, corr_e, mode)
                     for mode in ROUNDING_MODES)

    def matches(o, M, k, scale, p):
        p = max(p, k)
        pred = arch(M >> p, scale + p)
        R = M >> k
        actual = arch(R - 1, scale + k) if o else arch(R, scale + k)
        return pred == actual

    print("\n--- family A: p = E0 - scale (absolute anchor) ---")
    scales = sorted({scale + k for _, M, k, scale, _, _ in data})
    lo, hi = scales[0] - 3, scales[-1] + 3
    for E0 in range(lo, hi + 1):
        good = sum(1 for o, M, k, scale, le2, re2 in data
                   if matches(o, M, k, scale, E0 - scale))
        if good > n - fires:
            print(f"  E0={E0}: exact-match {good}/{n}  <-- beats "
                  f"never-fire")
        elif E0 % 4 == 0:
            print(f"  E0={E0}: exact-match {good}/{n}")

    print("\n--- family B: p = (re2 - scale) + c ---")
    for c in range(6, 14):
        good = sum(1 for o, M, k, scale, le2, re2 in data
                   if matches(o, M, k, scale, re2 - scale + c))
        mark = "  <-- beats never-fire" if good > n - fires else ""
        print(f"  c={c}: exact-match {good}/{n}{mark}")

    print("\n--- family C: p = k + c (uniform; control) ---")
    for c in range(0, 4):
        good = sum(1 for o, M, k, scale, le2, re2 in data
                   if matches(o, M, k, scale, k + c))
        print(f"  c={c}: exact-match {good}/{n}")

if __name__ == "__main__":
    main()
