#!/usr/bin/env python3
"""h453: full-pipeline replica from m; chain-construction variants.

h451/h452 exhausted the fourth-power path.  The remaining upstream state
is the Horner chain construction: products chop67, constant adds RN64.
h442 showed rf+1 explains ALL fire_R and lf+1/mul+1 the fire_L rows, so
a rare one-ulp flip in the chain values is exactly the fire signature —
e.g. if the hardware's chain adds see the unchopped product (fused
behavior), RN64 outcomes flip precisely at double-rounding states.

This script recomputes the whole FCOS producer from the recovered m
(e2 = -66 for the direct e=-3 corpora), validates bit-exactness against
every traced field, then scores variants against hardware:

  base      : replica as ported (control; must equal the 310 baseline)
  fuse_last : final chain adds consume the exact product (no chop67)
  fuse_all  : both adds in each chain fused
  prod68-71 : chain products chopped at 68..71 bits
  add_rn65-67, add_chop65-67 : chain adds at wider widths
  sticky    : RN64 adds with the chopped product's sticky ORed in

Run from /tmp/stageA.
"""
import math
from collections import Counter
from multiprocessing import Pool

from h437_gate_extraction import (
    ROUNDING_MODES, load_labeled_rows, chop_to_67_bits, final_cosine_result)

# P5 ROM constants: (sign, e2, sig)
C6_1 = (1, -68, (0x7 << 64) | 0xfffffffffffffffe)
C6_2 = (0, -71, (0x5 << 64) | 0x5555555555554277)
C6_3 = (1, -76, (0x5 << 64) | 0xb05b05b05a18a1ba)
C6_4 = (0, -82, (0x6 << 64) | 0x80680675b559f2cf)
C6_5 = (1, -88, (0x4 << 64) | 0x9f93af61f5349300)
C6_6 = (0, -95, (0x4 << 64) | 0x7a4f2483514c1af8)

E2_M = -66      # direct e=-3 inputs: value = m * 2^-66, m in [2^63, 2^64)


def normalize(sign, mag, scale, bits, mode, sticky_extra=0):
    """acc_round_bits_mode replica for a positive magnitude integer."""
    if mag == 0:
        return (sign, 0, 0)
    sh = mag.bit_length() - bits
    if sh <= 0:
        return (sign, scale + sh, mag << -sh)
    top = mag >> sh
    guard = (mag >> (sh - 1)) & 1
    below = (mag & ((1 << (sh - 1)) - 1)) | sticky_extra
    if mode == "chop":
        pass
    elif mode == "rn":
        if guard and (below or (top & 1)):
            top += 1
            if top >> bits:
                top >>= 1
                sh += 1
    else:
        raise ValueError(mode)
    return (sign, scale + sh, top)


def mul_round(a, b, bits, mode):
    return normalize(a[0] ^ b[0], a[2] * b[2], a[1] + b[1], bits, mode)


def add_round(left, right, bits, mode, sticky_extra=0):
    scale = min(left[1], right[1])
    acc = (-1 if left[0] else 1) * (left[2] << (left[1] - scale)) \
        + (-1 if right[0] else 1) * (right[2] << (right[1] - scale))
    sign = 1 if acc < 0 else 0
    return normalize(sign, abs(acc), scale, bits, mode,
                     sticky_extra=sticky_extra)


def recover_m(square_sig):
    for s in (58, 59, 60, 61):
        m = math.isqrt(square_sig << s)
        for cand in (m, m + 1):
            sq = cand * cand
            if sq >> s == square_sig and sq.bit_length() - 67 == s:
                return cand
    return None


def build_chain(fourth, c_lead, c_mid, c_last, prod_bits, add_bits,
                add_mode, fuse_last, fuse_all, sticky):
    """One Horner chain: lead const -> xf4 -> +mid -> xf4 -> +last."""
    chain = c_lead
    # first product + mid add
    if fuse_all:
        prod_exact = (fourth[0] ^ chain[0], fourth[1] + chain[1],
                      fourth[2] * chain[2])
        chain = add_round(c_mid, prod_exact, add_bits, add_mode)
    else:
        prod = mul_round(fourth, chain, prod_bits, "chop")
        extra = 0
        if sticky:
            full = fourth[2] * chain[2]
            sh = full.bit_length() - prod_bits
            extra = 1 if (sh > 0 and full & ((1 << sh) - 1)) else 0
        chain = add_round(c_mid, prod, add_bits, add_mode,
                          sticky_extra=extra)
    # second product + last add
    if fuse_last or fuse_all:
        prod_exact = (fourth[0] ^ chain[0], fourth[1] + chain[1],
                      fourth[2] * chain[2])
        chain = add_round(c_last, prod_exact, add_bits, add_mode)
    else:
        prod = mul_round(fourth, chain, prod_bits, "chop")
        extra = 0
        if sticky:
            full = fourth[2] * chain[2]
            sh = full.bit_length() - prod_bits
            extra = 1 if (sh > 0 and full & ((1 << sh) - 1)) else 0
        chain = add_round(c_last, prod, add_bits, add_mode,
                          sticky_extra=extra)
    return chain


