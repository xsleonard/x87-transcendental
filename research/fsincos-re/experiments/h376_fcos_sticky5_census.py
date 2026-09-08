#!/usr/bin/env python3
"""Census a baseline-versus-sticky FCOS terminal-carrier choice."""

from __future__ import annotations

import argparse
import collections
import pathlib
import sys


def trailing_zeros(value: int) -> int:
    return 999 if not value else (value & -value).bit_length() - 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("constants", type=pathlib.Path, help="public sibling-constants.json")
    parser.add_argument("inputs", type=pathlib.Path)
    parser.add_argument("metadata", type=pathlib.Path)
    parser.add_argument("capture_directory", type=pathlib.Path)
    parser.add_argument("capture_stem")
    parser.add_argument("--show", type=int, default=100)
    parser.add_argument("--depth", type=int, default=5)
    parser.add_argument(
        "--low3-payload",
        action="store_true",
        help="use the guarded multiplier low-three-bit payload candidate",
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
    metadata = {}
    for line in args.metadata.read_text().splitlines():
        if not line or line.startswith("#") or line.startswith("row "):
            continue
        fields = line.split()
        if len(fields) == 5:
            row, seed, offset, sign, partition = fields
            metadata[int(row)] = (seed, offset, sign, partition)
        elif len(fields) == 6 and fields[0].isdigit():
            row, seed, offset, relative, sign, kind = fields
            metadata[int(row)] = (seed, offset, sign, f"{kind}/{relative}")
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
    one = constants["one"]
    final_quantizations = {
        mode: Quantization(64, mode) for mode in ROUNDING_MODES
    }
    counts = collections.Counter()
    feature_counts = collections.Counter()
    shown = 0

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
        left_exact = multiply_exact(exact_from_p6(tmp1), exact_from_p6(negative))
        left, left_inexact, _ = quantize_exact(left_exact, chop67)
        left_shift = left_exact.significand.bit_length() - 67
        left_discarded = left_exact.significand & ((1 << left_shift) - 1)
        left_tail3 = (left_discarded << 3) >> left_shift
        payload = (
            (tmp1.mantissa & 7)
            if args.low3_payload and left_tail3 else int(left_inexact)
        )
        sticky = ExactFP(left.sign, payload, left.scale - args.depth)
        left_sticky = add_exact(left, sticky)

        positive = multiply(tmp2, constants["C6"], chop67).value
        positive = add(constants["C4"], positive, rn64).value
        positive = multiply(tmp2, positive, chop67).value
        positive = add(constants["C2"], positive, rn64).value
        right_exact = multiply_exact(exact_from_p6(tmp2), exact_from_p6(positive))
        right = quantize_exact(right_exact, chop67)[0]

        corrections = {
            "base": materialize_exact(add_exact(left, right), chop67).value,
            "sticky": materialize_exact(
                add_exact(left_sticky, right), chop67
            ).value,
        }
        expected = {}
        results = {route: {} for route in corrections}
        for mode in ROUNDING_MODES:
            captured = captures[mode][index]
            assert captured is not None
            output, status = captured
            expected[mode] = (output, bool(status & CONDITION_C1))
            for route, correction in corrections.items():
                result = add(one, correction, final_quantizations[mode])
                results[route][mode] = (
                    extended_from_p6(result.value, mode)[0], result.incremented
                )
        accepted = tuple(route for route in corrections if results[route] == expected)
        if len(accepted) == len(corrections):
            category = "both"
        elif accepted:
            category = accepted[0]
        else:
            category = "neither"
        counts[category] += 1
        if results["base"] == results["sticky"]:
            counts["nondiscriminating"] += 1
            if category != "neither":
                continue
        else:
            counts["discriminating"] += 1

        left_retained = left_exact.significand >> left_shift
        combined = add_exact(left, right)
        combine_shift = combined.significand.bit_length() - 67
        combine_retained = combined.significand >> combine_shift
        combine_discarded = combined.significand & ((1 << combine_shift) - 1)
        features = {
            "lwidth": left_exact.significand.bit_length(),
            "ltz0": trailing_zeros(tmp1.mantissa),
            "ltz1": trailing_zeros(negative.mantissa),
            "ltzsum": trailing_zeros(tmp1.mantissa) + trailing_zeros(negative.mantissa),
            "llsb3": left_retained & 7,
            "ylow3": tmp1.mantissa & 7,
            "ldhi3": (left_discarded << 3) >> left_shift,
            "ldhi5": (left_discarded << 5) >> left_shift,
            "expdiff": abs(left.scale - right.scale),
            "clsb3": combine_retained & 7,
            "cdhi5": (combine_discarded << 5) >> combine_shift,
        }
        for name, feature in features.items():
            feature_counts[category, name, feature] += 1
        if category != "sticky" and shown < args.show:
            seed, offset, sign, partition = metadata.get(
                index, ("?", "?", str(sign_exponent >> 15), "?")
            )
            print(
                f"row={index} category={category} seed={seed} offset={offset} "
                f"sign={sign} part={partition} "
                + " ".join(f"{name}={number}" for name, number in features.items())
            )
            shown += 1

    print(f"h376 inputs={len(inputs)} counts={dict(counts)}")
    for category in ("base", "sticky", "neither"):
        print(f"{category} feature distributions:")
        for name in (
            "lwidth", "ltz0", "ltz1", "ltzsum", "llsb3", "ylow3", "ldhi3",
            "ldhi5", "expdiff", "clsb3", "cdhi5",
        ):
            values = {
                value: count
                for (active, feature, value), count in feature_counts.items()
                if active == category and feature == name
            }
            print(f"  {name}: {dict(sorted(values.items()))}")


if __name__ == "__main__":
    main()
