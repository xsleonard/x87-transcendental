#!/usr/bin/env python3
"""Gate focused low-unit changes to the final positive FCOS coefficient."""

from __future__ import annotations

import argparse
import pathlib
import sys


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("constants", type=pathlib.Path, help="public sibling-constants.json")
    parser.add_argument("inputs", type=pathlib.Path)
    parser.add_argument("capture_directory", type=pathlib.Path)
    parser.add_argument("capture_stem")
    parser.add_argument("--candidate", action="append", type=int, required=True)
    args = parser.parse_args()

    uop_directory = pathlib.Path(__file__).resolve().parents[1] / "uop-re"
    sys.path.insert(0, str(uop_directory))
    from p6_arithmetic import (  # pylint: disable=import-outside-toplevel
        Quantization,
        add,
        extended_from_p6,
        multiply,
        p6_from_extended,
    )
    from p6_constants import load_cosine_constants  # pylint: disable=import-outside-toplevel
    from numerical_capture import CONDITION_C1, ROUNDING_MODES  # pylint: disable=import-outside-toplevel
    from numerical_capture import (  # pylint: disable=import-outside-toplevel
        direct_region,
        parse_capture,
    )
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
    prepared = []
    for index, (sign_exponent, significand) in enumerate(inputs):
        if direct_region(sign_exponent, significand) != "small":
            continue
        value = p6_from_extended(sign_exponent, significand)
        magnitude = P6Value.from_fields(0, value.exponent, value.mantissa)
        tmp1 = multiply(magnitude, magnitude, chop67).value
        tmp2 = multiply(tmp1, tmp1, chop67).value

        negative = multiply(tmp2, constants["C5"], chop67).value
        negative = add(constants["C3"], negative, rn64).value
        negative = multiply(tmp2, negative, chop67).value
        negative = add(constants["C1"], negative, rn64).value
        negative = multiply(tmp1, negative, chop67).value

        positive_prefix = multiply(tmp2, constants["C6"], chop67).value
        positive_prefix = add(constants["C4"], positive_prefix, rn64).value
        positive_prefix = multiply(tmp2, positive_prefix, chop67).value
        expected = {}
        for mode in ROUNDING_MODES:
            captured = captures[mode][index]
            assert captured is not None
            output, status = captured
            expected[mode] = (output, bool(status & CONDITION_C1))
        prepared.append((tmp2, negative, positive_prefix, expected))

    def score(delta):
        original = constants["C2"]
        coefficient = P6Value.from_fields(
            original.sign, original.exponent, original.mantissa + delta
        )
        output_misses = c1_misses = input_misses = 0
        for tmp2, negative, positive_prefix, expected in prepared:
            positive = add(coefficient, positive_prefix, rn64).value
            positive = multiply(tmp2, positive, chop67).value
            correction = add(negative, positive, chop67).value
            any_miss = False
            for mode in ROUNDING_MODES:
                result = add(one, correction, Quantization(64, mode))
                output = extended_from_p6(result.value, mode)[0]
                expected_output, expected_c1 = expected[mode]
                output_miss = output != expected_output
                output_misses += output_miss
                c1_misses += result.incremented != expected_c1
                any_miss |= output_miss or result.incremented != expected_c1
            input_misses += any_miss
        return output_misses, c1_misses, input_misses

    print(f"h369 inputs={len(prepared)}")
    for delta in args.candidate:
        output_misses, c1_misses, input_misses = score(delta)
        print(
            f"  delta={delta:+d} output={output_misses} "
            f"C1={c1_misses} inputs={input_misses}"
        )


if __name__ == "__main__":
    main()
