#!/usr/bin/env python3
"""Infer per-input accepted hidden-carrier intervals at the FCOS terminal add."""

from __future__ import annotations

import argparse
import collections
import pathlib
import sys


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("constants", type=pathlib.Path, help="public sibling-constants.json")
    parser.add_argument("inputs", type=pathlib.Path)
    parser.add_argument("capture_directory", type=pathlib.Path)
    parser.add_argument("capture_stem")
    parser.add_argument("--maximum", type=int, default=31)
    parser.add_argument("--show", type=int, default=200)
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
    interval_counts: collections.Counter[tuple[int, ...]] = collections.Counter()
    interesting = []

    for index, (sign_exponent, significand) in enumerate(inputs):
        if sign_exponent >> 15 or direct_region(sign_exponent, significand) != "small":
            continue
        value = p6_from_extended(sign_exponent, significand)
        magnitude = P6Value.from_fields(0, value.exponent, value.mantissa)
        square_exact = multiply_exact(
            exact_from_p6(magnitude), exact_from_p6(magnitude)
        )
        tmp1 = multiply(magnitude, magnitude, chop67).value
        tmp2 = multiply(tmp1, tmp1, chop67).value

        negative = multiply(tmp2, constants["C5"], chop67).value
        negative = add(constants["C3"], negative, rn64).value
        negative = multiply(tmp2, negative, chop67).value
        negative = add(constants["C1"], negative, rn64).value
        left_exact = multiply_exact(exact_from_p6(tmp1), exact_from_p6(negative))
        left = quantize_exact(left_exact, chop67)[0]

        positive = multiply(tmp2, constants["C6"], chop67).value
        positive = add(constants["C4"], positive, rn64).value
        positive = multiply(tmp2, positive, chop67).value
        positive = add(constants["C2"], positive, rn64).value
        right_exact = multiply_exact(exact_from_p6(tmp2), exact_from_p6(positive))
        right = quantize_exact(right_exact, chop67)[0]

        expected = {}
        for mode in ROUNDING_MODES:
            captured = captures[mode][index]
            assert captured is not None
            output, status = captured
            expected[mode] = (output, bool(status & CONDITION_C1))

        accepted = []
        for payload in range(args.maximum + 1):
            active_left = left
            if payload:
                active_left = add_exact(
                    left,
                    ExactFP(left.sign, payload, left.scale - 8),
                )
            correction = materialize_exact(
                add_exact(active_left, right), chop67
            ).value
            observed = {}
            for mode in ROUNDING_MODES:
                result = add(one, correction, final_quantizations[mode])
                observed[mode] = (
                    extended_from_p6(result.value, mode)[0], result.incremented
                )
            if observed == expected:
                accepted.append(payload)
        interval = tuple(accepted)
        interval_counts[interval] += 1

        ylow = tmp1.mantissa & 7
        if ylow in interval:
            continue
        left_shift = left_exact.significand.bit_length() - 67
        left_discarded = left_exact.significand & ((1 << left_shift) - 1)
        combined = add_exact(left, right)
        combine_shift = combined.significand.bit_length() - 67
        combine_discarded = combined.significand & ((1 << combine_shift) - 1)
        square_shift = square_exact.significand.bit_length() - 67
        square_discarded = square_exact.significand & ((1 << square_shift) - 1)
        features = {
            "ylow": ylow,
            "sqkeep8": (square_exact.significand >> square_shift) & 0xFF,
            "sqtail8": (square_discarded << 8) >> square_shift,
            "sqtail12": (square_discarded << 12) >> square_shift,
            "xlow8": negative.mantissa & 0xFF,
            "lkeep8": (left_exact.significand >> left_shift) & 0xFF,
            "ltail8": (left_discarded << 8) >> left_shift,
            "ltail12": (left_discarded << 12) >> left_shift,
            "rkeep8": right.significand & 0xFF,
            "clow8": (combined.significand >> combine_shift) & 0xFF,
            "ctail8": (combine_discarded << 8) >> combine_shift,
            "expdiff": abs(left.scale - right.scale),
        }
        interesting.append((index, interval, features))

    print(
        f"h381 positive-small-inputs={sum(interval_counts.values())} "
        f"interesting={len(interesting)}"
    )
    print("accepted interval census:")
    for interval, count in interval_counts.most_common(24):
        interval_text = (
            "none" if not interval else
            f"{interval[0]}..{interval[-1]} ({len(interval)})"
        )
        print(f"  {interval_text}: {count}")
    for index, interval, features in interesting[: args.show]:
        print(
            f"  row={index} accepted="
            + ("none" if not interval else f"{interval[0]}..{interval[-1]}")
            + " "
            + " ".join(f"{name}={number:x}" for name, number in features.items())
        )


if __name__ == "__main__":
    main()
