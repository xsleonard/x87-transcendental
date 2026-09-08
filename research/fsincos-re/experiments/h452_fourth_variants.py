#!/usr/bin/env python3
"""h452: how does hardware really compute the fourth power?

h451 localized the collision family to the right product's fourth-power
path: building the right product from the true m^4 (U6) scores 607 vs
baseline 310, everything else ~34k.  Sweep the middle ground: the fourth
power computed from a square kept at 67+k bits (k guard bits visible
only to the squaring), and/or with different roundings:

  fourth_k,r1,r2 = round67_r2( (round(67+k)_r1(m^2))^2 )

with k in 0..12/full and roundings in {chop, RN}; terminal otherwise
baseline (payload kept).  Count mismatching rows over the full corpus.

Run from /tmp/stageA.
"""
import math
from collections import Counter
from multiprocessing import Pool

from h437_gate_extraction import (
    ROUNDING_MODES, load_labeled_rows, chop_to_67_bits, final_cosine_result)


def recover_m(square):
    for s in (58, 59, 60, 61):
        target = square << s
        m = math.isqrt(target)
        for cand in (m, m + 1):
            sq = cand * cand
            if sq >> s == square and sq.bit_length() - 67 == s:
                return cand, s
    return None, None


def round_to(full, width, mode):
    """Round `full` to `width` significant bits; returns (sig, dropped_bits)
    where value = sig * 2^dropped_bits (relative to full's own units)."""
    shift = max(full.bit_length() - width, 0)
    sig = full >> shift
    if mode == "rn" and shift:
        rem = full & ((1 << shift) - 1)
        half = 1 << (shift - 1)
        if rem > half or (rem == half and sig & 1):
            sig += 1
            if sig.bit_length() > width:
                sig >>= 1
                shift += 1
    return sig, shift

# ks: guard bits on the square feeding the squaring; "full" = exact m^2
CONFIGS = [(k, r1, r2)
           for k in [0, 1, 2, 3, 4, 6, 8, 12, "full"]
           for r1 in ("chop", "rn")
           for r2 in ("chop", "rn")
           if not (k == "full" and r1 == "rn")]


def analyze_row(row):
    fields, hw_results = row
    payload = int(fields["payload"])
    left_e2, right_e2 = int(fields["le2"]), int(fields["re2"])
    left_sig = int(fields["ls"], 16)
    left_sign, right_sign = int(fields["lsign"]), int(fields["rsign"])
    square, even_chain = int(fields["mul"], 16), int(fields["rf"], 16)
    fourth = int(fields["f4"], 16)

    m_rec, s_sq = recover_m(square)
    if m_rec is None:
        return ("NORECOVER",)
    msq = m_rec * m_rec

    # baseline right product value scale: rs = base_R >> shift_bR, exp re2
    base_R = fourth * even_chain
    shift_bR = max(base_R.bit_length() - 67, 0)
    eR_full = right_e2 - shift_bR
    # value(fourth) = fourth * 2^(ef4); base_R scale: ef4 + erf = eR_full
    # value(m^4) = m4 * 2^(ef4 + shift_f4v - 2*s_sq ... ) -- anchor via
    # square^2: fourth = (square^2) >> shift_f4  (chop; verify)
    sq2 = square * square
    shift_f4 = max(sq2.bit_length() - 67, 0)
    if sq2 >> shift_f4 != fourth:
        return ("F4NOTCHOP",)

    def check(rs_v, e_r):
        scale = min(left_e2, e_r)
        if payload:
            scale = min(scale, left_e2 - 8)
        acc = (-1 if left_sign else 1) * (left_sig << (left_e2 - scale)) \
            + (-1 if right_sign else 1) * (rs_v << (e_r - scale))
        if payload:
            acc += (-1 if left_sign else 1) * (payload << (left_e2 - 8 - scale))
        corr, corr_e = chop_to_67_bits(acc, scale)
        return all(final_cosine_result(corr, corr_e, m) == hw_results[m]
                   for m in ROUNDING_MODES)

    bad = []
    for k, r1, r2 in CONFIGS:
        if k == "full":
            sq_k, drop1 = msq, 0        # value = sq_k * 2^(em2 - s_sq)
            extra1 = s_sq
        else:
            width = 67 + k
            sq_k, shift1 = round_to(msq, width, r1)
            extra1 = s_sq - shift1      # bits below the baseline square
        # square value = sq_k * 2^(em2 - extra1) where square=chop67 ref
        f4_full = sq_k * sq_k           # value scale 2^(2*em2 - 2*extra1)
        f4_k, shift2 = round_to(f4_full, 67, r2)
        # value(f4_k) = f4_k * 2^(2*em2 - 2*extra1 + shift2)
        # baseline: value(fourth) = fourth * 2^(2*em2 + shift_f4)
        # => exponent delta vs baseline ef4: shift2 - 2*extra1 - shift_f4
        e_delta = shift2 - 2 * extra1 - shift_f4
        rprod = f4_k * even_chain
        shift_r = max(rprod.bit_length() - 67, 0)
        rs_v = rprod >> shift_r
        e_r = eR_full + e_delta + shift_r
        if not check(rs_v, e_r):
            bad.append((k, r1, r2))
    return tuple(bad)


def main():
    rows = load_labeled_rows()
    with Pool(8) as pool:
        results = pool.map(analyze_row, rows, chunksize=1000)
    counts = Counter()
    special = Counter()
    for bad in results:
        for name in bad:
            if isinstance(name, str):
                special[name] += 1
            else:
                counts[name] += 1
    print(f"rows: {len(results)}  special: {dict(special)}")
    for config in CONFIGS:
        n = counts.get(config, 0)
        tag = "  <== EXACT" if n == 0 else ""
        print(f"  k={config[0]!s:>4} sq={config[1]:4s} f4={config[2]:4s}: "
              f"{n:6d} mismatching rows{tag}")


if __name__ == "__main__":
    main()
