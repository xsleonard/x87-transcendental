#!/usr/bin/env python3
"""Generate an independent hardware-blind FCOS tail-gate discriminator."""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import re
import sys


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("constants", type=pathlib.Path, help="public sibling-constants.json")
    parser.add_argument("inputs", type=pathlib.Path)
    parser.add_argument("output", type=pathlib.Path)
    parser.add_argument("metadata", type=pathlib.Path)
    parser.add_argument("--index", action="append", type=int, required=True)
    parser.add_argument("--minimum-offset", type=int, default=1)
    parser.add_argument("--maximum-offset", type=int, default=32768)
    parser.add_argument("--neighbor-radius", type=int, default=8)
    parser.add_argument("--control-count", type=int, default=8192)
    parser.add_argument("--distance", type=int, default=8)
    parser.add_argument("--ylow", type=int, default=7)
    parser.add_argument(
        "--tail-source", choices=("left", "right", "square"), default="left"
    )
    parser.add_argument("--tail-bits", type=int, default=2)
    parser.add_argument("--tail-threshold", type=int, default=1)
    parser.add_argument("--tail-bit", type=int, default=-1)
    parser.add_argument("--tail-bit-state", type=int, choices=(0, 1), default=1)
    parser.add_argument("--payload-delta", type=int, default=-1)
    parser.add_argument("--lane-delta", type=int, default=0)
    parser.add_argument(
        "--csa-gate",
        help="optional MODE,FEATURE,FEATURE literal multiplier-vector gate",
    )
    parser.add_argument("--csa-bit", help="optional literal multiplier-vector bit")
    args = parser.parse_args()

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
        p6_from_extended,
        quantize_exact,
    )
    from p6_constants import load_cosine_constants  # pylint: disable=import-outside-toplevel
    from numerical_capture import ROUNDING_MODES  # pylint: disable=import-outside-toplevel
    from numerical_capture import direct_region  # pylint: disable=import-outside-toplevel
    from p6_value import P6Value  # pylint: disable=import-outside-toplevel
    from h382_fcos_literal_csa_carrier import (  # pylint: disable=import-outside-toplevel
        bit,
        literal_csa_product,
    )

    source = [
        tuple(int(field, 16) for field in line.split())
        for line in args.inputs.read_text().splitlines()
        if line.strip()
    ]
    constants = load_cosine_constants([args.constants])
    chop67 = Quantization(67, "chop")
    rn64 = Quantization(64, "rn")
    finals = {mode: Quantization(64, mode) for mode in ROUNDING_MODES}
    one = constants["one"]

    def prefix(exact, bits):
        shift = exact.significand.bit_length() - 67
        if shift <= 0:
            return 0
        discarded = exact.significand & ((1 << shift) - 1)
        return (discarded << bits) >> shift

    def signature(sign_exponent, significand):
        if direct_region(sign_exponent, significand) != "small":
            return None
        value = p6_from_extended(sign_exponent, significand)
        magnitude = P6Value.from_fields(0, value.exponent, value.mantissa)
        square_exact = multiply_exact(
            exact_from_p6(magnitude), exact_from_p6(magnitude)
        )
        square = multiply(magnitude, magnitude, chop67).value
        if (square.mantissa & 7) != args.ylow:
            return None
        fourth = multiply(square, square, chop67).value
        negative = multiply(fourth, constants["C5"], chop67).value
        negative = add(constants["C3"], negative, rn64).value
        negative = multiply(fourth, negative, chop67).value
        negative = add(constants["C1"], negative, rn64).value
        left_exact = multiply_exact(exact_from_p6(square), exact_from_p6(negative))
        left = quantize_exact(left_exact, chop67)[0]

        positive = multiply(fourth, constants["C6"], chop67).value
        positive = add(constants["C4"], positive, rn64).value
        positive = multiply(fourth, positive, chop67).value
        positive = add(constants["C2"], positive, rn64).value
        right_exact = multiply_exact(
            exact_from_p6(fourth), exact_from_p6(positive)
        )
        right = quantize_exact(right_exact, chop67)[0]
        distance = abs(left.scale - right.scale)
        if distance != args.distance:
            return None
        if not (
            prefix(left_exact, 3)
            or (distance == 7 and prefix(left_exact, 5))
        ):
            return None
        payload = args.ylow + 8 - distance
        lane_shift = (left.scale - 8) - right.scale
        lane = (
            right.significand >> lane_shift
            if lane_shift >= 0
            else right.significand << -lane_shift
        ) & 0xFF
        if ((lane - payload) & 0xFF) != (args.lane_delta & 0xFF):
            return None
        selected_tail = {
            "left": left_exact,
            "right": right_exact,
            "square": square_exact,
        }[args.tail_source]
        if prefix(selected_tail, args.tail_bits) < args.tail_threshold:
            return None
        if args.tail_bit >= 0 and bool(
            prefix(selected_tail, 8) & (1 << args.tail_bit)
        ) != bool(args.tail_bit_state):
            return None
        if args.csa_gate or args.csa_bit:
            assert (negative.mantissa & 7) == 0
            physical = square.mantissa * (negative.mantissa >> 3)
            product_shift = physical.bit_length() - 67
            sum_vector, carry_vector, _ = literal_csa_product(
                square.mantissa, negative.mantissa >> 3
            )
            vectors = {
                "s": sum_vector,
                "c": carry_vector,
                "p": sum_vector ^ carry_vector,
                "g": sum_vector & carry_vector,
            }

            def feature(text):
                match = re.fullmatch(r"([a-z]+)([+-]\d+)", text)
                if match is None:
                    raise ValueError(text)
                return bit(
                    vectors[match.group(1)],
                    product_shift + int(match.group(2)),
                )

            if args.csa_bit and not feature(args.csa_bit):
                return None
            if args.csa_gate:
                gate_mode, first_text, second_text = args.csa_gate.split(",")
                relation = feature(first_text) ^ feature(second_text)
                if relation != (gate_mode == "xor"):
                    return None

        variants = []
        for delta in (0, args.payload_delta):
            active_left = add_exact(
                left,
                ExactFP(left.sign, payload + delta, left.scale - 8),
            )
            correction = materialize_exact(
                add_exact(active_left, right), chop67
            ).value
            variants.append(
                tuple(
                    (
                        extended_from_p6(
                            (result := add(one, correction, finals[mode])).value,
                            mode,
                        )[0],
                        result.incremented,
                    )
                    for mode in ROUNDING_MODES
                )
            )
        return tuple(variants)

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
                variants = signature(exponent, significand)
                if variants is not None and variants[0] != variants[1]:
                    centers.append((seed_index, direction * distance, exponent, significand))

    rows = {}

    def insert(seed_index, center_offset, exponent, significand, relative, kind):
        neighbor = significand + relative
        if not 1 << 63 <= neighbor < 1 << 64:
            return
        for sign in (0, 1):
            rows.setdefault(
                (exponent | (sign << 15), neighbor),
                (seed_index, center_offset, relative, sign, kind),
            )

    for seed_index, center_offset, exponent, significand in centers:
        for relative in range(-args.neighbor_radius, args.neighbor_radius + 1):
            insert(seed_index, center_offset, exponent, significand, relative, "separator")

    span = args.maximum_offset - args.minimum_offset + 1
    for control in range(args.control_count):
        seed_index = args.index[control % len(args.index)]
        sign_exponent, seed_significand = source[seed_index]
        exponent = sign_exponent & 0x7FFF
        mixed = (control * 0x9E3779B1 + 0x388FC05) & 0xFFFFFFFF
        distance = args.minimum_offset + mixed % span
        direction = -1 if mixed & 0x80000000 else 1
        insert(
            seed_index,
            direction * distance,
            exponent,
            seed_significand + direction * distance,
            0,
            "control",
        )

    output_text = "".join(
        f"{sign_exponent:04x} {significand:016x}\n"
        for sign_exponent, significand in rows
    )
    digest = hashlib.sha256(output_text.encode()).hexdigest()
    metadata_lines = [
        "# hardware-blind FCOS aligned-lane/tail discriminator",
        f"# candidate_magnitudes={candidates}",
        f"# separator_centers={len(centers)}",
        f"# rows={len(rows)}",
        f"# offset_annulus={args.minimum_offset}..{args.maximum_offset}",
        f"# neighbor_radius={args.neighbor_radius}",
        f"# distance={args.distance}",
        f"# ylow={args.ylow}",
        f"# tail={args.tail_source}:{args.tail_bits}>={args.tail_threshold}",
        f"# tail_bit={args.tail_bit}:{args.tail_bit_state}",
        f"# payload_delta={args.payload_delta}",
        f"# lane_delta={args.lane_delta}",
        f"# csa_gate={args.csa_gate or 'none'}",
        f"# csa_bit={args.csa_bit or 'none'}",
        "# seed_indexes=" + ",".join(str(index) for index in args.index),
        f"# input_sha256={digest}",
        "# row seed_index center_offset relative sign kind",
    ]
    metadata_lines.extend(
        f"{row} {seed_index} {center_offset} {relative} {sign} {kind}"
        for row, (seed_index, center_offset, relative, sign, kind) in enumerate(rows.values())
    )
    args.output.write_text(output_text)
    args.metadata.write_text("\n".join(metadata_lines) + "\n")
    print(
        f"h388 candidates={candidates} centers={len(centers)} "
        f"rows={len(rows)} sha256={digest}"
    )


if __name__ == "__main__":
    main()
