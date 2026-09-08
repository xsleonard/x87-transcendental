#!/usr/bin/env python3
"""Search low-unit FCOS polynomial coefficient corrections."""

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
    parser.add_argument("--control-count", type=int, default=2048)
    parser.add_argument("--delta", type=int, default=64)
    parser.add_argument("--full-top", type=int, default=12)
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
    indexes = ("C1", "C2", "C3", "C4", "C5", "C6")
    one = constants["one"]
    chop67 = Quantization(67, "chop")
    rn64 = Quantization(64, "rn")

    prepared = []
    baseline_misses = []

    def evaluate(tmp1, tmp2, active_constants, mode):
        tmp5 = multiply(tmp2, active_constants["C5"], chop67).value
        tmp6 = multiply(tmp2, active_constants["C6"], chop67).value
        tmp5 = add(active_constants["C3"], tmp5, rn64).value
        tmp6 = add(active_constants["C4"], tmp6, rn64).value
        tmp5 = multiply(tmp2, tmp5, chop67).value
        tmp6 = multiply(tmp2, tmp6, chop67).value
        tmp5 = add(active_constants["C1"], tmp5, rn64).value
        tmp6 = add(active_constants["C2"], tmp6, rn64).value
        tmp5 = multiply(tmp1, tmp5, chop67).value
        tmp6 = multiply(tmp2, tmp6, chop67).value
        correction = add(tmp5, tmp6, chop67).value
        result = add(one, correction, Quantization(64, mode))
        return extended_from_p6(result.value, mode)[0], result.incremented

    for input_index, (sign_exponent, significand) in enumerate(inputs):
        value = p6_from_extended(sign_exponent, significand)
        magnitude = P6Value.from_fields(0, value.exponent, value.mantissa)
        tmp1 = multiply(magnitude, magnitude, chop67).value
        tmp2 = multiply(tmp1, tmp1, chop67).value
        expected = {}
        baseline_ok = True
        for mode in ROUNDING_MODES:
            captured = captures[mode][input_index]
            assert captured is not None
            output, status = captured
            expected[mode] = (output, bool(status & CONDITION_C1))
            baseline_ok &= evaluate(tmp1, tmp2, constants, mode) == expected[mode]
        record = (input_index, tmp1, tmp2, expected)
        prepared.append(record)
        if not baseline_ok:
            baseline_misses.append(record)

    exact = [record for record in prepared if record not in baseline_misses]
    control_count = min(args.control_count, len(exact))
    selected = baseline_misses + [
        exact[(index * len(exact)) // control_count]
        for index in range(control_count)
    ]

    def score(points, constant_index, delta):
        active = dict(constants)
        original = constants[constant_index]
        mantissa = original.mantissa + delta
        if not 0 <= mantissa < 1 << 68:
            return (10**9, 10**9)
        active[constant_index] = P6Value.from_fields(
            original.sign, original.exponent, mantissa
        )
        output_misses = c1_misses = 0
        for _, tmp1, tmp2, expected in points:
            for mode in ROUNDING_MODES:
                output, c1 = evaluate(tmp1, tmp2, active, mode)
                expected_output, expected_c1 = expected[mode]
                output_misses += output != expected_output
                c1_misses += c1 != expected_c1
        return output_misses, c1_misses

    ranked = sorted(
        (
            *score(selected, constant_index, delta),
            constant_index,
            delta,
        )
        for constant_index in indexes
        for delta in range(-args.delta, args.delta + 1)
    )
    baseline = score(selected, "C1", 0)
    print(
        f"h367 inputs={len(inputs)} baseline-input-misses={len(baseline_misses)} "
        f"selected={len(selected)} baseline-selected={baseline[0]}/{baseline[1]}"
    )
    print("selected ranking:")
    for output_misses, c1_misses, constant_index, delta in ranked[:24]:
        print(
            f"  constant={constant_index} delta={delta:+d} "
            f"output={output_misses} C1={c1_misses}"
        )
    print("full-corpus top candidates:")
    full_ranked = sorted(
        (
            *score(prepared, constant_index, delta),
            constant_index,
            delta,
        )
        for _, _, constant_index, delta in ranked[:args.full_top]
    )
    for output_misses, c1_misses, constant_index, delta in full_ranked:
        print(
            f"  constant={constant_index} delta={delta:+d} "
            f"output={output_misses} C1={c1_misses}"
        )


if __name__ == "__main__":
    main()
