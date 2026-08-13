#!/usr/bin/env python3
"""h455: select truth-table capture targets and reconstruct their inputs.

Purpose: the h441-h454 campaign proved the remaining 310 FCOS fires are
single borrow-bit flips at the terminal subtract, decided by state that
no numeric basis exposes.  The next probe OBSERVES the gate on silicon:
capture every single-bit-flip neighbor of each fire input and see which
input bits toggle the hardware borrow.  This script builds the target
list.

Method:
  1. Re-derive every constrained row (half-line offset probe, as
     h446): b_hw = side of the boundary hardware chose, theta = the
     boundary's offset from the model payload, fire = model on the
     wrong side.
  2. Reconstruct each row's architectural input: the significand m is
     recovered from the traced square by integer sqrt (unique; h450);
     the exponent is selected by validating the bit-exact chain replica
     (h453) against the traced lf/rf.  Rows from the second input
     family (no exponent validates: the P5C4 path) are counted and
     skipped.
  3. Select ALL fire rows plus ALL constrained no-fire rows as
     controls, deduplicated by input.  (First revision sampled 3
     controls per fire cell; the per-bit fire-persistence statistic
     needs every base we have, and capture cost is trivial.)

Output (TSV, one header line, no pickle):
  h456_package/targets.tsv with columns
  id  role  se  sig  theta  b_hw  dist  low3  prepay
  where (se, sig) is the positive-sign x87 input as the capture runner
  wants it ("%x %llx").

Run from /tmp/stageA.
"""
import os
from multiprocessing import Pool

from h437_gate_extraction import (
    ROUNDING_MODES, load_labeled_rows, chop_to_67_bits, final_cosine_result)
from h453_chain_variants import (
    C6_1, C6_2, C6_3, C6_4, C6_5, C6_6, recover_m, mul_round, build_chain)

PROBE = list(range(-8, 9))
CONTROLS_PER_CELL = 3
EXP_BIAS_AT_M = 16446           # se = 16446 + e2m for a 64-bit sig m


def analyze_row(row):
    """One labeled row -> (b_hw, theta, fire, dist, low3, prepay, se, sig)
    or None (blind/inactive) or "NOEXPONENT" (P5C4 family)."""
    fields, hw_results = row
    payload = int(fields["payload"])
    left_e2, right_e2 = int(fields["le2"]), int(fields["re2"])
    left_sig, right_sig = int(fields["ls"], 16), int(fields["rs"], 16)
    left_sign, right_sign = int(fields["lsign"]), int(fields["rsign"])
    dist = int(fields["dist"])
    low3 = int(fields["low3"])
    if left_sign != 1 or right_sign != 0 or not payload:
        return None
    prepay = low3 + 8 - dist
    scale = min(left_e2, right_e2, left_e2 - 8)
    A = left_sig << (left_e2 - scale)
    B = right_sig << (right_e2 - scale)
    unit = left_e2 - 8 - scale

    def matches(payload_value):
        corr, corr_e = chop_to_67_bits(-(A - B + (payload_value << unit)),
                                       scale)
        return all(final_cosine_result(corr, corr_e, m) == hw_results[m]
                   for m in ROUNDING_MODES)

    allowed = [off for off in PROBE if matches(prepay + off)]
    if not allowed or len(allowed) == len(PROBE):
        return None
    lo_run = allowed[0] == PROBE[0]
    hi_run = allowed[-1] == PROBE[-1]
    if lo_run and not hi_run:
        b_hw, theta = 0, allowed[-1] + 1
    elif hi_run and not lo_run:
        b_hw, theta = 1, allowed[0]
    else:
        return None
    fire = 1 if (1 if 0 >= theta else 0) != b_hw else 0

    square_sig = int(fields["mul"], 16)
    m = recover_m(square_sig)
    if m is None:
        return "NOEXPONENT"
    lf_t, rf_t = int(fields["lf"], 16), int(fields["rf"], 16)
    for e2m in (-66, -67, -65, -68, -64, -69, -63):
        mag = (0, e2m, m)
        sq = mul_round(mag, mag, 67, "chop")
        f4 = mul_round(sq, sq, 67, "chop")
        if sq[2] != square_sig:
            return "NOEXPONENT"
        neg = build_chain(f4, C6_5, C6_3, C6_1, 67, 64, "rn",
                          False, False, False)
        pos = build_chain(f4, C6_6, C6_4, C6_2, 67, 64, "rn",
                          False, False, False)
        if neg[2] == lf_t and pos[2] == rf_t:
            # architectural encoding: the x87 significand must be
            # normalized (explicit integer bit set).  recover_m can
            # return a 63-bit m (value m*2^e2m); shift into the 64-bit
            # significand and lower the exponent accordingly, keeping
            # the value identical.
            shift = 64 - m.bit_length()
            return (b_hw, theta, fire, dist, low3, prepay,
                    EXP_BIAS_AT_M + e2m - shift, m << shift)
    return "NOEXPONENT"


def main():
    rows = load_labeled_rows()
    with Pool(8) as pool:
        results = pool.map(analyze_row, rows, chunksize=2000)
    noexp = sum(1 for r in results if r == "NOEXPONENT")
    usable = [r for r in results if r not in (None, "NOEXPONENT")]
    # dedupe by input, fires win over controls
    by_input = {}
    for r in usable:
        key = (r[6], r[7])
        if key not in by_input or r[2] > by_input[key][2]:
            by_input[key] = r
    fires = [r for r in by_input.values() if r[2] == 1]

    unique_controls = [r for r in by_input.values() if r[2] == 0]

    os.makedirs("h456_package", exist_ok=True)
    with open("h456_package/targets.tsv", "w") as fh:
        fh.write("id\trole\tse\tsig\ttheta\tb_hw\tdist\tlow3\tprepay\n")
        idx = 0
        for role, group in (("fire", fires), ("control", unique_controls)):
            for b_hw, theta, _, dist, low3, prepay, se, sig in group:
                fh.write(f"T{idx:05d}\t{role}\t{se:x}\t{sig:016x}\t"
                         f"{theta}\t{b_hw}\t{dist}\t{low3}\t{prepay}\n")
                idx += 1
    print(f"constrained usable rows: {len(usable)} "
          f"(NOEXPONENT skipped: {noexp})")
    print(f"unique inputs: {len(by_input)}; fires: {len(fires)}; "
          f"controls selected: {len(unique_controls)}")
    print("wrote h456_package/targets.tsv")


if __name__ == "__main__":
    main()
