#!/usr/bin/env python3
"""h449: is the payload an alias of the products' true discarded bits?

h448's delta gradient (P(delta>=0) monotone-decreasing in prepay)
suggests hardware compares a real correction quantity against the chop
boundary, and prepay = low3+8-dist only approximates it.  The physical
candidate: the correction IS the discarded low bits of the two terminal
products.  h447's g=full variant kept the payload term and failed —
that double-counts the correction if payload approximates it.

Variants tested over every labeled row, all three modes:
  V1: full-width products, NO payload term at all.
  V2: full-width products, payload term replaced by its two ported
      collision patches' pre-images... (skipped; V1 covers the idea)
  V3: chopped products + payload = floor of the exact correction
      (a - b) expressed in 2^(le2-8) units, computed from the traced
      operands; V4: same with round-to-nearest; V5: ceil.
  V6: chopped products + payload = floor(a-units) only (left product's
      discarded field alone), V7: round.

Run from /tmp/stageA.
"""
from collections import Counter
from multiprocessing import Pool

from h437_gate_extraction import (
    ROUNDING_MODES, load_labeled_rows, chop_to_67_bits, final_cosine_result)

VARIANTS = ["V1_full_nopay", "V3_corr_floor", "V4_corr_round",
            "V5_corr_ceil", "V6_left_floor", "V7_left_round",
            "V0_baseline"]


def analyze_row(row):
    fields, hw_results = row
    payload = int(fields["payload"])
    left_e2, right_e2 = int(fields["le2"]), int(fields["re2"])
    left_sign, right_sign = int(fields["lsign"]), int(fields["rsign"])
    square, odd_chain = int(fields["mul"], 16), int(fields["lf"], 16)
    fourth, even_chain = int(fields["f4"], 16), int(fields["rf"], 16)

    full_L = square * odd_chain
    full_R = fourth * even_chain
    shift_L = max(full_L.bit_length() - 67, 0)
    shift_R = max(full_R.bit_length() - 67, 0)
    ls, rs = full_L >> shift_L, full_R >> shift_R
    a_disc = full_L & ((1 << shift_L) - 1)      # left discarded, units 2^(le2-shift_L)
    b_disc = full_R & ((1 << shift_R) - 1)

    def check(acc, scale):
        corr, corr_e = chop_to_67_bits(acc, scale)
        return all(final_cosine_result(corr, corr_e, m) == hw_results[m]
                   for m in ROUNDING_MODES)

    def acc_of(ls_v, rs_v, e_l, e_r, pay, pay_e):
        scale = min(e_l, e_r)
        if pay:
            scale = min(scale, pay_e)
        acc = (-1 if left_sign else 1) * (ls_v << (e_l - scale)) \
            + (-1 if right_sign else 1) * (rs_v << (e_r - scale))
        if pay:
            acc += (-1 if left_sign else 1) * (pay << (pay_e - scale))
        return acc, scale

    bad = []

    # V0: baseline model (chopped + traced payload)
    acc, scale = acc_of(int(fields["ls"], 16), int(fields["rs"], 16),
                        left_e2, right_e2, payload, left_e2 - 8)
    if not check(acc, scale):
        bad.append("V0_baseline")

    # V1: full products, no payload
    acc, scale = acc_of(full_L, full_R, left_e2 - shift_L,
                        right_e2 - shift_R, 0, 0)
    if not check(acc, scale):
        bad.append("V1_full_nopay")

    # exact correction in payload units 2^(le2-8):
    #   a_disc has units 2^(le2 - shift_L)  -> a_disc / 2^(shift_L - 8)
    #   b_disc has units 2^(re2 - shift_R)  -> b_disc / 2^(shift_R - 8 + dist)
    # signs: |acc| = (A + a) - (B + b) + 0 ; payload enters |acc| as +P
    # (left_sign=1 convention), so P_true = a - b in those units.
    num_shift_a = shift_L - 8
    num_shift_b = shift_R - 8 + (left_e2 - right_e2)
    # common denominator 2^D
    D = max(num_shift_a, num_shift_b, 0)
    num = (a_disc << (D - num_shift_a)) - (b_disc << (D - num_shift_b))
    for name, rounder in (("V3_corr_floor", 0), ("V4_corr_round", 1),
                          ("V5_corr_ceil", 2)):
        if rounder == 0:
            pay = num >> D
        elif rounder == 1:
            pay = (num + (1 << (D - 1))) >> D
        else:
            pay = -((-num) >> D)
        acc, scale = acc_of(ls, rs, left_e2, right_e2, pay, left_e2 - 8)
        if not check(acc, scale):
            bad.append(name)

    numL = a_disc
    DL = max(num_shift_a, 0)
    for name, rounder in (("V6_left_floor", 0), ("V7_left_round", 1)):
        pay = (numL >> DL) if rounder == 0 else (numL + (1 << (DL - 1))) >> DL
        acc, scale = acc_of(ls, rs, left_e2, right_e2, pay, left_e2 - 8)
        if not check(acc, scale):
            bad.append(name)

    return tuple(bad)


def main():
    rows = load_labeled_rows()
    with Pool(8) as pool:
        results = pool.map(analyze_row, rows, chunksize=1000)
    counts = Counter()
    for bad in results:
        for name in bad:
            counts[name] += 1
    print(f"rows: {len(results)}")
    for name in VARIANTS:
        n = counts.get(name, 0)
        tag = "  <== EXACT" if n == 0 else ""
        print(f"  {name:15s}: {n:6d} mismatching rows{tag}")


if __name__ == "__main__":
    main()
