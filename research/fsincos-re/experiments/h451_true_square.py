#!/usr/bin/env python3
"""h451: does the payload stand in for the square/fourth chop error?

With m recovered exactly (h450), test terminal variants that replace the
chopped square/fourth by their true powers, with and without the payload
term, over every labeled row and all three modes:

  U1: left=chop67(m^2*lf), right=chop67(m^4*rf), no payload
  U2: left=chop67(m^2*lf), right=baseline,        no payload
  U3: left=baseline,       right=chop67(m^4*rf),  no payload
  U4/U5/U6: same three with the payload kept
  U7: full-width m^2*lf and m^4*rf into the accumulator, no payload
  U0: baseline (control)

Alignment: m^2 = (mul + frac)*2^sqe2 with mul = chop67(m^2), so
chop67(m^2*lf) shares ls's exponent le2 when its width matches; handled
by tracking widths explicitly.

Run from /tmp/stageA.
"""
import math
from collections import Counter
from multiprocessing import Pool

from h437_gate_extraction import (
    ROUNDING_MODES, load_labeled_rows, chop_to_67_bits, final_cosine_result)

VARIANTS = ["U0_baseline",
            "U1_trueLR_nopay", "U2_trueL_nopay", "U3_trueR_nopay",
            "U4_trueLR_pay", "U5_trueL_pay", "U6_trueR_pay",
            "U7_fulltrue_nopay"]


def recover_m(square):
    for s in (58, 59, 60, 61):
        target = square << s
        m = math.isqrt(target)
        for cand in (m, m + 1):
            sq = cand * cand
            if sq >> s == square and sq.bit_length() - 67 == s:
                return cand, s
    return None, None


def analyze_row(row):
    fields, hw_results = row
    payload = int(fields["payload"])
    left_e2, right_e2 = int(fields["le2"]), int(fields["re2"])
    left_sign, right_sign = int(fields["lsign"]), int(fields["rsign"])
    square, odd_chain = int(fields["mul"], 16), int(fields["lf"], 16)
    even_chain = int(fields["rf"], 16)
    fourth = int(fields["f4"], 16)

    m_rec, s_sq = recover_m(square)
    if m_rec is None:
        return ("NORECOVER",)
    msq = m_rec * m_rec                 # = (square<<s_sq) + sqdisc

    # Exponent bookkeeping (value scales):
    #   ls = base_L >> shift_bL with exponent le2
    #     => value(base_L, full) = base_L * 2^(le2 - shift_bL)
    #   value(m^2) = msq * 2^(em - s_sq) where value(mul) = mul * 2^em
    #     => true_L = msq*lf sits s_sq fractional bits below base_L
    #   fourth = (square^2) >> shift_f4
    #     => m4 = msq^2 sits (shift_f4 + 2*s_sq) bits below base_R
    base_L = square * odd_chain
    base_R = fourth * even_chain
    true_L = msq * odd_chain
    m4 = msq * msq
    true_R = m4 * even_chain

    shift_bL = max(base_L.bit_length() - 67, 0)
    shift_bR = max(base_R.bit_length() - 67, 0)
    shift_f4 = max((square * square).bit_length() - 67, 0)
    eL_full = left_e2 - shift_bL
    eR_full = right_e2 - shift_bR
    eL_true = eL_full - s_sq
    eR_true = eR_full - shift_f4 - 2 * s_sq

    def check(terms, pay):
        scale = min(e for _, e in terms)
        if pay:
            scale = min(scale, left_e2 - 8)
        acc = 0
        for (value, e), sign in zip(terms, (left_sign, right_sign)):
            acc += (-1 if sign else 1) * (value << (e - scale))
        if pay:
            acc += (-1 if left_sign else 1) * (pay << (left_e2 - 8 - scale))
        corr, corr_e = chop_to_67_bits(acc, scale)
        return all(final_cosine_result(corr, corr_e, m) == hw_results[m]
                   for m in ROUNDING_MODES)

    def chop67v(full, e_full):
        shift = max(full.bit_length() - 67, 0)
        return full >> shift, e_full + shift

    bad = []
    ls_b = chop67v(base_L, eL_full)
    rs_b = chop67v(base_R, eR_full)
    ls_t = chop67v(true_L, eL_true)
    rs_t = chop67v(true_R, eR_true)

    tests = {
        "U0_baseline": ([ls_b, rs_b], payload),
        "U1_trueLR_nopay": ([ls_t, rs_t], 0),
        "U2_trueL_nopay": ([ls_t, rs_b], 0),
        "U3_trueR_nopay": ([ls_b, rs_t], 0),
        "U4_trueLR_pay": ([ls_t, rs_t], payload),
        "U5_trueL_pay": ([ls_t, rs_b], payload),
        "U6_trueR_pay": ([ls_b, rs_t], payload),
        "U7_fulltrue_nopay": ([(true_L, eL_true), (true_R, eR_true)], 0),
    }
    for name, (terms, pay) in tests.items():
        if not check(terms, pay):
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
    print(f"rows: {len(results)}  (NORECOVER: {counts.get('NORECOVER', 0)})")
    for name in VARIANTS:
        n = counts.get(name, 0)
        tag = "  <== EXACT" if n == 0 else ""
        print(f"  {name:18s}: {n:6d} mismatching rows{tag}")


if __name__ == "__main__":
    main()
