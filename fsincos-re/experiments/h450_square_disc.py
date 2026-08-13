#!/usr/bin/env python3
"""h450: recover the reduced operand m from the trace and test the
square's discarded field against the delta constraints.

mul = chop67(m^2) discards ~60 bits, but sqrt contracts the interval to
width < 1, so m is uniquely determined by mul (integer sqrt + verify).
This exposes the one upstream state the terminal trace hides: the
discarded fraction of the square, sqfrac = (m^2 mod 2^s) / 2^s — and
the fourth power's discarded fraction f4frac likewise (from mul).

Scan sign(delta) on exact-tie rows and [delta>=1] on theta=+1 rows
against these, alone and in simple arithmetic combinations with prepay.

Run from /tmp/stageA.
"""
import math
from collections import Counter, defaultdict
from multiprocessing import Pool

from h437_gate_extraction import (
    ROUNDING_MODES, load_labeled_rows, chop_to_67_bits, final_cosine_result)

PROBE = list(range(-8, 9))


def analyze_row(row):
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

    square = int(fields["mul"], 16)
    # recover m: find integer m with (m*m) >> s == square for some s
    m_rec, s_rec, sqdisc = None, None, None
    for s in (58, 59, 60, 61):
        target = square << s
        m = math.isqrt(target)
        for cand in (m, m + 1):
            sq = cand * cand
            if sq >> s == square and sq.bit_length() - 67 == s:
                m_rec, s_rec = cand, s
                sqdisc = sq & ((1 << s) - 1)
                break
        if m_rec is not None:
            break
    if m_rec is None:
        return "NORECOVER"

    sqfrac = sqdisc / (1 << s_rec)
    f4full = square * square
    f4shift = max(f4full.bit_length() - 67, 0)
    f4frac = (f4full & ((1 << f4shift) - 1)) / (1 << f4shift)

    feats = {
        "dist": dist, "low3": low3, "prepay": prepay,
        "m_low8": m_rec & 0xFF,
        "sqfrac": sqfrac, "f4frac": f4frac,
        "sq_top8": int(sqfrac * 256),
        "f4_top8": int(f4frac * 256),
        "combo_2s_f4": (2 * sqfrac + f4frac),
        "ud": int(fields["ud"]), "u5d": int(fields["u5d"]),
    }
    return b_hw, theta, feats


def scan_float(rows, label_name, keys):
    """For float features: find best single threshold separating labels."""
    print(f"\n=== {label_name} (n={len(rows)}, "
          f"pos={sum(l for l, _ in rows)}) ===")
    base = min(sum(l for l, _ in rows), len(rows) - sum(l for l, _ in rows))
    print(f"  baseline inseparable: {base}")
    for key in keys:
        pairs = sorted((f[key], l) for l, f in rows)
        values = [v for v, _ in pairs]
        labels = [l for _, l in pairs]
        total_pos = sum(labels)
        best = base
        # threshold scan: below t -> class c
        pos_below = 0
        for i in range(1, len(pairs)):
            pos_below += labels[i - 1]
            if values[i] == values[i - 1]:
                continue
            neg_below = i - pos_below
            err_a = pos_below + (len(pairs) - i - (total_pos - pos_below))
            err_b = neg_below + (total_pos - pos_below)
            best = min(best, err_a, err_b)
        print(f"  {key:12s}: best single-threshold error {best}")


def main():
    rows = load_labeled_rows()
    with Pool(8) as pool:
        results = pool.map(analyze_row, rows, chunksize=2000)
    norec = sum(1 for r in results if r == "NORECOVER")
    good = [r for r in results if r not in (None, "NORECOVER")]
    print(f"constrained rows: {len(good)}, m-recovery failures: {norec}")

    ties = [(b, f) for b, t, f in good if t == 0]
    ones = [(b, f) for b, t, f in good if t == 1]
    keys = ["sqfrac", "f4frac", "combo_2s_f4", "m_low8", "sq_top8",
            "f4_top8", "u5d", "prepay"]
    scan_float(ties, "sign(delta) on ties", keys)
    scan_float(ones, "[delta>=1] on theta=+1", keys)

    # conditional: within each (dist, low3), does sqfrac order the ties?
    print("\n=== per-cell sqfrac threshold consistency on ties ===")
    cells = defaultdict(list)
    for b, t, f in good:
        if t == 0:
            cells[(f["dist"], f["low3"])].append((f["sqfrac"], b))
    inconsistent = 0
    total_cells = 0
    for key in sorted(cells):
        group = sorted(cells[key])
        labels = [b for _, b in group]
        n = len(labels)
        pos = sum(labels)
        best = min(pos, n - pos)
        pos_below = 0
        for i in range(1, n):
            pos_below += labels[i - 1]
            neg_below = i - pos_below
            best = min(best,
                       pos_below + (n - i - (pos - pos_below)),
                       neg_below + (pos - pos_below))
        total_cells += 1
        if best > 0:
            inconsistent += 1
        print(f"  dist={key[0]} low3={key[1]}: n={n} pos={pos} "
              f"best-threshold-err={best}")
    print(f"cells with perfect sqfrac threshold: "
          f"{total_cells - inconsistent}/{total_cells}")


if __name__ == "__main__":
    main()
