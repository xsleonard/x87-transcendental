#!/usr/bin/env python3
"""h441: test the truncated-Booth-multiplier hypothesis directly.

h439 proved the gates G_R/G_L are deterministic over product-generation
state but NOT expressible over chop-boundary literal bases (covers grow
with data).  The handoff's priority-1 basis is Booth-recoding digits;
this script tests the physical mechanism those digits would encode: the
hardware multiplier does not form the full 134-bit product and chop it —
it TRUNCATES the partial-product array at some column C (bits below C
are never formed), possibly mishandling the two's-complement correction
bits of negative Booth digits and adding a constant compensation.  Under
that hypothesis the observed conditional +1 on the retained 67-bit unit
is not a "gate" at all: it is the deterministic difference between the
truncated-array sum and the ideal chopped product.

Model, per config (radix, recoded operand, C, correction mode, K):
  product a*b with b recoded (radix 2 = plain AND array, 4, or 8);
  PP_i = d_i * a * 2^(rb*i); negative PPs are ones-complemented over a
  W-bit field with a +1 correction at column rb*i;
  every PP has its bits below column C zeroed (never formed);
  corrections with rb*i < C are dropped / lumped at C / kept (variants);
  compensation constant K * 2^(C-1) is added.
Prediction: delta = (trunc_sum >> shift) - (full_product >> shift) with
shift = bitlen(full)-67.  A config is correct iff delta == 1 on every
must-fire row and delta == 0 on every must-not-fire row, for BOTH
products (left = mul*lf, right = f4*rf) with the SAME config.

Two stages: a fast sweep on all fire rows + a nofire sample, then full
validation of surviving configs on every labeled row.

Run from /tmp/stageA (needs h412/, h422/, corpus2/, captures/).
"""
import random
from multiprocessing import Pool

from h437_gate_extraction import (
    ROUNDING_MODES, load_labeled_rows, chop_to_67_bits, final_cosine_result)

W = 160          # two's-complement field width for the array sum
MASK_W = (1 << W) - 1


def label_raw(row):
    """Like h437.label_one_row but returning raw operand pairs:
    ((aR, bR), label_R, (aL, bL), label_L)."""
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

    label_R = 1 if (not plain_ok and right_up_ok) else (0 if (plain_ok and not right_up_ok) else -1)
    label_L = 1 if (not plain_ok and left_up_ok and not right_up_ok) else (0 if (plain_ok and not left_up_ok) else -1)
    return (fourth, even_chain), label_R, (square, odd_chain), label_L


def recode(value, radix_bits):
    """Booth digits d_i with value == sum d_i * 2^(radix_bits*i).
    radix_bits 1 means no recoding: digits are the plain bits."""
    if radix_bits == 1:
        return [(value >> i) & 1 for i in range(value.bit_length())]
    digits = []
    base = 0
    top = value.bit_length()
    low_mask = (1 << (radix_bits - 1)) - 1
    while base <= top:
        prev = (value >> (base - 1)) & 1 if base else 0
        window = (value >> base) & ((1 << radix_bits) - 1)
        digits.append(prev + (window & low_mask)
                      - (((window >> (radix_bits - 1)) & 1) << (radix_bits - 1)))
        base += radix_bits
    return digits


def truncated_product(a, b, radix_bits, column, corr_mode, comp_units):
    """Truncated-array Booth product of a*b (b recoded).
    corr_mode: 0 = negative-digit corrections below `column` dropped,
               1 = each such correction added at `column` instead,
               2 = corrections always added at their true column.
    comp_units: compensation constant in units of 2^(column-1)."""
    total = 0
    keep_mask = MASK_W & ~((1 << column) - 1)
    for i, digit in enumerate(recode(b, radix_bits)):
        if digit == 0:
            continue
        position = radix_bits * i
        value = ((-digit if digit < 0 else digit) * a) << position
        if digit > 0:
            total += value & keep_mask
        else:
            # ones-complement row: zero below the row's own LSB column
            total += (MASK_W ^ value) & keep_mask & ~((1 << position) - 1)
            if position >= column or corr_mode == 2:
                total += 1 << position
            elif corr_mode == 1:
                total += 1 << column
    if comp_units:
        total += comp_units << (column - 1)
    return total & MASK_W


def config_delta(pair, config):
    """(a,b) -> truncated-array vs ideal-chop delta on the 67-bit unit."""
    a, b = pair
    radix_bits, swap, column, corr_mode, comp_units = config
    if swap:
        a, b = b, a
    full = a * b
    shift = max(full.bit_length() - 67, 0)
    trunc = truncated_product(a, b, radix_bits, column, corr_mode, comp_units)
    return (trunc >> shift) - (full >> shift)


