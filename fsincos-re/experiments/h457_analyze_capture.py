#!/usr/bin/env python3
"""h457: analyze the h456 truth-table capture — input-bit sensitivity
of the borrow phenomenon.

Primary statistic (defined for EVERY captured line, no classification
needed): fire-ness = "hardware differs from the bit-exact model in at
least one rounding mode".  The model is exact on all corpora except the
borrow fires, so a firing neighbor is a fresh instance of the
phenomenon.  Per flipped input-bit position b and base role
(fire/control), we measure the neighbor fire rate.  Interpretation:

  - If neighbors of fire bases keep firing at elevated rates when low
    bits flip but fall to the corpus base rate (~0.1%) for high bits,
    the deciding state is a smooth/low-order function of the input —
    and the bit position where persistence dies measures the gate's
    correlation length in input space.
  - A flat profile at base rate for ALL bits means hash-like
    sensitivity: the gate reads state that any input perturbation
    scrambles.
  - Any bit whose flip PRESERVES fire-ness near 100 percent is directly
    upstream of the gate (or outside its support).

Secondary: for the (rare) neighbors that are themselves classifiable by
the half-line offset probe, per-bit borrow-toggle counts among
base/neighbor pairs.

Usage:
  python3 h457_analyze_capture.py            # real captures in
                                             # h456_package/cos_*_status.txt
  python3 h457_analyze_capture.py --mock     # synthesize captures from
                                             # the baseline model to
                                             # smoke-test the pipeline
                                             # (expected: zero fires,
                                             # zero toggles)

Run from /tmp/stageA.
"""
import os
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool

from h437_gate_extraction import chop_to_67_bits, final_cosine_result
from h453_chain_variants import (
    C6_1, C6_2, C6_3, C6_4, C6_5, C6_6, mul_round, build_chain)

PKG = "h456_package"
PROBE = list(range(-8, 9))
MODES = ("rn", "rd", "ru")
EXP_BIAS_AT_M = 16446


def model_terminal(se, sig):
    """Input -> (active, offset_results).

    offset_results[off][mode] is the model's 64-bit result significand
    with the payload perturbed by `off` units.  For payload-inactive
    rows the payload is 0 (the model's own rule) and only offset 0 is
    populated — enough for the fire-ness statistic; the offset probe
    (classification) is only meaningful for active rows.  Includes the
    two ported Round-52 collision patches, matching the C model."""
    e2m = se - EXP_BIAS_AT_M
    mag = (0, e2m, sig)
    square = mul_round(mag, mag, 67, "chop")
    fourth = mul_round(square, square, 67, "chop")
    negative = build_chain(fourth, C6_5, C6_3, C6_1, 67, 64, "rn",
                           False, False, False)
    positive = build_chain(fourth, C6_6, C6_4, C6_2, 67, 64, "rn",
                           False, False, False)
    left = mul_round(square, negative, 67, "chop")
    right = mul_round(fourth, positive, 67, "chop")
    product = square[2] * negative[2]
    shift = max(product.bit_length() - 67, 0)
    discarded = product & ((1 << shift) - 1) if shift > 0 else 0
    ud = (discarded << 3) >> shift if shift > 0 else 0
    u5d = (discarded << 5) >> shift if shift > 0 else 0
    rproduct = fourth[2] * positive[2]
    rshift = max(rproduct.bit_length() - 67, 0)
    rdisc = rproduct & ((1 << rshift) - 1) if rshift > 0 else 0
    rud = (rdisc << 1) >> rshift if rshift > 0 else 0
    low3 = square[2] & 7
    distance = abs(left[1] - right[1])
    active = 1 if (low3 and (ud or (distance == 7 and u5d))) else 0
    payload = low3 + 8 - distance if active else 0
    if active and distance == 10 and low3 == 6 and rud:
        lane_shift = (left[1] - 8) - right[1]
        lane = (right[2] >> lane_shift) if lane_shift >= 0 \
            else (right[2] << -lane_shift)
        difference = ((lane & 0xFF) - payload) & 0xFF
        if difference >= 128:
            difference -= 256
        if difference == -2:
            payload = lane & 0xFF
    if active and distance == 8 and low3 == 7 and ud >= 3:
        lane_shift = (left[1] - 8) - right[1]
        lane = (right[2] >> lane_shift) if lane_shift >= 0 \
            else (right[2] << -lane_shift)
        difference = ((lane & 0xFF) - payload) & 0xFF
        if difference >= 128:
            difference -= 256
        if difference == 0:
            payload -= 1
    scale = min(left[1], right[1])
    if payload and left[1] - 8 < scale:
        scale = left[1] - 8
    A = left[2] << (left[1] - scale)
    B = right[2] << (right[1] - scale)
    unit = left[1] - 8 - scale
    offset_results = {}
    for off in (PROBE if active else [0]):
        pay = payload + off if active else 0
        acc = (-1 if left[0] else 1) * A + (-1 if right[0] else 1) * B
        if pay:
            acc += (-1 if left[0] else 1) * (pay << unit)
        corr, corr_e = chop_to_67_bits(acc, scale)
        offset_results[off] = {m: final_cosine_result(corr, corr_e, m)
                               for m in MODES}
    return active, offset_results


