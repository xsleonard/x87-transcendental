#!/usr/bin/env python3
"""Feed retained multiplier sum/carry vectors into FCOS's final subtract."""

from __future__ import annotations

import argparse
import pathlib
import sys

from h382_fcos_literal_csa_carrier import literal_csa_product


MASK135 = (1 << 135) - 1
VECTOR_MODES = ("chop", "odd", "combined-odd", "carry-count")


def retained_vector_sum(
    sum_vector: int,
    carry_vector: int,
    shift: int,
    mode: str,
) -> int:
    """Truncate the two unresolved vectors on a shared product grid."""
    sum_vector &= MASK135
    carry_vector &= MASK135
    if shift <= 0:
        return (sum_vector + carry_vector) & MASK135
    mask = (1 << shift) - 1
    sum_tail = sum_vector & mask
    carry_tail = carry_vector & mask
    retained_sum = sum_vector & ~mask
    retained_carry = carry_vector & ~mask
    if mode == "odd":
        retained_sum |= int(bool(sum_tail)) << shift
        retained_carry |= int(bool(carry_tail)) << shift
    elif mode == "combined-odd":
        retained_sum |= int(bool(sum_tail or carry_tail)) << shift
    elif mode == "carry-count":
        retained_sum += (int(bool(sum_tail)) + int(bool(carry_tail))) << shift
    elif mode != "chop":
        raise ValueError(mode)
    return (retained_sum + retained_carry) & MASK135


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("constants", type=pathlib.Path, help="public sibling-constants.json")
    parser.add_argument("inputs", type=pathlib.Path)
    parser.add_argument("capture_directory", type=pathlib.Path)
    parser.add_argument("capture_stem")
    parser.add_argument("--minimum-extra", type=int, default=0)
    parser.add_argument("--maximum-extra", type=int, default=16)
    parser.add_argument("--control-count", type=int, default=2048)
    parser.add_argument("--full-top", type=int, default=16)
    parser.add_argument("--top", type=int, default=32)
    parser.add_argument(
        "--sidecar",
        action="store_true",
        help="keep the ordinary chopped product and derive only its low lane from CSA state",
    )
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
    from numerical_capture import CONDITION_C1, ROUNDING_MODES  # pylint: disable=import-outside-toplevel
    from numerical_capture import direct_region, parse_capture  # pylint: disable=import-outside-toplevel
    from p6_value import P6Value  # pylint: disable=import-outside-toplevel

    inputs = [
        tuple(int(field, 16) for field in line.split())
        for line in args.inputs.read_text().splitlines()
        if line.strip()
    ]
    captures = {
        mode: [
            parse_capture(line, "cos")
            for line in (
                args.capture_directory / f"{args.capture_stem}_{mode}_status.txt"
            ).read_text().splitlines()
        ]
        for mode in ROUNDING_MODES
    }
    constants = load_cosine_constants([args.constants])
    chop67 = Quantization(67, "chop")
    rn64 = Quantization(64, "rn")
    final_quantizations = {
        mode: Quantization(64, mode) for mode in ROUNDING_MODES
    }
    one = constants["one"]
    prepared = []

    for index, (sign_exponent, significand) in enumerate(inputs):
        if sign_exponent >> 15 or direct_region(sign_exponent, significand) != "small":
            continue
        value = p6_from_extended(sign_exponent, significand)
        magnitude = P6Value.from_fields(0, value.exponent, value.mantissa)
        square = multiply(magnitude, magnitude, chop67).value
        fourth = multiply(square, square, chop67).value

        negative = multiply(fourth, constants["C5"], chop67).value
        negative = add(constants["C3"], negative, rn64).value
        negative = multiply(fourth, negative, chop67).value
        negative = add(constants["C1"], negative, rn64).value
        assert (negative.mantissa & 7) == 0
        left_exact = multiply_exact(exact_from_p6(square), exact_from_p6(negative))
        left = quantize_exact(left_exact, chop67)[0]
        physical = square.mantissa * (negative.mantissa >> 3)
        assert physical << 3 == left_exact.significand
        normal = literal_csa_product(square.mantissa, negative.mantissa >> 3)
        reverse = literal_csa_product(
            square.mantissa, negative.mantissa >> 3, True
        )

        positive = multiply(fourth, constants["C6"], chop67).value
        positive = add(constants["C4"], positive, rn64).value
        positive = multiply(fourth, positive, chop67).value
        positive = add(constants["C2"], positive, rn64).value
        right = quantize_exact(
            multiply_exact(exact_from_p6(fourth), exact_from_p6(positive)),
            chop67,
        )[0]

        expected = {}
        for mode in ROUNDING_MODES:
            captured = captures[mode][index]
            assert captured is not None
            output, status = captured
            expected[mode] = (output, bool(status & CONDITION_C1))
        prepared.append(
            (
                physical,
                left_exact.scale,
                left,
                normal[:2],
                reverse[:2],
                right,
                expected,
            )
        )

    candidates = tuple(
        (orientation, extra, mode)
        for orientation in ("normal", "reverse")
        for extra in range(args.minimum_extra, args.maximum_extra + 1)
        for mode in VECTOR_MODES
    )

    def score(points, candidate):
        orientation, extra, vector_mode = candidate if candidate is not None else (
            "normal", 0, "chop"
        )
        output_misses = c1_misses = input_misses = 0
        for physical, scale, left, normal, reverse, right, expected in points:
            active_left = left
            if candidate is not None:
                vectors = normal if orientation == "normal" else reverse
                shift = physical.bit_length() - (67 + extra)
                retained = retained_vector_sum(*vectors, shift, vector_mode)
                if args.sidecar:
                    grid_shift = physical.bit_length() - 67 - 8
                    retained_grid = (
                        retained >> grid_shift
                        if grid_shift >= 0 else retained << -grid_shift
                    )
                    payload = retained_grid - (left.significand << 8)
                    if payload:
                        active_left = add_exact(
                            left,
                            ExactFP(
                                left.sign ^ int(payload < 0),
                                abs(payload),
                                left.scale - 8,
                            ),
                        )
                else:
                    active_left = ExactFP(1, retained << 3, scale)
            correction = materialize_exact(
                add_exact(active_left, right), chop67
            ).value
            any_miss = False
            for rounding_mode in ROUNDING_MODES:
                result = add(
                    one, correction, final_quantizations[rounding_mode]
                )
                observed = (
                    extended_from_p6(result.value, rounding_mode)[0],
                    result.incremented,
                )
                output_miss = observed[0] != expected[rounding_mode][0]
                c1_miss = observed[1] != expected[rounding_mode][1]
                output_misses += output_miss
                c1_misses += c1_miss
                any_miss |= output_miss or c1_miss
            input_misses += any_miss
        return output_misses, c1_misses, input_misses

    baseline_misses = []
    exact_rows = []
    for record in prepared:
        if score((record,), None) == (0, 0, 0):
            exact_rows.append(record)
        else:
            baseline_misses.append(record)
    control_count = min(args.control_count, len(exact_rows))
    selected = baseline_misses + [
        exact_rows[(index * len(exact_rows)) // control_count]
        for index in range(control_count)
    ]
    ranked = sorted(
        (*score(selected, candidate), candidate)
        for candidate in candidates
    )
    print(
        f"h386 inputs={len(prepared)} selected={len(selected)} "
        f"baseline-input-misses={len(baseline_misses)} candidates={len(candidates)}"
    )
    print("selected ranking:")
    for output, c1, input_misses, candidate in ranked[: args.top]:
        print(
            f"  {candidate}: output={output} C1={c1} inputs={input_misses}"
        )
    full = sorted(
        (*score(prepared, candidate), candidate)
        for _, _, _, candidate in ranked[: args.full_top]
    )
    print("full-corpus finalists:")
    for output, c1, input_misses, candidate in full:
        print(
            f"  {candidate}: output={output} C1={c1} inputs={input_misses}"
        )


if __name__ == "__main__":
    main()
