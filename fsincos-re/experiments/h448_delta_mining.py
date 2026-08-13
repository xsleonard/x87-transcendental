#!/usr/bin/env python3
"""h448: mine the payload deviation delta.

Framing established by h444-h447: the hardware terminal payload equals
the model's prepay = low3+8-dist plus a state-dependent deviation delta
in (-3, +3); each constrained row yields one inequality delta >= theta
or delta < theta, where theta is the row's empirically-located
chop-boundary offset.  Guard bits and lane arithmetic are excluded; the
open question is what state determines delta.

This script builds the per-row delta-constraint dataset with a rich
feature panel (including both terminal products' recomputed discarded
fields and the fourth power's own generation state mul^2), then:
  1. tabulates fire direction by (dist, low3) - is the sign of delta
     window-determined?
  2. scans every feature for discrimination of sign(delta) on the
     exact-tie rows (theta == 0), where sign(delta) is directly visible;
  3. saves the dataset for deeper mining.

Run from /tmp/stageA.
"""
import pickle
from collections import Counter, defaultdict
from multiprocessing import Pool

from h437_gate_extraction import (
    ROUNDING_MODES, load_labeled_rows, chop_to_67_bits, final_cosine_result)

PROBE = list(range(-8, 9))


def disc_top16(full):
    shift = max(full.bit_length() - 67, 0)
    disc = full & ((1 << shift) - 1)
    return ((disc >> (shift - 16)) if shift >= 16
            else disc << (16 - shift)) & 0xFFFF, shift


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

    square, odd_chain = int(fields["mul"], 16), int(fields["lf"], 16)
    fourth, even_chain = int(fields["f4"], 16), int(fields["rf"], 16)
    ldisc16, _ = disc_top16(square * odd_chain)
    rdisc16, _ = disc_top16(fourth * even_chain)
    f4disc16, _ = disc_top16(square * square)

    feats = {
        "dist": dist, "low3": low3, "prepay": prepay,
        "ud": int(fields["ud"]), "u5d": int(fields["u5d"]),
        "rud": int(fields["rud"]), "payload": payload,
        "ls_low8": left_sig & 0xFF, "rs_low8": right_sig & 0xFF,
        "rs_next8": (right_sig >> 8) & 0xFF,
        "mul_low8": square & 0xFF, "lf_low8": odd_chain & 0xFF,
        "rf_low8": even_chain & 0xFF, "f4_low8": fourth & 0xFF,
        "ldisc_hi8": ldisc16 >> 8, "ldisc_lo8": ldisc16 & 0xFF,
        "rdisc_hi8": rdisc16 >> 8, "rdisc_lo8": rdisc16 & 0xFF,
        "f4disc_hi8": f4disc16 >> 8, "f4disc_lo8": f4disc16 & 0xFF,
        "mul_b3_7": (square >> 3) & 0x1F,
    }
    return b_hw, theta, feats


def feature_bits(feats):
    """Expand features into named binary literals."""
    bits = {}
    for name, value in feats.items():
        if name in ("dist", "low3", "prepay", "payload", "ud", "rud"):
            bits[name] = value            # keep small categoricals whole
            continue
        width = 8 if value < 256 else 16
        for b in range(width if name != "u5d" else 5):
            bits[f"{name}.{b}"] = (value >> b) & 1
    bits["u5d"] = feats["u5d"]
    return bits


def scan(rows, label_name):
    """Single-feature discrimination scan on (label, feats) rows."""
    print(f"\n=== scan: {label_name} (n={len(rows)}, "
          f"pos={sum(l for l, _ in rows)}) ===")
    names = list(feature_bits(rows[0][1]))
    scored = []
    for name in names:
        table = defaultdict(Counter)
        for label, feats in rows:
            table[feature_bits(feats)[name]][label] += 1
        impure = sum(min(c[0], c[1]) for c in table.values())
        scored.append((impure, name, dict(table)))
    scored.sort()
    base = min(sum(l for l, _ in rows), len(rows) - sum(l for l, _ in rows))
    print(f"  baseline inseparable: {base}")
    for impure, name, table in scored[:12]:
        detail = {k: (v.get(0, 0), v.get(1, 0))
                  for k, v in sorted(table.items())} if len(table) <= 10 else ""
        print(f"  {name:14s}: inseparable {impure:4d}  {detail}")


def main():
    rows = load_labeled_rows()
    with Pool(8) as pool:
        results = [r for r in pool.map(analyze_row, rows, chunksize=2000)
                   if r is not None]
    print(f"constrained rows: {len(results)}")

    # fire = model side wrong
    def fire_of(b_hw, theta):
        return 1 if ((1 if 0 >= theta else 0) != b_hw) else 0

    print("\n=== fire direction by (dist, low3) ===")
    table = defaultdict(Counter)
    for b_hw, theta, feats in results:
        if fire_of(b_hw, theta):
            direction = "up" if b_hw == 1 else "down"
        else:
            direction = "none"
        table[(feats["dist"], feats["low3"])][direction] += 1
    for key in sorted(table):
        c = table[key]
        print(f"  dist={key[0]} low3={key[1]}: up={c['up']:3d} "
              f"down={c['down']:3d} none={c['none']:4d}")

    # exact-tie rows: theta == 0 -> label = b_hw = [delta >= 0]
    ties = [(b_hw, feats) for b_hw, theta, feats in results if theta == 0]
    scan(ties, "sign(delta) on exact ties (1 = delta >= 0)")

    # theta=+1 rows: label = [delta >= 1]
    ones = [(b_hw, feats) for b_hw, theta, feats in results if theta == 1]
    scan(ones, "[delta >= 1] on theta=+1 rows")

    with open("h448_constraints.pkl", "wb") as fh:
        pickle.dump(results, fh)
    print("\nsaved h448_constraints.pkl")


if __name__ == "__main__":
    main()
