#!/usr/bin/env python3
"""h437: extract the conditional product-increment gates G_R and G_L.

Context (see notes/skylake-comparison.md, h432-h435): every remaining
FCOS/FSIN one-ulp miss is explained by the silicon conditionally rounding
one of the two terminal reconstruction products UP (increment of the
67-bit chopped product) instead of chopping.  This script:

  1. loads the terminal-operation traces and hardware captures for the
     four hostile FCOS sets plus the h422 corpus;
  2. labels every row:  does incrementing the right product (R+1) or the
     left product (L+1) make the model match hardware in all three
     rounding modes?  Rows already exact under plain chop are negative
     examples (the gate must not fire where an increment would break
     them); rows fixed by R+1 are positive examples for G_R; rows fixed
     only by L+1 are positive examples for G_L;
  3. computes features of each product's OWN generation state (the
     discarded field of the 134-bit -> 67-bit chop, the retained low
     bits, the operand low bits) — the physically available inputs of a
     rounding decision at the multiplier output;
  4. verifies the positive/negative sets are separable (no feature
     vector appears on both sides), then searches for a small decision
     tree that states the gate explicitly.

Run from a directory containing h412/ (traces), h422/ (corpus),
captures/skylake-fcos-*/ (hardware status files).
"""
from collections import Counter
from multiprocessing import Pool

ROUNDING_MODES = ("rn", "rd", "ru")
HOSTILE_SETS = [
    ("h363", "captures/skylake-fcos-h363", "h412/h363_trace.txt"),
    ("h372", "captures/skylake-fcos-h372", "h412/h372_trace.txt"),
    ("h380", "captures/skylake-fcos-h380", "h412/h380_trace.txt"),
    ("h384", "captures/skylake-fcos-h384", "h412/h384_trace.txt"),
]


def parse_trace_line(line):
    """One COS_CARRIER debug line -> dict of name=value tokens."""
    fields = {}
    for token in line.split()[1:]:
        name, value = token.split("=")
        fields[name] = value
    return fields


def chop_to_67_bits(signed_value, scale):
    """Truncate a signed integer to 67 significant bits (round toward zero),
    returning (signed_mantissa, adjusted_exponent)."""
    negative = signed_value < 0
    magnitude = -signed_value if negative else signed_value
    shift = max(magnitude.bit_length() - 67, 0)
    magnitude >>= shift
    return (-magnitude if negative else magnitude), scale + shift


def final_cosine_result(correction, corr_exponent, mode):
    """Architectural 64-bit rounding of (1 + correction); returns the
    result significand exactly as the hardware capture reports it."""
    numerator = (1 << -corr_exponent) + correction
    shift = numerator.bit_length() - 64
    if shift <= 0:
        return numerator << -shift
    kept = numerator >> shift
    remainder = numerator & ((1 << shift) - 1)
    half = 1 << (shift - 1)
    round_up = 0
    if mode == "rn":
        round_up = 1 if (remainder > half or (remainder == half and kept & 1)) else 0
    elif mode == "ru":
        round_up = 1 if remainder else 0
    kept += round_up
    if kept >> 64:
        kept >>= 1
    return kept


def load_labeled_rows():
    """All active rows: (trace fields, hardware significands per mode)."""
    rows = []
    for _, capture_dir, trace_path in HOSTILE_SETS:
        traces = open(trace_path).read().splitlines()
        hardware = {
            mode: [line.split() for line in
                   open(f"{capture_dir}/fcos_{mode}_status.txt")]
            for mode in ROUNDING_MODES
        }
        for i, line in enumerate(traces):
            fields = parse_trace_line(line)
            if fields["active"] != "1":
                continue
            rows.append((fields, {m: int(hardware[m][i][2], 16)
                                  for m in ROUNDING_MODES}))
    traces = open("h422/selected_traces.txt").read().splitlines()
    hardware = {m: [line.split() for line in open(f"h422/hw_{m}.txt")]
                for m in ROUNDING_MODES}
    for i, line in enumerate(traces):
        rows.append((parse_trace_line(line),
                     {m: int(hardware[m][i][2], 16) for m in ROUNDING_MODES}))
    return rows


def product_features(full_product, chopped_mantissa, multiplicand, multiplier):
    """Features physically available when the multiplier output is chopped:
    the discarded-field structure and the low bits of the retained result
    and of the two operands."""
    shift = max(full_product.bit_length() - 67, 0)
    discarded = full_product & ((1 << shift) - 1)
    half = 1 << (shift - 1) if shift else 0
    top16 = (discarded >> (shift - 16)) if shift >= 16 else discarded << (16 - shift)
    return {
        "disc_width": shift,
        "above_half": 1 if discarded > half else 0,
        "exactly_half": 1 if discarded == half else 0,
        "disc_top16": int(top16) & 0xFFFF,
        "disc_nonzero": 1 if discarded else 0,
        "sticky_below_guard": (1 if (discarded & (half - 1)) else 0) if half else 0,
        "kept_low8": chopped_mantissa & 0xFF,
        "multiplicand_low3": multiplicand & 7,
        "multiplier_low3": multiplier & 7,
    }


