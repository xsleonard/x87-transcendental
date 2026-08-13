#!/usr/bin/env python3
"""h629: re-diagnose the 248 rows seeding from the SQUARE.

Hypothesis: recover_m returns a pattern-consistent operand
whose value is sqrt(2) off (square patterns are x2-invariant);
the chains then see f4 at 4x the wrong scale.  Seed the
replica at the square level instead: sq = (0, esq, mul) for
BOTH e2 parities, f4/chains follow, no operand needed.
Validate against traced f4/lf/rf; report parity census.
"""
from collections import defaultdict
from h437_gate_extraction import load_labeled_rows
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5,
                                 C6_6, build_chain, mul_round,
                                 recover_m)

rows = load_labeled_rows()
cens = defaultdict(int)
for fields, hw in rows:
    if fields.get("active") != "1" or fields["lsign"] != "1" \
            or fields["rsign"] != "0":
        continue
    le2, re2 = int(fields["le2"]), int(fields["re2"])
    ls, rs = int(fields["ls"], 16), int(fields["rs"], 16)
    dist, low3 = int(fields["dist"]), int(fields["low3"])
    prepay = low3 + 8 - dist
    scale = min(le2, re2, le2 - 8)
    M = (ls << (le2 - scale)) - (rs << (re2 - scale)) \
        + (prepay << (le2 - 8 - scale))
    if M <= 0:
        continue
    k = max(M.bit_length() - 67, 0)
    if k < 3:
        continue
    disc = M & ((1 << k) - 1)
    if disc > 2 and disc < (1 << k) - 2:
        continue
    mul = int(fields["mul"], 16)
    # old recipe check (is it one of the 248?)
    m = recover_m(mul)
    ispoly = False
    if m is not None:
        mm = m
        while mm.bit_length() > 64:
            mm >>= 1
        while 0 < mm.bit_length() < 64:
            mm <<= 1
        mag = (0, -66, mm)
        sq0 = mul_round(mag, mag, 67, "chop")
        f40 = mul_round(sq0, sq0, 67, "chop")
        neg0 = build_chain(f40, C6_5, C6_3, C6_1, 67, 64,
                           "rn", False, False, False)
        if f40[2] == int(fields["f4"], 16) and \
                neg0[2] == int(fields["lf"], 16):
            ispoly = True
    if ispoly:
        continue
    # square-seeded: try both parities across a range
    hit = None
    for esq in range(-140, -120):
        sq = (0, esq, mul)
        f4 = mul_round(sq, sq, 67, "chop")
        if f4[2] != int(fields["f4"], 16):
            continue
        neg = build_chain(f4, C6_5, C6_3, C6_1, 67, 64, "rn",
                          False, False, False)
        pos = build_chain(f4, C6_6, C6_4, C6_2, 67, 64, "rn",
                          False, False, False)
        if neg[2] == int(fields["lf"], 16) and \
                pos[2] == int(fields["rf"], 16):
            hit = esq
            break
    if hit is None:
        cens["UNFIXED"] += 1
    else:
        cens[("FIXED", "esq_parity", hit & 1)] += 1
        cens[("FIXED_esq", hit)] += 1
print(dict(sorted(cens.items(), key=str)))
