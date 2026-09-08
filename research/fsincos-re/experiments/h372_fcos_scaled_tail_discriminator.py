#!/usr/bin/env python3
"""Generate a hardware-blind FCOS discriminator for a scaled product tail."""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import sys


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("constants", type=pathlib.Path, help="public sibling-constants.json")
    parser.add_argument("inputs", type=pathlib.Path)
    parser.add_argument("output", type=pathlib.Path)
    parser.add_argument("metadata", type=pathlib.Path)
    parser.add_argument("--index", action="append", type=int, required=True)
    parser.add_argument("--minimum-offset", type=int, default=4097)
    parser.add_argument("--maximum-offset", type=int, default=32768)
    parser.add_argument("--neighbor-radius", type=int, default=8)
    parser.add_argument("--control-count", type=int, default=4096)
    parser.add_argument("--payload-discriminator", action="store_true")
    args = parser.parse_args()

    if not 0 < args.minimum_offset <= args.maximum_offset:
        raise SystemExit("offset range must be positive and nonempty")

    uop_directory = pathlib.Path(__file__).resolve().parents[1] / "uop-re"
    sys.path.insert(0, str(uop_directory))
    from p6_arithmetic import (  # pylint: disable=import-outside-toplevel
        ExactFP,
        Quantization,
        add,
        add_exact,
        exact_from_p6,
        extended_from_p6,
        materialize_exact,
        multiply,
        multiply_exact,
        negate,
        p6_from_extended,
        quantize_exact,
    )
    from p6_constants import load_cosine_constants  # pylint: disable=import-outside-toplevel
    from numerical_capture import ROUNDING_MODES  # pylint: disable=import-outside-toplevel
    from p6_value import P6Value  # pylint: disable=import-outside-toplevel

    source = [
        tuple(int(field, 16) for field in line.split())
        for line in args.inputs.read_text().splitlines()
        if line.strip()
    ]
    constants = load_cosine_constants([args.constants])
    chop67 = Quantization(67, "chop")
    rn64 = Quantization(64, "rn")
    final_quantizations = {
        mode: Quantization(64, mode) for mode in ROUNDING_MODES
    }
    one = constants["one"]
    fraction_bits = 10
    numerator = 24

    def corrections(sign_exponent, significand):
        value = p6_from_extended(sign_exponent, significand)
        magnitude = P6Value.from_fields(0, value.exponent, value.mantissa)
        tmp1 = multiply(magnitude, magnitude, chop67).value
        tmp2 = multiply(tmp1, tmp1, chop67).value

        negative = multiply(tmp2, constants["C5"], chop67).value
        negative = add(constants["C3"], negative, rn64).value
        negative = multiply(tmp2, negative, chop67).value
        negative = add(constants["C1"], negative, rn64).value
        left_exact = multiply_exact(exact_from_p6(tmp1), exact_from_p6(negative))
        left = quantize_exact(left_exact, chop67)[0]
        tail = add_exact(left_exact, negate(left))

        positive = multiply(tmp2, constants["C6"], chop67).value
        positive = add(constants["C4"], positive, rn64).value
        positive = multiply(tmp2, positive, chop67).value
        positive = add(constants["C2"], positive, rn64).value
        right_exact = multiply_exact(exact_from_p6(tmp2), exact_from_p6(positive))
        right = quantize_exact(right_exact, chop67)[0]
        base = add_exact(left, right)
        retained_tail = ExactFP(
            tail.sign,
            tail.significand * numerator,
            tail.scale - fraction_bits,
        )
        baseline = materialize_exact(base, chop67).value
        if not args.payload_discriminator:
            return (
                baseline,
                materialize_exact(add_exact(base, retained_tail), chop67).value,
            )
        remainder_bits = left_exact.significand.bit_length() - 67
        remainder = left_exact.significand & ((1 << remainder_bits) - 1)
        tail3 = (remainder << 3) >> remainder_bits
        ylow = tmp1.mantissa & 7
        variants = [baseline]
        for depth, payload in (
            (8, ylow),
            (8, ylow + 1),
            (8, ylow ^ (ylow >> 1)),
            (11, 5 * ylow + 11),
        ):
            active_left = left
            if ylow and tail3:
                active_left = add_exact(
                    left,
                    ExactFP(left.sign, payload, left.scale - depth),
                )
            variants.append(
                materialize_exact(add_exact(active_left, right), chop67).value
            )
        return tuple(variants)

    def final_signature(correction):
        return tuple(
            (
                extended_from_p6(
                    (result := add(one, correction, final_quantizations[mode])).value,
                    mode,
                )[0],
                result.incremented,
            )
            for mode in ROUNDING_MODES
        )

    centers = []
    candidates = 0
    for seed_index in args.index:
        sign_exponent, seed_significand = source[seed_index]
        exponent = sign_exponent & 0x7FFF
        for direction in (-1, 1):
            for distance in range(args.minimum_offset, args.maximum_offset + 1):
                significand = seed_significand + direction * distance
                if not 1 << 63 <= significand < 1 << 64:
                    continue
                candidates += 1
                variants = corrections(exponent, significand)
                if len({final_signature(variant) for variant in variants}) > 1:
                    centers.append((seed_index, direction * distance, exponent, significand))

    rows = {}

    def insert(seed_index, center_offset, exponent, significand, relative, kind):
        neighbor = significand + relative
        if not 1 << 63 <= neighbor < 1 << 64:
            return
        for sign in (0, 1):
            key = exponent | (sign << 15), neighbor
            rows.setdefault(key, (seed_index, center_offset, relative, sign, kind))

    for seed_index, center_offset, exponent, significand in centers:
        for relative in range(-args.neighbor_radius, args.neighbor_radius + 1):
            insert(seed_index, center_offset, exponent, significand, relative, "separator")

    span = args.maximum_offset - args.minimum_offset + 1
    for control in range(args.control_count):
        seed_index = args.index[control % len(args.index)]
        sign_exponent, seed_significand = source[seed_index]
        exponent = sign_exponent & 0x7FFF
        mixed = (control * 0x9E3779B1 + 0x372FC05) & 0xFFFFFFFF
        distance = args.minimum_offset + mixed % span
        direction = -1 if mixed & 0x80000000 else 1
        significand = seed_significand + direction * distance
        insert(seed_index, direction * distance, exponent, significand, 0, "control")

    output_lines = [f"{se:04x} {sig:016x}" for se, sig in rows]
    output_text = "\n".join(output_lines) + "\n"
    metadata_lines = [
        "# hardware-blind FCOS scaled-tail discriminator",
        f"# candidate_magnitudes={candidates}",
        f"# separator_centers={len(centers)}",
        f"# rows={len(rows)}",
        (
            "# routes=baseline,ylow/256,(ylow+1)/256,gray/256,(5*ylow+11)/2048"
            if args.payload_discriminator
            else f"# alpha={numerator}/{1 << fraction_bits}"
        ),
        f"# offset_annulus={args.minimum_offset}..{args.maximum_offset}",
        f"# neighbor_radius={args.neighbor_radius}",
        "# seed_indexes=" + ",".join(str(index) for index in args.index),
        "# input_sha256=" + hashlib.sha256(output_text.encode()).hexdigest(),
        "# row seed_index center_offset relative sign kind",
    ]
    metadata_lines.extend(
        f"{row} {seed_index} {center_offset} {relative} {sign} {kind}"
        for row, (seed_index, center_offset, relative, sign, kind) in enumerate(rows.values())
    )
    args.output.write_text(output_text)
    args.metadata.write_text("\n".join(metadata_lines) + "\n")
    print(
        f"h372 candidates={candidates} centers={len(centers)} "
        f"rows={len(rows)} sha256={hashlib.sha256(output_text.encode()).hexdigest()}"
    )


if __name__ == "__main__":
    main()
