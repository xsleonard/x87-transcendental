#!/usr/bin/env python3
"""h626c: the 248 rows are TABLE-PATH rows (h626b: chain fields
are interval constants).  Test the borrow frame on the table
producer's own terminal: B_full = f4_field * rf_field from the
trace; validate rs == chop67(B_full); EU-anchored census.
"""
from collections import defaultdict
from h437_gate_extraction import (ROUNDING_MODES, load_labeled_rows,
                                  final_cosine_result)
from h453_chain_variants import mul_round, recover_m
from h453_chain_variants import build_chain, C6_1, C6_3, C6_5, \
    C6_2, C6_4, C6_6

rows = load_labeled_rows()
cens = defaultdict(int)
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
    # replica check: is this a poly row?
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
    # table-frame test
    f4v = int(fields["f4"], 16)
    rfv = int(fields["rf"], 16)
    B_full = f4v * rfv
    rsh = B_full.bit_length() - 67
    chop_ok = (B_full >> rsh) == rs
    cens[("chop_ok", chop_ok)] += 1
    if not chop_ok:
        continue
    bshift = re2 - scale
    F = rsh - bshift
    if F < 0:
        cens["noF"] += 1
        continue
    kf = k + F
    A = ls << (le2 - scale)
    P = prepay << (le2 - 8 - scale)
    APf = (A + P) << F
    EU = (APf - B_full) >> kf
    Vlow = (APf - B_full) - (EU << kf)
    ce = scale + k
    hw = [hw_sigs[md] for md in ROUNDING_MODES]
    zs = [z for z in (-2, -1, 0, 1, 2)
          if [final_cosine_result(-(EU + z), ce, md)
              for md in ROUNDING_MODES] == hw]
    theta = disc if disc <= 2 else disc - (1 << k)
    side = "up" if theta <= 0 else "dn"
    frame_ok = any((z in (0, 1)) if side == "up"
                   else (z in (-1, 0)) for z in zs)
    R = M >> k
    base_ok = hw == [final_cosine_result(-R, ce, md)
                     for md in ROUNDING_MODES]
    cens[("zset", tuple(zs), side, "base_ok" if base_ok
          else "BASE_MISS")] += 1
    cens[("frame_ok", frame_ok)] += 1
print(dict(sorted(cens.items(), key=str)))