def terminal(square, negative, positive, fourth, hw_results):
    """fcos_low3_terminal_correction + final combine, all three modes."""
    left = mul_round(square, negative, 67, "chop")
    right = mul_round(fourth, positive, 67, "chop")
    product = square[2] * negative[2]
    shift = max(product.bit_length() - 67, 0)
    discarded = product & ((1 << shift) - 1) if shift > 0 else 0
    ud = (discarded << 3) >> shift if shift > 0 else 0
    u5d = (discarded << 5) >> shift if shift > 0 else 0
    rproduct = fourth[2] * positive[2]
    rshift = max(rproduct.bit_length() - 67, 0)
    rdisc = rproduct & ((1 << rshift) - 1) if rshift > 0 else 0
    rud = (rdisc << 1) >> rshift if rshift > 0 else 0
    low3 = square[2] & 7
    distance = abs(left[1] - right[1])
    active = 1 if (low3 and (ud or (distance == 7 and u5d))) else 0
    payload = low3 + 8 - distance if active else 0
    if active and distance == 10 and low3 == 6 and rud:
        lane_shift = (left[1] - 8) - right[1]
        lane = (right[2] >> lane_shift) if lane_shift >= 0 \
            else (right[2] << -lane_shift)
        lane_payload = lane & 0xFF
        difference = (lane_payload - payload) & 0xFF
        if difference >= 128:
            difference -= 256
        if difference == -2:
            payload = lane_payload
    if active and distance == 8 and low3 == 7 and ud >= 3:
        lane_shift = (left[1] - 8) - right[1]
        lane = (right[2] >> lane_shift) if lane_shift >= 0 \
            else (right[2] << -lane_shift)
        lane_payload = lane & 0xFF
        difference = (lane_payload - payload) & 0xFF
        if difference >= 128:
            difference -= 256
        if difference == 0:
            payload -= 1
    scale = min(left[1], right[1])
    if payload and left[1] - 8 < scale:
        scale = left[1] - 8
    acc = (-1 if left[0] else 1) * (left[2] << (left[1] - scale)) \
        + (-1 if right[0] else 1) * (right[2] << (right[1] - scale))
    if payload:
        acc += (-1 if left[0] else 1) * (payload << (left[1] - 8 - scale))
    corr, corr_e = chop_to_67_bits(acc, scale)
    ok = all(final_cosine_result(corr, corr_e, m) == hw_results[m]
             for m in ROUNDING_MODES)
    return ok, left, right


VARIANTS = (["base", "fuse_last", "fuse_all", "sticky"]
            + [f"prod{b}" for b in (68, 69, 70, 71)]
            + [f"add_rn{b}" for b in (65, 66, 67)]
            + [f"add_chop{b}" for b in (64, 65, 66)])


def analyze_row(row):
    fields, hw_results = row
    square_sig = int(fields["mul"], 16)
    m = recover_m(square_sig)
    if m is None:
        return ("NORECOVER",)
    # the input exponent is not recoverable from mul alone (corpora mix
    # exponents); select it by validating the traced chain values
    lf_t, rf_t = int(fields["lf"], 16), int(fields["rf"], 16)
    square = fourth = None
    for e2m in (-66, -67, -65, -68, -64, -69, -63):
        mag = (0, e2m, m)
        sq = mul_round(mag, mag, 67, "chop")
        f4 = mul_round(sq, sq, 67, "chop")
        if sq[2] != square_sig or f4[2] != int(fields["f4"], 16):
            return ("SQMISMATCH",)
        neg = build_chain(f4, C6_5, C6_3, C6_1, 67, 64, "rn",
                          False, False, False)
        pos = build_chain(f4, C6_6, C6_4, C6_2, 67, 64, "rn",
                          False, False, False)
        if neg[2] == lf_t and pos[2] == rf_t:
            square, fourth = sq, f4
            break
    if square is None:
        return ("NOEXPONENT",)

    bad = []
    validated = None
    for name in VARIANTS:
        prod_bits, add_bits, add_mode = 67, 64, "rn"
        fuse_last = name == "fuse_last"
        fuse_all = name == "fuse_all"
        sticky = name == "sticky"
        if name.startswith("prod"):
            prod_bits = int(name[4:])
        elif name.startswith("add_rn"):
            add_bits = int(name[6:])
        elif name.startswith("add_chop"):
            add_bits, add_mode = int(name[8:]), "chop"
        negative = build_chain(fourth, C6_5, C6_3, C6_1, prod_bits,
                               add_bits, add_mode, fuse_last, fuse_all,
                               sticky)
        positive = build_chain(fourth, C6_6, C6_4, C6_2, prod_bits,
                               add_bits, add_mode, fuse_last, fuse_all,
                               sticky)
        if name == "base":
            validated = (negative[2] == int(fields["lf"], 16)
                         and positive[2] == int(fields["rf"], 16))
        ok, left, right = terminal(square, negative, positive, fourth,
                                   hw_results)
        if name == "base" and validated:
            validated = (left[2] == int(fields["ls"], 16)
                         and right[2] == int(fields["rs"], 16)
                         and left[1] == int(fields["le2"])
                         and right[1] == int(fields["re2"]))
        if not ok:
            bad.append(name)
    if not validated:
        bad.append("REPLICA_INVALID")
    return tuple(bad)


def main():
    rows = load_labeled_rows()
    with Pool(8) as pool:
        results = pool.map(analyze_row, rows, chunksize=500)
    counts = Counter()
    for bad in results:
        for name in bad:
            counts[name] += 1
    print(f"rows: {len(results)}")
    for name in ["NORECOVER", "SQMISMATCH", "NOEXPONENT", "REPLICA_INVALID"]:
        print(f"  {name}: {counts.get(name, 0)}")
    for name in VARIANTS:
        n = counts.get(name, 0)
        tag = "  <== EXACT" if n == 0 else ""
        print(f"  {name:10s}: {n:6d} mismatching rows{tag}")


if __name__ == "__main__":
    main()
