#!/usr/bin/env python3
"""h454: predict the borrow bit from same-instruction datapath state.

The h441-h453 campaign proved the 310 fires are +-1..2 lowest-unit
errors in the terminal subtract, decided by state outside every
arithmetic reformulation.  Prime remaining suspects: physical state the
subtract inherits from the SAME instruction's earlier datapath steps
(stale carries / latched rounding state), and fine carry-chain
structure of the subtract operands themselves.

Using the h453 bit-exact replica, compute per constrained row:
  - each chain add's guard, sticky, and round-up outcome (4 adds);
  - each product chop's guard/sticky (square, fourth, left, right);
  - terminal subtract: theta, distance-to-boundary parity, carry-run
    lengths up/down from the payload position, low nibbles of the
    aligned operands at 4-bit block boundaries;
and scan all of them (plus pairs with theta/dist/low3) for separation
of the fire bit.

Run from /tmp/stageA.
"""
import pickle
from collections import Counter, defaultdict
from multiprocessing import Pool

from h437_gate_extraction import (
    ROUNDING_MODES, load_labeled_rows, chop_to_67_bits, final_cosine_result)
from h453_chain_variants import (
    C6_1, C6_2, C6_3, C6_4, C6_5, C6_6, recover_m, mul_round)

PROBE = list(range(-8, 9))


def normalize_state(sign, mag, scale, bits, mode):
    """Like h453.normalize but also returns (guard, sticky, rounded_up)."""
    if mag == 0:
        return (sign, 0, 0), (0, 0, 0)
    sh = mag.bit_length() - bits
    if sh <= 0:
        return (sign, scale + sh, mag << -sh), (0, 0, 0)
    top = mag >> sh
    guard = (mag >> (sh - 1)) & 1
    below = mag & ((1 << (sh - 1)) - 1)
    up = 0
    if mode == "rn" and guard and (below or (top & 1)):
        top += 1
        up = 1
        if top >> bits:
            top >>= 1
            sh += 1
    return (sign, scale + sh, top), (guard, 1 if below else 0, up)


def mul_state(a, b, bits, mode):
    return normalize_state(a[0] ^ b[0], a[2] * b[2], a[1] + b[1], bits, mode)


def add_state(left, right, bits, mode):
    scale = min(left[1], right[1])
    acc = (-1 if left[0] else 1) * (left[2] << (left[1] - scale)) \
        + (-1 if right[0] else 1) * (right[2] << (right[1] - scale))
    sign = 1 if acc < 0 else 0
    return normalize_state(sign, abs(acc), scale, bits, mode)


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
    fire = 1 if (1 if 0 >= theta else 0) != b_hw else 0

    # replica intermediates (validated pipeline only)
    square_sig = int(fields["mul"], 16)
    m = recover_m(square_sig)
    if m is None:
        return None
    lf_t, rf_t = int(fields["lf"], 16), int(fields["rf"], 16)
    states = None
    for e2m in (-66, -67, -65, -68, -64, -69, -63):
        mag = (0, e2m, m)
        sq, st_sq = mul_state(mag, mag, 67, "chop")
        f4, st_f4 = mul_state(sq, sq, 67, "chop")
        if sq[2] != square_sig:
            return None
        p1, st_p1 = mul_state(f4, C6_5, 67, "chop")
        n_mid, st_a1 = add_state(C6_3, p1, 64, "rn")
        p2, st_p2 = mul_state(f4, n_mid, 67, "chop")
        neg, st_a2 = add_state(C6_1, p2, 64, "rn")
        p3, st_p3 = mul_state(f4, C6_6, 67, "chop")
        p_mid, st_a3 = add_state(C6_4, p3, 64, "rn")
        p4, st_p4 = mul_state(f4, p_mid, 67, "chop")
        pos, st_a4 = add_state(C6_2, p4, 64, "rn")
        if neg[2] == lf_t and pos[2] == rf_t:
            states = (st_sq, st_f4, st_p1, st_a1, st_p2, st_a2,
                      st_p3, st_a3, st_p4, st_a4)
            break
    if states is None:
        return (b_hw, theta, fire, None)

    # terminal subtract carry structure
    diffAB = A - B + (prepay << unit)
    run_up = 0
    probe_bits = diffAB >> unit
    while (probe_bits >> run_up) & 1:
        run_up += 1
    run_zero = 0
    while run_zero < 40 and not ((probe_bits >> run_zero) & 1):
        run_zero += 1

    feats = {"dist": dist, "low3": low3, "prepay": prepay,
             "theta": theta,
             "run_up": min(run_up, 15), "run_zero": min(run_zero, 15),
             "B_low4": (B >> unit) & 0xF, "A_low4": (A >> unit) & 0xF}
    names = ["sq", "f4", "p1", "a1", "p2", "a2", "p3", "a3", "p4", "a4"]
    for name, (guard, sticky, up) in zip(names, states):
        feats[f"{name}_g"] = guard
        feats[f"{name}_s"] = sticky
        feats[f"{name}_u"] = up
    return (b_hw, theta, fire, feats)


def main():
    rows = load_labeled_rows()
    with Pool(8) as pool:
        results = [r for r in pool.map(analyze_row, rows, chunksize=2000)
                   if r is not None]
    with_states = [r for r in results if r[3] is not None]
    fires = sum(r[2] for r in with_states)
    print(f"constrained rows: {len(results)}, with replica states: "
          f"{len(with_states)}, fires among them: {fires}")

    zone = [(r[2], r[3]) for r in with_states if -3 <= r[1] <= 3]
    print(f"zone rows: {len(zone)}, fires: {sum(f for f, _ in zone)}")
    names = list(zone[0][1])
    scored = []
    for name in names:
        table = defaultdict(Counter)
        for fire, feats in zone:
            table[feats[name]][fire] += 1
        impure = sum(min(c[0], c[1]) for c in table.values())
        scored.append((impure, name))
    scored.sort()
    base = min(sum(f for f, _ in zone), len(zone) - sum(f for f, _ in zone))
    print(f"baseline inseparable: {base}")
    for impure, name in scored[:20]:
        print(f"  {name:10s}: inseparable {impure}")

    # pairs with theta (the natural conditioning)
    print("\npairs (theta x feature):")
    scored2 = []
    for name in names:
        if name == "theta":
            continue
        table = defaultdict(Counter)
        for fire, feats in zone:
            table[(feats["theta"], feats[name])][fire] += 1
        impure = sum(min(c[0], c[1]) for c in table.values())
        scored2.append((impure, name))
    scored2.sort()
    for impure, name in scored2[:15]:
        print(f"  theta x {name:10s}: inseparable {impure}")

    with open("h454_rows.pkl", "wb") as fh:
        pickle.dump(with_states, fh)
    print("\nsaved h454_rows.pkl")


if __name__ == "__main__":
    main()
