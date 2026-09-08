#!/usr/bin/env python3
"""h446: the single-borrow-bit reframing of the collision gate.

h444/h445 proved every informative row constrains exactly ONE bit: on
which side of a chop-boundary crossing the hardware's payload quantity
lies (equivalently: whether the borrow out of the payload byte in the
terminal subtract |acc| = A - B + P propagated into the retained bits).
The historical "add / carry-suppressed merge / lane capture" trichotomy
collapses into this bit: fires with the boundary above the model payload
are borrow suppressions, fires with it at/below are borrow injections.

Per row this script probes payload offsets in [-8, 8], locates the
boundary empirically (the allowed set must be a contiguous run touching
one end of the probe window), labels the row high-side/low-side, and
mines predictors of the FIRE bit (model on the wrong side), emphasizing
accumulator-subtract carry structure no earlier basis included.

Run from /tmp/stageA.
"""
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
    unit = left_e2 - 8 - scale          # payload bit position in acc units

    def matches(payload_value):
        corr, corr_e = chop_to_67_bits(-(A - B + (payload_value << unit)),
                                       scale)
        return all(final_cosine_result(corr, corr_e, m) == hw_results[m]
                   for m in ROUNDING_MODES)

    allowed = [off for off in PROBE if matches(prepay + off)]
    if not allowed:
        return None                     # unexplained in window (none seen)
    if len(allowed) == len(PROBE):
        return "BLIND"
    lo_run = allowed[0] == PROBE[0] and allowed == list(
        range(PROBE[0], allowed[-1] + 1))
    hi_run = allowed[-1] == PROBE[-1] and allowed == list(
        range(allowed[0], PROBE[-1] + 1))
    if lo_run and not hi_run:
        b_hw, theta = 0, allowed[-1] + 1    # hw on low side; boundary above
    elif hi_run and not lo_run:
        b_hw, theta = 1, allowed[0]         # hw on high side; boundary at lo
    else:
        return "MIXED"
    b_model = 1 if 0 >= theta else 0
    fire = 1 if b_hw != b_model else 0

    lane_shift = dist - 8
    lane = ((right_sig >> lane_shift) if lane_shift >= 0
            else (right_sig << -lane_shift)) & 0xFF
    prediff = (lane - prepay) & 0xFF
    if prediff >= 128:
        prediff -= 256

    diffAB = A - B
    byte_lo = (diffAB >> unit) & 0xFF
    byte_hi = (diffAB >> (unit + 8)) & 0xFF
    below = diffAB & ((1 << unit) - 1) if unit else 0
    run = 0
    probe_bits = diffAB >> unit
    while (probe_bits >> run) & 1:
        run += 1
    features = {
        "dist": dist, "low3": low3, "pd": prediff, "prepay": prepay,
        "theta": theta,
        "lane": lane, "ud": int(fields["ud"]), "u5d": int(fields["u5d"]),
        "rud": int(fields["rud"]),
        "byte_lo": byte_lo, "byte_hi": byte_hi,
        "run": min(run, 15),
        "below_nz": 1 if below else 0,
        "rs_low8": right_sig & 0xFF,
        "rs_next8": (right_sig >> 8) & 0xFF,
        "ls_low8": left_sig & 0xFF,
        "mul_low8": int(fields["mul"], 16) & 0xFF,
        "lf_low8": int(fields["lf"], 16) & 0xFF,
        "rf_low8": int(fields["rf"], 16) & 0xFF,
        "f4_low8": int(fields["f4"], 16) & 0xFF,
    }
    return b_hw, b_model, fire, features


def main():
    rows = load_labeled_rows()
    with Pool(8) as pool:
        results = pool.map(analyze_row, rows, chunksize=2000)
    blind = sum(1 for r in results if r == "BLIND")
    mixed = sum(1 for r in results if r == "MIXED")
    constrained = [r for r in results
                   if r not in (None, "BLIND", "MIXED")]
    fires = [r for r in constrained if r[2]]
    print(f"constrained={len(constrained)} blind={blind} mixed={mixed} "
          f"fires={len(fires)}")
    print(f"(b_model, b_hw): "
          f"{dict(Counter((r[1], r[0]) for r in constrained))}")
    print(f"fires by theta: "
          f"{dict(sorted(Counter(r[3]['theta'] for r in fires).items()))}")
    print(f"all constrained by theta: "
          f"{dict(sorted(Counter(r[3]['theta'] for r in constrained).items()))}")

    # near-zone: rows whose boundary is within +-3 of the model payload —
    # the only place the gate can act
    zone = [(r[2], r[3]) for r in constrained if -3 <= r[3]["theta"] <= 3]
    print(f"\nzone rows (theta in [-3,3]): {len(zone)}, "
          f"fires: {sum(f for f, _ in zone)}")
    names = list(zone[0][1])
    print("single-feature inseparability (lower = better discriminator):")
    for name in names:
        table = defaultdict(Counter)
        for fire, feats in zone:
            table[feats[name]][fire] += 1
        impure = sum(min(c[0], c[1]) for c in table.values())
        print(f"  {name:10s}: {len(table):3d} values, inseparable: {impure}")

    print("\n=== fire rate by (theta, run) ===")
    table = defaultdict(Counter)
    for fire, feats in zone:
        table[(feats["theta"], feats["run"])][fire] += 1
    for key in sorted(table):
        c = table[key]
        print(f"  theta={key[0]:+d} run={key[1]:2d}: "
              f"fire {c[1]:4d} / {c[0] + c[1]:4d}")

    print("\n=== fire rate by (dist, theta) ===")
    table = defaultdict(Counter)
    for fire, feats in zone:
        table[(feats["dist"], feats["theta"])][fire] += 1
    for key in sorted(table):
        c = table[key]
        print(f"  dist={key[0]} theta={key[1]:+d}: "
              f"fire {c[1]:4d} / {c[0] + c[1]:4d}")

    import pickle
    with open("h446_zone.pkl", "wb") as fh:
        pickle.dump(zone, fh)
    print("\nzone rows saved to h446_zone.pkl")


if __name__ == "__main__":
    main()