def label_one_row(row):
    """Return (features_R, label_R, features_L, label_L) for one row.
    Labels: 1 = the gate must fire, 0 = must not fire, -1 = don't care."""
    fields, hw_results = row
    payload = int(fields["payload"])
    left_e2, right_e2 = int(fields["le2"]), int(fields["re2"])
    left_sig, right_sig = int(fields["ls"], 16), int(fields["rs"], 16)
    left_sign, right_sign = int(fields["lsign"]), int(fields["rsign"])
    square, odd_chain = int(fields["mul"], 16), int(fields["lf"], 16)
    fourth, even_chain = int(fields["f4"], 16), int(fields["rf"], 16)

    def model_matches_hardware(ls_value, rs_value):
        scale = min(left_e2, right_e2)
        if payload:
            scale = min(scale, left_e2 - 8)
        accumulator = (-1 if left_sign else 1) * (ls_value << (left_e2 - scale)) \
                    + (-1 if right_sign else 1) * (rs_value << (right_e2 - scale))
        if payload:
            accumulator += (-1 if left_sign else 1) * (payload << (left_e2 - 8 - scale))
        corr, corr_e = chop_to_67_bits(accumulator, scale)
        return all(final_cosine_result(corr, corr_e, m) == hw_results[m]
                   for m in ROUNDING_MODES)

    plain_ok = model_matches_hardware(left_sig, right_sig)
    right_up_ok = model_matches_hardware(left_sig, right_sig + 1)
    left_up_ok = model_matches_hardware(left_sig + 1, right_sig)

    feats_R = product_features(fourth * even_chain, right_sig, fourth, even_chain)
    feats_L = product_features(square * odd_chain, left_sig, square, odd_chain)

    # Right gate takes priority: rows fixed by R+1 are R-positives and
    # don't constrain the left gate's positive side.
    label_R = 1 if (not plain_ok and right_up_ok) else (0 if (plain_ok and not right_up_ok) else -1)
    label_L = 1 if (not plain_ok and left_up_ok and not right_up_ok) else (0 if (plain_ok and not left_up_ok) else -1)
    return feats_R, label_R, feats_L, label_L


FEATURE_ORDER = ["disc_width", "above_half", "exactly_half", "disc_top16",
                 "disc_nonzero", "sticky_below_guard", "kept_low8",
                 "multiplicand_low3", "multiplier_low3"]


def learn_tree(examples, depth, path, beam=3):
    """Small decision tree over (feature_tuple, label) examples with a
    lookahead beam; every leaf must be pure FIRE or pure NOFIRE."""
    labels = {label for _, label in examples}
    if labels <= {0}:
        return [(path, "NOFIRE", len(examples))]
    if labels <= {1}:
        return [(path, "FIRE", len(examples))]
    if depth == 0:
        return None
    candidates = []
    n_features = len(examples[0][0])
    for fi in range(n_features):
        for threshold in sorted({f[fi] for f, _ in examples})[1:]:
            low = [e for e in examples if e[0][fi] < threshold]
            high = [e for e in examples if e[0][fi] >= threshold]
            mixed = sum(1 for part in (low, high)
                        if {lbl for _, lbl in part} >= {0, 1})
            candidates.append((mixed, -min(len(low), len(high)),
                               fi, threshold, low, high))
    candidates.sort(key=lambda c: (c[0], c[1]))
    for mixed, _, fi, threshold, low, high in candidates[:beam]:
        name = FEATURE_ORDER[fi]
        low_tree = learn_tree(low, depth - 1, path + [f"{name}<{threshold}"], beam)
        if low_tree is None:
            continue
        high_tree = learn_tree(high, depth - 1, path + [f"{name}>={threshold}"], beam)
        if high_tree is not None:
            return low_tree + high_tree
    return None


def main():
    with Pool(8) as pool:
        labeled = pool.map(label_one_row, load_labeled_rows(), chunksize=2000)
    for gate_name, fi, li in (("G_R (right product)", 0, 1),
                              ("G_L (left product)", 2, 3)):
        fire = Counter()
        nofire = Counter()
        for row in labeled:
            feats, label = row[fi], row[li]
            vec = tuple(feats[k] for k in FEATURE_ORDER)
            if label == 1:
                fire[vec] += 1
            elif label == 0:
                nofire[vec] += 1
        conflicts = set(fire) & set(nofire)
        print(f"{gate_name}: fire-rows={sum(fire.values())} "
              f"nofire-rows={sum(nofire.values())} "
              f"conflicting-vectors={len(conflicts)}")
        if conflicts:
            for vec in list(conflicts)[:3]:
                print(f"  conflict {dict(zip(FEATURE_ORDER, vec))} "
                      f"(fire {fire[vec]}, nofire {nofire[vec]})")
            continue
        examples = [(v, 1) for v in fire] + [(v, 0) for v in nofire]
        for depth in (2, 3, 4, 5, 6, 8):
            result = learn_tree(examples, depth, [])
            if result:
                n_fire_leaves = sum(1 for _, kind, _ in result if kind == "FIRE")
                print(f"  tree found at depth {depth}: {len(result)} leaves, "
                      f"{n_fire_leaves} FIRE leaves")
                for path, kind, count in result:
                    if kind == "FIRE":
                        print(f"    FIRE ({count} vectors): {' AND '.join(path)}")
                break
        else:
            print("  separable but no tree up to depth 8 (needs richer split types)")


if __name__ == "__main__":
    main()
