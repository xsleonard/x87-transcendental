#!/usr/bin/env python3
"""h443: unify G_R/G_L as a payload-lane rule.

h442 showed: fires all live in the payload-active regime; fire_R rows
are (almost all) equally explained by payload-1, fire_L rows largely by
payload+1.  The C model already carries two empirical patches keyed on
`difference = (lane_payload - payload) mod 256 (signed)` where
lane_payload is the right operand's actual 8-bit lane at the payload
position.  Hypothesis: the hardware payload is a function of the lane,
and every remaining fire is a window where the model's low3-derived
payload is off by one.

For each labeled row compute (dist, low3, ud, rud, difference) and the
required payload adjustment implied by the label, then cross-tabulate.

Run from /tmp/stageA.
"""
from collections import Counter
from multiprocessing import Pool

from h437_gate_extraction import (
    ROUNDING_MODES, load_labeled_rows, chop_to_67_bits, final_cosine_result)


def analyze_row(row):
    fields, hw_results = row
    payload = int(fields["payload"])
    left_e2, right_e2 = int(fields["le2"]), int(fields["re2"])
    left_sig, right_sig = int(fields["ls"], 16), int(fields["rs"], 16)
    left_sign, right_sign = int(fields["lsign"]), int(fields["rsign"])

    def matches(ls_value, rs_value, payload_value=None):
        pay = payload if payload_value is None else payload_value
        scale = min(left_e2, right_e2)
        if payload:
            scale = min(scale, left_e2 - 8)
        accumulator = (-1 if left_sign else 1) * (ls_value << (left_e2 - scale)) \
                    + (-1 if right_sign else 1) * (rs_value << (right_e2 - scale))
        if pay:
            accumulator += (-1 if left_sign else 1) * (pay << (left_e2 - 8 - scale))
        corr, corr_e = chop_to_67_bits(accumulator, scale)
        return all(final_cosine_result(corr, corr_e, m) == hw_results[m]
                   for m in ROUNDING_MODES)

    plain_ok = matches(left_sig, right_sig)
    right_up_ok = matches(left_sig, right_sig + 1)
    left_up_ok = matches(left_sig + 1, right_sig)
    label_R = 1 if (not plain_ok and right_up_ok) else (0 if (plain_ok and not right_up_ok) else -1)
    label_L = 1 if (not plain_ok and left_up_ok and not right_up_ok) else (0 if (plain_ok and not left_up_ok) else -1)

    dist = int(fields["dist"])
    lane_shift = dist - 8
    lane = (right_sig >> lane_shift) if lane_shift >= 0 else (right_sig << -lane_shift)
    lane_payload = lane & 0xFF
    difference = (lane_payload - payload) & 0xFF
    if difference >= 128:
        difference -= 256

    # which payload adjustments reproduce hardware
    pay_fixes = tuple(adj for adj in (-2, -1, 1, 2)
                      if matches(left_sig, right_sig, payload_value=payload + adj))

    return (label_R, label_L, dist, int(fields["low3"]), int(fields["ud"]),
            int(fields["rud"]), payload, difference, plain_ok, pay_fixes)


def main():
    rows = load_labeled_rows()
    with Pool(8) as pool:
        analyzed = pool.map(analyze_row, rows, chunksize=2000)

    groups = {
        "fire_R": [a for a in analyzed if a[0] == 1],
        "fire_L": [a for a in analyzed if a[1] == 1],
        "nofire_R": [a for a in analyzed if a[0] == 0],
        "nofire_L": [a for a in analyzed if a[1] == 0],
    }
    print("=== difference = lane_payload - payload, by group ===")
    for name, group in groups.items():
        tally = Counter(a[7] for a in group)
        print(f"  {name} (n={len(group)}): {dict(sorted(tally.items()))}"
              if len(tally) < 20 else
              f"  {name} (n={len(group)}): {tally.most_common(12)}")

    print("\n=== fire rows: (dist, low3, difference) -> count ===")
    for name in ("fire_R", "fire_L"):
        tally = Counter((a[2], a[3], a[7]) for a in groups[name])
        print(f"  {name}:")
        for key, count in sorted(tally.items()):
            print(f"    dist={key[0]} low3={key[1]} diff={key[2]:+d}: {count}")

    print("\n=== fire rows: payload adjustments that reproduce hw ===")
    for name in ("fire_R", "fire_L"):
        tally = Counter(a[9] for a in groups[name])
        print(f"  {name}: {dict(tally)}")

    print("\n=== nofire rows: does any payload adjustment ALSO match? ===")
    for name in ("nofire_R", "nofire_L"):
        tally = Counter(a[9] for a in groups[name])
        print(f"  {name}: {dict(tally.most_common(8))}")

    print("\n=== ALL informative rows: (difference, required-fix) ===")
    informative = [a for a in analyzed if a[0] != -1 or a[1] != -1]
    tally = Counter()
    for a in informative:
        required = "R+1" if a[0] == 1 else ("L+1" if a[1] == 1 else "none")
        tally[(a[7], required)] += 1
    for (diff, req), count in sorted(tally.items()):
        print(f"  diff={diff:+4d} fix={req:5s}: {count}")


if __name__ == "__main__":
    main()