def classify(offset_results, hw_sigs):
    """Half-line classification -> (b_hw, theta, fire) or None."""
    allowed = [off for off in PROBE
               if all(offset_results[off][m] == hw_sigs[m] for m in MODES)]
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
    return b_hw, theta, fire


def process_line(job):
    """-> (line_no, target, bit, fires, classification-or-None)."""
    line_no, target, bit, se, sig, hw_sigs = job
    active, offset_results = model_terminal(se, sig)
    fires = 0 if all(offset_results[0][m] == hw_sigs[m]
                     for m in MODES) else 1
    cls = classify(offset_results, hw_sigs) if active else None
    return (line_no, target, bit, fires, cls)


def load_manifest():
    entries = []
    with open(f"{PKG}/manifest.tsv") as fh:
        fh.readline()
        for line in fh:
            n, target, bit, se, sig = line.split()
            entries.append((int(n), target, int(bit),
                            int(se, 16), int(sig, 16)))
    return entries


def load_captures(mock, entries):
    """-> list of {mode: result_sig} per manifest line."""
    if mock:
        out = []
        for _, _, _, se, sig in entries:
            _, offset_results = model_terminal(se, sig)
            out.append({m: offset_results[0][m] for m in MODES})
        return out
    captures = {}
    for mode in MODES:
        with open(f"{PKG}/cos_{mode}_status.txt") as fh:
            captures[mode] = fh.read().splitlines()
    out = []
    for i in range(len(entries)):
        sigs = {}
        for mode in MODES:
            tokens = captures[mode][i].split()
            sigs[mode] = int(tokens[2], 16) if tokens[0] == "OK" else -1
        out.append(sigs)
    return out


def main():
    mock = "--mock" in sys.argv
    entries = load_manifest()
    print(f"manifest lines: {len(entries)}  mode: "
          f"{'MOCK (model as hardware)' if mock else 'real captures'}")
    hw = load_captures(mock, entries)
    jobs = [(n, t, b, se, sig, hw[i])
            for i, (n, t, b, se, sig) in enumerate(entries)]
    with Pool(8) as pool:
        results = pool.map(process_line, jobs, chunksize=200)

    role_of = {}
    with open(f"{PKG}/targets.tsv") as fh:
        fh.readline()
        for line in fh:
            cols = line.split()
            role_of[cols[0]] = cols[1]

    by_target = defaultdict(dict)
    for line_no, target, bit, fires, cls in results:
        by_target[target][bit] = (fires, cls)

    # primary: per-bit neighbor fire rate by base role
    per_bit = defaultdict(Counter)
    pair_bit = defaultdict(Counter)
    for target, group in by_target.items():
        role = role_of[target]
        base = group.get(-1)
        for bit in range(63):
            nb = group.get(bit)
            if nb is None:
                continue
            per_bit[bit][f"{role}_n"] += 1
            per_bit[bit][f"{role}_fire"] += nb[0]
            if base and base[1] is not None and nb[1] is not None:
                pair_bit[bit]["pair"] += 1
                if nb[1][0] != base[1][0]:
                    pair_bit[bit]["toggle"] += 1

    n_fire_lines = sum(r[3] for r in results)
    print(f"total firing lines: {n_fire_lines}/{len(results)}")
    print("\nbit  fireN  fires(rate)      ctrlN  fires(rate)     "
          "cls-pairs toggles")
    for bit in range(63):
        c, p = per_bit[bit], pair_bit[bit]
        fn, ff = c["fire_n"], c["fire_fire"]
        cn, cf = c["control_n"], c["control_fire"]
        print(f"{bit:3d}  {fn:5d}  {ff:4d} ({ff / max(fn, 1):6.3f})  "
              f"{cn:6d}  {cf:4d} ({cf / max(cn, 1):6.3f})  "
              f"{p['pair']:6d} {p['toggle']:5d}")

    out = f"{PKG}/per_bit{'_mock' if mock else ''}.tsv"
    with open(out, "w") as fh:
        fh.write("bit\tfire_n\tfire_fires\tcontrol_n\tcontrol_fires\t"
                 "cls_pairs\tcls_toggles\n")
        for bit in range(63):
            c, p = per_bit[bit], pair_bit[bit]
            fh.write(f"{bit}\t{c['fire_n']}\t{c['fire_fire']}\t"
                     f"{c['control_n']}\t{c['control_fire']}\t"
                     f"{p['pair']}\t{p['toggle']}\n")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
