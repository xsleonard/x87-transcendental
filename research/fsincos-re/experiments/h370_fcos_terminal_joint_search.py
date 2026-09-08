#!/usr/bin/env python3
"""Search joint FCOS terminal-product and combine materializations."""

from __future__ import annotations

import argparse
import dataclasses
import pathlib
import sys


@dataclasses.dataclass(frozen=True)
class Candidate:
    coefficient_delta: int
    left: str
    right: str
    combine: str

    def short(self) -> str:
        return (
            f"c23={self.coefficient_delta:+d} left={self.left} "
            f"right={self.right} combine={self.combine}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("constants", type=pathlib.Path, help="public sibling-constants.json")
    parser.add_argument("inputs", type=pathlib.Path)
    parser.add_argument("capture_directory", type=pathlib.Path)
    parser.add_argument("capture_stem")
    parser.add_argument("--control-count", type=int, default=4096)
    parser.add_argument("--full-top", type=int, default=16)
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
    from numerical_capture import parse_capture  # pylint: disable=import-outside-toplevel
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
                args.capture_directory
                / f"{args.capture_stem}_{mode}_status.txt"
            ).read_text().splitlines()
        ]
        for mode in ROUNDING_MODES
    }
    constants = load_cosine_constants([args.constants])
    chop67 = Quantization(67, "chop")
    rn64 = Quantization(64, "rn")
    one = constants["one"]

    def quantize_wide(exact, specification):
        mode = "".join(character for character in specification if character.isalpha())
        bits = int("".join(character for character in specification if character.isdigit()))
        if bits <= 67:
            return quantize_exact(exact, Quantization(bits, mode))[0]
        shift = exact.significand.bit_length() - bits
        if shift <= 0:
            return exact
        retained = exact.significand >> shift
        remainder = exact.significand & ((1 << shift) - 1)
        if remainder:
            if mode == "away":
                retained += 1
            elif mode == "odd":
                retained |= 1
            elif mode == "rn":
                half = 1 << (shift - 1)
                retained += remainder > half or (
                    remainder == half and bool(retained & 1)
                )
        return ExactFP(exact.sign, retained, exact.scale + shift)

    coefficient_variants = {}
    original = constants["C2"]
    for delta in (0, -3):
        coefficient_variants[delta] = P6Value.from_fields(
            original.sign, original.exponent, original.mantissa + delta
        )

    prepared = []
    baseline_misses = []
    for index, (sign_exponent, significand) in enumerate(inputs):
        value = p6_from_extended(sign_exponent, significand)
        magnitude = P6Value.from_fields(0, value.exponent, value.mantissa)
        tmp1 = multiply(magnitude, magnitude, chop67).value
        tmp2 = multiply(tmp1, tmp1, chop67).value

        negative = multiply(tmp2, constants["C5"], chop67).value
        negative = add(constants["C3"], negative, rn64).value
        negative = multiply(tmp2, negative, chop67).value
        negative = add(constants["C1"], negative, rn64).value
        left_exact = multiply_exact(
            exact_from_p6(tmp1), exact_from_p6(negative)
        )

        positive_prefix = multiply(tmp2, constants["C6"], chop67).value
        positive_prefix = add(constants["C4"], positive_prefix, rn64).value
        positive_prefix = multiply(tmp2, positive_prefix, chop67).value
        right_exact = {}
        for delta, coefficient in coefficient_variants.items():
            positive = add(coefficient, positive_prefix, rn64).value
            right_exact[delta] = multiply_exact(
                exact_from_p6(tmp2), exact_from_p6(positive)
            )
        expected = {}
        for mode in ROUNDING_MODES:
            captured = captures[mode][index]
            assert captured is not None
            output, status = captured
            expected[mode] = (output, bool(status & CONDITION_C1))
        record = (left_exact, right_exact, expected)
        prepared.append(record)

        left = quantize_wide(left_exact, "chop67")
        right = quantize_wide(right_exact[0], "chop67")
        correction = materialize_exact(
            add_exact(left, right), chop67
        ).value
        baseline_ok = True
        for mode in ROUNDING_MODES:
            result = add(one, correction, Quantization(64, mode))
            baseline_ok &= (
                extended_from_p6(result.value, mode)[0], result.incremented
            ) == expected[mode]
        if not baseline_ok:
            baseline_misses.append(record)

    exact = [record for record in prepared if record not in baseline_misses]
    control_count = min(args.control_count, len(exact))
    selected = baseline_misses + [
        exact[(index * len(exact)) // control_count]
        for index in range(control_count)
    ]

    left_actions = (
        "chop67",
        *(f"chop{bits}" for bits in range(68, 73)),
        *(f"rn{bits}" for bits in range(68, 73)),
        "away68",
        "odd68",
    )
    right_actions = ("chop67", "chop66", "chop65", "chop64")
    combine_actions = ("chop67", "rn67", "away67", "odd67")
    candidates = tuple(
        Candidate(delta, left, right, combine)
        for delta in coefficient_variants
        for left in left_actions
        for right in right_actions
        for combine in combine_actions
    )

    def score(points, candidate):
        output_misses = c1_misses = input_misses = 0
        for left_exact, right_exact, expected in points:
            left = quantize_wide(left_exact, candidate.left)
            right = quantize_wide(
                right_exact[candidate.coefficient_delta], candidate.right
            )
            correction = materialize_exact(
                add_exact(left, right),
                Quantization(67, candidate.combine[:-2]),
            ).value
            any_miss = False
            for mode in ROUNDING_MODES:
                result = add(one, correction, Quantization(64, mode))
                output = extended_from_p6(result.value, mode)[0]
                expected_output, expected_c1 = expected[mode]
                output_miss = output != expected_output
                c1_miss = result.incremented != expected_c1
                output_misses += output_miss
                c1_misses += c1_miss
                any_miss |= output_miss or c1_miss
            input_misses += any_miss
        return output_misses, c1_misses, input_misses

    ranked = sorted(
        (*score(selected, candidate), candidate.short(), candidate)
        for candidate in candidates
    )
    print(
        f"h370 inputs={len(prepared)} baseline-input-misses={len(baseline_misses)} "
        f"selected={len(selected)} candidates={len(candidates)}"
    )
    print("selected ranking:")
    for output, c1, input_misses, _, candidate in ranked[:24]:
        print(
            f"  {candidate.short()} output={output} C1={c1} "
            f"inputs={input_misses}"
        )
    print("full-corpus ranking:")
    full_ranked = sorted(
        (*score(prepared, candidate), candidate.short())
        for _, _, _, _, candidate in ranked[:args.full_top]
    )
    for output, c1, input_misses, description in full_ranked:
        print(
            f"  {description} output={output} C1={c1} inputs={input_misses}"
        )


if __name__ == "__main__":
    main()
