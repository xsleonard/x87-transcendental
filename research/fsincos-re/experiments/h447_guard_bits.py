#!/usr/bin/env python3
"""h447: do the terminal products carry guard bits into the accumulator?

h446 reduced the collision gate to one borrow bit whose fires sit only
where the model's accumulator value lands within ~2 payload units of a
chop-67 retention boundary — exactly where extra low-order product bits
would tip the retained value.  Full-width products are excluded (they
would perturb ~half of all rows, but the chopped model is exact on
671k observations).  A SMALL number of guard bits g on each terminal
product perturbs the accumulator by < 2^(8-g) payload units and acts
only at near-ties — matching the observed fire rate at g ~ 4.

Sweep g = 0..14 plus FULL: recompute both terminal products from the
traced operands (mul*lf, f4*rf), chop each to 67+g bits, rebuild the
accumulator (payload term unchanged), chop to 67, apply the
architectural three-mode rounding, and count rows where the result
differs from the hardware capture in ANY mode.  A g with ZERO
mismatches over all rows is the collision-gate answer.

Run from /tmp/stageA.
"""
from collections import Counter
from multiprocessing import Pool

from h437_gate_extraction import (
    ROUNDING_MODES, load_labeled_rows, chop_to_67_bits, final_cosine_result)

G_VALUES = list(range(0, 15)) + ["full"]


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

    bad = []
    for g in G_VALUES:
        gl = shift_L if g == "full" else min(g, shift_L)
        gr = shift_R if g == "full" else min(g, shift_R)
        keep_L, e_L = full_L >> (shift_L - gl), left_e2 - gl
        keep_R, e_R = full_R >> (shift_R - gr), right_e2 - gr
        scale = min(e_L, e_R)
        if payload:
            scale = min(scale, left_e2 - 8)
        acc = (-1 if left_sign else 1) * (keep_L << (e_L - scale)) \
            + (-1 if right_sign else 1) * (keep_R << (e_R - scale))
        if payload:
            acc += (-1 if left_sign else 1) * (payload << (left_e2 - 8 - scale))
        corr, corr_e = chop_to_67_bits(acc, scale)
        if not all(final_cosine_result(corr, corr_e, m) == hw_results[m]
                   for m in ROUNDING_MODES):
            bad.append(g)
    return tuple(bad)


def main():
    rows = load_labeled_rows()
    with Pool(8) as pool:
        results = pool.map(analyze_row, rows, chunksize=1000)
    counts = Counter()
    for bad in results:
        for g in bad:
            counts[g] += 1
    print(f"rows: {len(results)}")
    for g in G_VALUES:
        n = counts.get(g, 0)
        tag = "  <== EXACT" if n == 0 else ""
        print(f"  g={g!s:>4}: {n:6d} mismatching rows{tag}")


if __name__ == "__main__":
    main()
