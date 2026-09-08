#!/usr/bin/env python3
"""h444: mine the unified payload rule payload_hw = g(prepay, lane, window).

h443 established: all fires are payload off-by-one events at small
lane-difference; the two empirical C patches (dist10/low3=6 diff==-2 ->
payload=lane; dist8/low3=7 ud>=3 diff==0 -> payload-1) are earlier
sightings of the same rule.  This script rewinds those patches to get
the PRE-PATCH payload (low3 + 8 - dist), computes the pre-patch lane
difference, and for every row derives the full set of payload_hw values
in [prepay-3, prepay+3] that reproduce hardware in all three modes.

Output: per (dist, low3, prediff) cell, the intersection of allowed
payload_hw offsets across rows that CONSTRAIN the rule (rows whose
allowed set excludes some offsets), split into "requires nonzero
offset" (fire-like) and "requires zero" (nofire-like) counts.  A clean
unified rule shows up as cells whose required offset is consistent; any
mixed cell gets its rows dumped with extended state (ud, u5d, rud,
lane9 low bit, rs bit above lane) for the residual discriminator.

Run from /tmp/stageA.
"""
from collections import Counter, defaultdict
from multiprocessing import Pool

from h437_gate_extraction import (
    ROUNDING_MODES, load_labeled_rows, chop_to_67_bits, final_cosine_result)

OFFSETS = range(-3, 4)


def analyze_row(row):
    fields, hw_results = row
    payload = int(fields["payload"])
    if not payload and not int(fields["active"]):
        return None
    left_e2, right_e2 = int(fields["le2"]), int(fields["re2"])
    left_sig, right_sig = int(fields["ls"], 16), int(fields["rs"], 16)
    left_sign, right_sign = int(fields["lsign"]), int(fields["rsign"])
    dist = int(fields["dist"])
    low3 = int(fields["low3"])

    prepay = low3 + 8 - dist
    lane_shift = dist - 8
    lane = (right_sig >> lane_shift) if lane_shift >= 0 else (right_sig << -lane_shift)
    lane_payload = lane & 0xFF
    prediff = (lane_payload - prepay) & 0xFF
    if prediff >= 128:
        prediff -= 256

    def matches(payload_value):
        scale = min(left_e2, right_e2)
        if payload:
            scale = min(scale, left_e2 - 8)
        accumulator = (-1 if left_sign else 1) * (left_sig << (left_e2 - scale)) \
                    + (-1 if right_sign else 1) * (right_sig << (right_e2 - scale))
        if payload_value:
            accumulator += (-1 if left_sign else 1) * (payload_value << (left_e2 - 8 - scale))
        corr, corr_e = chop_to_67_bits(accumulator, scale)
        return all(final_cosine_result(corr, corr_e, m) == hw_results[m]
                   for m in ROUNDING_MODES)

    allowed = frozenset(off for off in OFFSETS if matches(prepay + off))
    if not allowed:
        return (dist, low3, prediff, "UNEXPLAINED", None)

    # rows that allow offset 0 AND every candidate nonzero alternative
    # constrain nothing; classify by what they exclude
    extras = (int(fields["ud"]), int(fields["u5d"]), int(fields["rud"]),
              (lane >> 8) & 1 if lane_shift >= 0 else -1,   # bit above lane
              right_sig & 1, payload)
    return (dist, low3, prediff, allowed, extras)


def main():
    rows = load_labeled_rows()
    with Pool(8) as pool:
        analyzed = [a for a in pool.map(analyze_row, rows, chunksize=2000)
                    if a is not None]

    unexplained = [a for a in analyzed if a[3] == "UNEXPLAINED"]
    print(f"active rows: {len(analyzed)}, unexplained by any offset in "
          f"[-3,3]: {len(unexplained)}")

    cells = defaultdict(list)
    for dist, low3, prediff, allowed, extras in analyzed:
        if allowed == "UNEXPLAINED":
            continue
        cells[(dist, low3, prediff)].append((allowed, extras))

    print("\n=== cells with |prediff| <= 4 ===")
    print("cell (dist,low3,prediff): n, intersection-of-allowed, "
          "n-requiring-nonzero (0 excluded), n-requiring-zero (only 0)")
    mixed_cells = []
    for key in sorted(cells):
        dist, low3, prediff = key
        if abs(prediff) > 4:
            continue
        group = cells[key]
        inter = frozenset(OFFSETS)
        for allowed, _ in group:
            inter &= allowed
        need_nonzero = sum(1 for allowed, _ in group if 0 not in allowed)
        # "pinned to zero": allows 0 but excludes every nonzero candidate
        # that some fire row in the same cell needs -- approximate as
        # excluding both -1 and +1
        pinned = sum(1 for allowed, _ in group
                     if 0 in allowed and -1 not in allowed and 1 not in allowed)
        tag = ""
        if need_nonzero and need_nonzero != len(group) and pinned:
            tag = "  <-- MIXED"
            mixed_cells.append(key)
        print(f"  d={dist} low3={low3} pd={prediff:+d}: n={len(group):5d} "
              f"inter={sorted(inter) if inter else '{}'} "
              f"need!=0: {need_nonzero:4d}  pinned0: {pinned:5d}{tag}")

    print("\n=== far cells sanity: any need!=0 with |prediff|>4? ===")
    bad = 0
    for (dist, low3, prediff), group in cells.items():
        if abs(prediff) <= 4:
            continue
        n = sum(1 for allowed, _ in group if 0 not in allowed)
        bad += n
    print(f"  rows requiring nonzero offset outside |prediff|<=4: {bad}")

    for key in mixed_cells[:6]:
        dist, low3, prediff = key
        print(f"\n=== drill-down mixed cell d={dist} low3={low3} "
              f"pd={prediff:+d} ===")
        print("  (ud, u5d, rud, bit_above_lane, rs_bit0, model_payload) "
              "-> allowed offsets")
        for allowed, extras in sorted(cells[key],
                                      key=lambda g: (0 in g[0], g[1]))[:40]:
            kind = "FIRE" if 0 not in allowed else \
                   ("pinned" if -1 not in allowed and 1 not in allowed else "loose")
            print(f"    {extras} -> {sorted(allowed)} [{kind}]")


if __name__ == "__main__":
    main()
