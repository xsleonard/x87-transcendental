#!/usr/bin/env python3
"""h630: the 248 rows are sqrt(2)-branch recovery errors.
chop67(s^2) patterns are satisfiable from BOTH the 127-bit and
128-bit square branches (operands sqrt(2) apart); recover_m
picked the wrong one on these rows.  Recover with both
branches, validate against traced f4+lf+rf, and rescore under
the Round-57 rule (h610 pipeline)."""
import math
from collections import defaultdict
from h437_gate_extraction import (ROUNDING_MODES, load_labeled_rows,
                                  final_cosine_result)
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5,
                                 C6_6, build_chain, mul_round)
from h588_select import split_words
from h609_ref_predictor import load_model, predict

FITS, CBEST = load_model()


def recover_both(t):
    outs = []
    for sh in (60, 61):
        s0 = math.isqrt(t << sh)
        for s in range(s0 - 2, s0 + 3):
            if s <= 0:
                continue
            s2 = s * s
            r2 = s2.bit_length() - 67
            if r2 >= 0 and (s2 >> r2) == t:
                mm = s
                while mm.bit_length() > 64:
                    mm >>= 1
                while 0 < mm.bit_length() < 64:
                    mm <<= 1
                outs.append(mm)
    return outs


cens = defaultdict(int)
rows = load_labeled_rows()
for fields, hw_sigs in rows:
    if fields.get("active") != "1" or fields["lsign"] != "1" \
            or fields["rsign"] != "0":
        continue
    le2, re2 = int(fields["le2"]), int(fields["re2"])
    ls, rs = int(fields["ls"], 16), int(fields["rs"], 16)
    dist, low3 = int(fields["dist"]), int(fields["low3"])
    prepay = low3 + 8 - dist
    scale = min(le2, re2, le2 - 8)
    A = ls << (le2 - scale)
    P = prepay << (le2 - 8 - scale)
    M = A - (rs << (re2 - scale)) + P
    if M <= 0:
        continue
    k = max(M.bit_length() - 67, 0)
    if k < 3:
        continue
    disc = M & ((1 << k) - 1)
    if disc > 2 and disc < (1 << k) - 2:
        continue
    mul = int(fields["mul"], 16)
    good = None
    for mm in recover_both(mul):
        mag = (0, -66, mm)
        sq = mul_round(mag, mag, 67, "chop")
        if sq[2] != mul:
            continue
        f4 = mul_round(sq, sq, 67, "chop")
        neg = build_chain(f4, C6_5, C6_3, C6_1, 67, 64, "rn",
                          False, False, False)
        pos = build_chain(f4, C6_6, C6_4, C6_2, 67, 64, "rn",
                          False, False, False)
        if f4[2] == int(fields["f4"], 16) and \
                neg[2] == int(fields["lf"], 16) and \
                pos[2] == int(fields["rf"], 16):
            good = (mm, sq, f4, neg, pos)
            break
    if good is None:
        cens["STILL_UNFIXED"] += 1
        continue
    cens["recovered"] += 1
    mm, sq, f4, neg, pos = good
    # rescore under the rule (h610 semantics)
    theta = disc if disc <= 2 else disc - (1 << k)
    side = "up" if theta <= 0 else "dn"
    ce = scale + k
    R = M >> k
    hw = [hw_sigs[md] for md in ROUNDING_MODES]
    base_ok = hw == [final_cosine_result(-R, ce, md)
                     for md in ROUNDING_MODES]
    B_full = f4[2] * pos[2]
    rsh = B_full.bit_length() - 67
    rdisc = B_full & ((1 << rsh) - 1)
    f4_full = sq[2] * sq[2]
    s4 = f4_full.bit_length() - 67
    t4 = f4_full & ((1 << s4) - 1)
    left = mul_round(sq, neg, 67, "chop")
    right = mul_round(f4, pos, 67, "chop")
    scale2 = min(left[1], right[1], left[1] - 8)
    bshift = right[1] - scale2
    F = rsh - bshift
    if F < 0:
        cens["noF"] += 1
        continue
    kf = k + F
    A2 = left[2] << (left[1] - scale2)
    P2 = prepay << (left[1] - 8 - scale2)
    APf = (A2 + P2) << F
    EU = (APf - B_full) >> kf
    Vlow = (APf - B_full) - (EU << kf)
    za, zb = (0, 1) if side == "up" else (-1, 0)
    ra = [final_cosine_result(-(EU + za), ce, md)
          for md in ROUNDING_MODES]
    rb = [final_cosine_result(-(EU + zb), ce, md)
          for md in ROUNDING_MODES]
    if ra == rb:
        cens[("blind", base_ok)] += 1
        continue
    S, C = split_words(f4[2], pos[2])
    st = ((S + C) >> max(rsh - 59, 0)) & 63
    tau = t4 / (1 << s4)
    mf = (mm & ((1 << 63) - 1)) / (1 << 63)
    xd12 = min(11, (rdisc * 12) >> rsh)
    key = (dist, low3, ce, side)
    p = predict(FITS, CBEST, key, xd12, mf, st, tau, Vlow, kf,
                pos[2])
    if p is None:
        cens[("uncovered", base_ok)] += 1
        continue
    _, req2p, _ = p
    port_ok = hw == [final_cosine_result(-(EU + req2p), ce, md)
                     for md in ROUNDING_MODES]
    cens[("scored", base_ok, port_ok)] += 1
print(dict(sorted(cens.items(), key=str)))