def evaluate_config(job):
    """-> (config, total_mismatches, fire_missed, nofire_missed, deltas)"""
    config, rows = job
    fire_missed = nofire_missed = 0
    deltas = {}
    for pair, label in rows:
        delta = config_delta(pair, config)
        deltas[delta] = deltas.get(delta, 0) + 1
        if delta != label:
            if label == 1:
                fire_missed += 1
            else:
                nofire_missed += 1
    return config, fire_missed + nofire_missed, fire_missed, nofire_missed, deltas


def self_test():
    rng = random.Random(1)
    for radix_bits in (1, 2, 3):
        for _ in range(50):
            value = rng.getrandbits(67)
            digits = recode(value, radix_bits)
            assert sum(d << (radix_bits * i) for i, d in enumerate(digits)) == value
            a = rng.getrandbits(67)
            # untruncated array with corrections kept must equal a*value
            assert truncated_product(a, value, radix_bits, 0, 2, 0) == a * value


def main():
    self_test()
    rows = load_labeled_rows()
    with Pool(8) as pool:
        labeled = pool.map(label_raw, rows, chunksize=2000)

    examples = {"R": {}, "L": {}}
    conflicts = 0
    for pair_R, label_R, pair_L, label_L in labeled:
        for side, pair, label in (("R", pair_R, label_R), ("L", pair_L, label_L)):
            if label < 0:
                continue
            prior = examples[side].get(pair)
            if prior is not None and prior != label:
                conflicts += 1
            examples[side][pair] = label
    fire = {s: [(p, l) for p, l in examples[s].items() if l == 1] for s in "RL"}
    nofire = {s: [(p, l) for p, l in examples[s].items() if l == 0] for s in "RL"}
    print(f"raw-pair examples: R fire={len(fire['R'])} nofire={len(nofire['R'])}  "
          f"L fire={len(fire['L'])} nofire={len(nofire['L'])}  "
          f"pair-level conflicts={conflicts}", flush=True)

    rng = random.Random(441)
    sample = (fire["R"] + fire["L"]
              + rng.sample(nofire["R"], min(1500, len(nofire["R"])))
              + rng.sample(nofire["L"], min(1500, len(nofire["L"]))))
    n_fire_sample = len(fire["R"]) + len(fire["L"])

    configs = [(radix_bits, swap, column, corr_mode, comp_units)
               for radix_bits in (1, 2, 3)
               for swap in (0, 1)
               for column in range(40, 70)
               for corr_mode in ((0,) if radix_bits == 1 else (0, 1, 2))
               for comp_units in range(0, 7)]
    print(f"stage 1: {len(configs)} configs x {len(sample)} rows", flush=True)
    with Pool(8) as pool:
        results = pool.map(evaluate_config,
                           [(c, sample) for c in configs], chunksize=8)
    results.sort(key=lambda r: r[1])
    survivors = [r[0] for r in results if r[1] == 0]
    print(f"  exact on sample: {len(survivors)} configs")
    for config, miss, fire_missed, nofire_missed, deltas in results[:15]:
        radix_bits, swap, column, corr_mode, comp_units = config
        print(f"    radix={1 << radix_bits} swap={swap} C={column} "
              f"corr={corr_mode} K={comp_units}: {miss} mismatches "
              f"(fire {fire_missed}/{n_fire_sample}, nofire {nofire_missed}) "
              f"deltas={dict(sorted(deltas.items()))}")

    if not survivors:
        return
    everything = (fire["R"] + nofire["R"] + fire["L"] + nofire["L"])
    print(f"stage 2: validating {len(survivors)} survivors "
          f"on all {len(everything)} rows", flush=True)
    with Pool(8) as pool:
        final = pool.map(evaluate_config,
                         [(c, everything) for c in survivors], chunksize=1)
    for config, miss, fire_missed, nofire_missed, _ in sorted(final, key=lambda r: r[1]):
        radix_bits, swap, column, corr_mode, comp_units = config
        tag = "EXACT" if miss == 0 else \
            f"{miss} mismatches (fire {fire_missed}, nofire {nofire_missed})"
        print(f"  radix={1 << radix_bits} swap={swap} C={column} "
              f"corr={corr_mode} K={comp_units}: {tag}")


if __name__ == "__main__":
    main()
