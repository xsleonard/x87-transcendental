#!/usr/bin/env python3
"""h442: can the conditional +1 live UPSTREAM of the terminal products?

h441 killed the truncated-array family, and h439 killed every
chop-boundary literal basis.  Both assumed the increment is generated at
the terminal product's own chop.  But the chain operands (rf, lf) and
the fourth power (f4 = chop67(mul^2), verified) are THEMSELVES chopped
products: a rare +1 at an upstream chop propagates to ~1 retained unit
of the terminal product, and the all-modes match test used for labeling
cannot tell `chop(a*b)+1` from `chop(a*(b+1))` when the two coincide.

This script, per fire row:
  1. tests which alternatives reproduce hardware in all three modes:
     product+1 (baseline), each operand+1, and both-products variants;
  2. reports whether the alternative is numerically identical to
     product+1 (indistinguishable) or a genuinely different value that
     ALSO matches (distinguishable support for upstream);
and across all rows:
  3. cross-tabulates fire/nofire against trace-level state the h437-h439
     bases never saw: dist, low3, ud/u5d/rud, payload, signs, exponent
     gaps, accumulator discarded (disc_hi), and the f4 upstream
     discarded fraction disc(mul^2).

Run from /tmp/stageA.
"""
from multiprocessing import Pool

from h437_gate_extraction import (
    ROUNDING_MODES, load_labeled_rows, chop_to_67_bits, final_cosine_result)


def chop67(value):
    shift = max(value.bit_length() - 67, 0)
    return value >> shift


def disc_frac(value):
    """Discarded fraction of the 67-bit chop of `value`, in [0, 1)."""
    shift = max(value.bit_length() - 67, 0)
    if shift == 0:
        return 0.0
    return (value & ((1 << shift) - 1)) / (1 << shift)


def analyze_row(row):
    fields, hw_results = row
    payload = int(fields["payload"])
    left_e2, right_e2 = int(fields["le2"]), int(fields["re2"])
    left_sig, right_sig = int(fields["ls"], 16), int(fields["rs"], 16)
    left_sign, right_sign = int(fields["lsign"]), int(fields["rsign"])
    square, odd_chain = int(fields["mul"], 16), int(fields["lf"], 16)
    fourth, even_chain = int(fields["f4"], 16), int(fields["rf"], 16)

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

    alternatives = None
    if label_R == 1 or label_L == 1:
        candidates = {
            "rs+1": (left_sig, right_sig + 1),
            "ls+1": (left_sig + 1, right_sig),
            "rf+1": (left_sig, chop67(fourth * (even_chain + 1))),
            "f4+1": (left_sig, chop67((fourth + 1) * even_chain)),
            "lf+1": (chop67(square * (odd_chain + 1)), right_sig),
            "mul+1": (chop67((square + 1) * odd_chain), right_sig),
            # mul feeds BOTH products (f4 = chop67(mul^2) -> right side)
            "mul+1both": (chop67((square + 1) * odd_chain),
                          chop67(chop67((square + 1) * (square + 1)) * even_chain)),
        }
        alternatives = {}
        for name, (lv, rv) in candidates.items():
            if matches(lv, rv):
                same = "=rs+1" if (lv, rv) == (left_sig, right_sig + 1) else \
                       "=ls+1" if (lv, rv) == (left_sig + 1, right_sig) else "DISTINCT"
                alternatives[name] = same
        if payload:
            for name, pay in (("pay-1", payload - 1), ("pay+1", payload + 1)):
                if matches(left_sig, right_sig, payload_value=pay):
                    alternatives[name] = "DISTINCT"

    features = {
        "dist": int(fields["dist"]),
        "low3": int(fields["low3"]),
        "ud": int(fields["ud"]),
        "u5d": int(fields["u5d"]),
        "rud": int(fields["rud"]),
        "payload": payload,
        "lsign": left_sign,
        "rsign": right_sign,
        "active": int(fields["active"]),
        "rdisc_frac": disc_frac(fourth * even_chain),
        "ldisc_frac": disc_frac(square * odd_chain),
        "f4disc_frac": disc_frac(square * square),
        "disc_hi_top4": int(fields["disc_hi"], 16) >> 60,
        "rdisc_hi_top4": int(fields["rdisc_hi"], 16) >> 60,
    }
    return label_R, label_L, alternatives, features


def summarize(name, rows, keys):
    print(f"  {name} (n={len(rows)}):")
    for key in keys:
        values = [r[key] for r in rows]
        if isinstance(values[0], float):
            values.sort()
            n = len(values)
            print(f"    {key}: min={values[0]:.4f} "
                  f"q25={values[n // 4]:.4f} med={values[n // 2]:.4f} "
                  f"q75={values[3 * n // 4]:.4f} max={values[-1]:.4f}")
        else:
            from collections import Counter
            top = Counter(values).most_common(8)
            print(f"    {key}: {top}")


def main():
    rows = load_labeled_rows()
    with Pool(8) as pool:
        analyzed = pool.map(analyze_row, rows, chunksize=2000)

    fire_R = [a for a in analyzed if a[0] == 1]
    fire_L = [a for a in analyzed if a[1] == 1]
    nofire_R = [a for a in analyzed if a[0] == 0]
    nofire_L = [a for a in analyzed if a[1] == 0]
    print(f"rows: fire_R={len(fire_R)} fire_L={len(fire_L)} "
          f"nofire_R={len(nofire_R)} nofire_L={len(nofire_L)}\n")

    print("=== operand-increment alternatives on fire rows ===")
    from collections import Counter
    for side, group in (("R", fire_R), ("L", fire_L)):
        tally = Counter()
        for _, _, alternatives, _ in group:
            for name, kind in alternatives.items():
                tally[f"{name}[{kind}]"] += 1
        print(f"  fire_{side} (n={len(group)}): "
              f"{dict(sorted(tally.items(), key=lambda kv: -kv[1]))}")

    keys = ["dist", "low3", "ud", "u5d", "rud", "payload", "lsign", "rsign",
            "active", "rdisc_frac", "ldisc_frac", "f4disc_frac",
            "disc_hi_top4", "rdisc_hi_top4"]
    print("\n=== trace-level state, fire vs informative nofire ===")
    import random
    rng = random.Random(442)
    summarize("fire_R", [a[3] for a in fire_R], keys)
    summarize("nofire_R", [a[3] for a in
                           rng.sample(nofire_R, min(4000, len(nofire_R)))], keys)
    summarize("fire_L", [a[3] for a in fire_L], keys)
    summarize("nofire_L", [a[3] for a in
                           rng.sample(nofire_L, min(4000, len(nofire_L)))], keys)
    active_nofire_L = [a[3] for a in nofire_L if a[3]["active"] == 1]
    summarize("nofire_L, active only",
              [f for f in rng.sample(active_nofire_L,
                                     min(4000, len(active_nofire_L)))], keys)


if __name__ == "__main__":
    main()
