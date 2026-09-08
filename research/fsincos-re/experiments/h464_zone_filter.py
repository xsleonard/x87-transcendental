#!/usr/bin/env python3
"""h464 streaming zone filter (runs on the i7, self-contained).

Purpose: third-pass borrow-bit campaign — build cell-matched input
families.  Reads candidate inputs and the model's COS_CARRIER trace
stream in lockstep and keeps only NEAR-BOUNDARY rows: payload-active
rows (lsign=1, rsign=0) whose terminal accumulator sits within
THETA_WINDOW payload units of a chop-67 retention boundary, where
crossing that boundary changes the architectural result in at least
one rounding mode (visibility).  These are the only rows on which the
hardware borrow bit is observable; capturing them densifies the
(dist, low3, theta) cells for within-cell contrast analysis.

The boundary offset is computed arithmetically (no offset probing):
  mag   = A - B + prepay*2^unit          (|accumulator|, pre-patch
                                          payload coordinates)
  shift = bitlen(mag) - 67, rem = mag mod 2^shift
  t_up   = ceil((2^shift - rem) / 2^unit)   crossing above
  t_down = floor(rem / 2^unit) + 1          crossing below
theta = t_up (boundary above, hardware-high side is offsets >= t_up)
or -t_down + 1, whichever is nearer; a row is kept when the nearer
crossing is within THETA_WINDOW and visible.

Usage:  h464_zone_filter.py candidates.txt < trace_stream \
            1> selected.tsv
selected.tsv columns: input_se  input_sig  theta  trace_line
Exits nonzero if candidate/trace counts diverge.
"""
import sys

THETA_WINDOW = 5
MODES = ("rn", "rd", "ru")


def chop67(signed_value, scale):
    negative = signed_value < 0
    magnitude = -signed_value if negative else signed_value
    shift = max(magnitude.bit_length() - 67, 0)
    magnitude >>= shift
    return (-magnitude if negative else magnitude), scale + shift


def final_result(correction, corr_exponent, mode):
    numerator = (1 << -corr_exponent) + correction
    shift = numerator.bit_length() - 64
    if shift <= 0:
        return numerator << -shift
    kept = numerator >> shift
    remainder = numerator & ((1 << shift) - 1)
    half = 1 << (shift - 1)
    round_up = 0
    if mode == "rn":
        round_up = 1 if (remainder > half
                         or (remainder == half and kept & 1)) else 0
    elif mode == "ru":
        round_up = 1 if remainder else 0
    kept += round_up
    if kept >> 64:
        kept >>= 1
    return kept


def results_of(payload_value, A, B, unit, scale):
    corr, corr_e = chop67(-(A - B + (payload_value << unit)), scale)
    return tuple(final_result(corr, corr_e, m) for m in MODES)


def main():
    candidates = open(sys.argv[1])
    kept = total = 0
    for trace in sys.stdin:
        if not trace.startswith("COS_CARRIER"):
            continue                    # stray stderr noise: no candidate
        cand = candidates.readline()
        if not cand:
            sys.stderr.write("FATAL: trace stream longer than candidates\n")
            sys.exit(1)
        total += 1
        fields = {}
        for token in trace.split()[1:]:
            name, _, value = token.partition("=")
            fields[name] = value
        if fields["active"] != "1" or fields["lsign"] != "1" \
                or fields["rsign"] != "0":
            continue
        dist = int(fields["dist"])
        low3 = int(fields["low3"])
        prepay = low3 + 8 - dist
        le2, re2 = int(fields["le2"]), int(fields["re2"])
        ls, rs = int(fields["ls"], 16), int(fields["rs"], 16)
        scale = min(le2, re2, le2 - 8)
        A = ls << (le2 - scale)
        B = rs << (re2 - scale)
        unit = le2 - 8 - scale
        mag = A - B + (prepay << unit)
        if mag <= 0:
            continue
        shift = mag.bit_length() - 67
        if shift <= 0:
            continue
        rem = mag & ((1 << shift) - 1)
        step = 1 << unit
        t_up = -((rem - (1 << shift)) // step)      # ceil((2^s - rem)/step)
        t_down = rem // step + 1
        if t_up <= t_down:
            theta, rep_low, rep_high = t_up, prepay, prepay + t_up
        else:
            theta, rep_low, rep_high = (-t_down + 1, prepay - t_down, prepay)
        if abs(theta) > THETA_WINDOW:
            continue
        if results_of(rep_low, A, B, unit, scale) == \
                results_of(rep_high, A, B, unit, scale):
            continue                                  # blind boundary
        # pairing self-check: the traced square must be the chop-67 of
        # this candidate's m^2 — catches any candidate/trace slippage
        se, sig = cand.split()
        m_sq = int(sig, 16) ** 2
        if m_sq >> (m_sq.bit_length() - 67) != int(fields["mul"], 16):
            sys.stderr.write(f"FATAL: pairing broken at row {total}\n")
            sys.exit(1)
        kept += 1
        sys.stdout.write(f"{se}\t{sig}\t{theta}\t{trace.rstrip()}\n")
    if candidates.readline():
        sys.stderr.write("FATAL: candidates longer than trace stream\n")
        sys.exit(1)
    sys.stderr.write(f"filter: kept {kept} of {total}\n")


if __name__ == "__main__":
    main()
