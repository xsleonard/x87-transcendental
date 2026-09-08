#!/usr/bin/env python3
"""h627a: target census for the table-path campaign — strata
of the 248 table rows, the 7 base-miss rows in detail, and
the input values (needed to design the scan ranges)."""
from collections import defaultdict
from h437_gate_extraction import (ROUNDING_MODES, load_labeled_rows,
                                  final_cosine_result)
from h453_chain_variants import mul_round, recover_m, \
    build_chain, C6_1, C6_3, C6_5

rows = load_labeled_rows()
cens = defaultdict(int)
print("the 7 base-miss rows (+2 off-frame):")
for fields, hw_sigs in rows:
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
    m = recover_m(mul)
    ispoly = False
    if m is not None:
        while m.bit_length() > 64:
            m >>= 1
        while 0 < m.bit_length() < 64:
            m <<= 1
        mag = (0, -66, m)
        sq = mul_round(mag, mag, 67, "chop")
        f4r = mul_round(sq, sq, 67, "chop")
        neg = build_chain(f4r, C6_5, C6_3, C6_1, 67, 64, "rn",
                          False, False, False)
        if f4r[2] == int(fields["f4"], 16) and \
                neg[2] == int(fields["lf"], 16):
            ispoly = True
    if ispoly:
        continue
    theta = disc if disc <= 2 else disc - (1 << k)
    ce = scale + k
    R = M >> k
    hw = [hw_sigs[md] for md in ROUNDING_MODES]
    base_ok = hw == [final_cosine_result(-R, ce, md)
                     for md in ROUNDING_MODES]
    cens[(dist, low3, ce, theta, base_ok)] += 1
    if not base_ok:
        print(f"  d={dist} l3={low3} ce={ce} th={theta} "
              f"le2={le2} mul={mul:x} lf={fields['lf']} "
              f"rf={fields['rf']}")
print("\nstrata census (dist, low3, ce, theta, base_ok):")
for kk in sorted(cens, key=str):
    print(f"  {kk}: {cens[kk]}")
