#!/usr/bin/env python3
"""Inventory the residual geometry after FCOS carrier alignment."""

from __future__ import annotations

import argparse
import collections
import pathlib
import sys


MODES = ("chop", "ceil", "rn", "odd")


def align_integer(exact, grid_scale: int, mode: str) -> int:
    shift = grid_scale - exact.scale
    if shift <= 0:
        magnitude = exact.significand << -shift
    else:
        magnitude, remainder = divmod(exact.significand, 1 << shift)
        if remainder:
            if mode == "ceil":
                magnitude += 1
            elif mode == "rn":
                half = 1 << (shift - 1)
                if remainder > half or (remainder == half and (magnitude & 1)):
                    magnitude += 1
            elif mode == "odd":
                magnitude |= 1
            elif mode != "chop":
                raise ValueError(mode)
    return -magnitude if exact.sign else magnitude


def centered_byte(value: int) -> int:
    value &= 0xFF
    return value - 256 if value >= 128 else value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("constants", type=pathlib.Path, help="public sibling-constants.json")
    parser.add_argument(
        "--corpus",
        action="append",
        required=True,
        help="TAG,INPUT,CAPTURE_DIRECTORY,CAPTURE_STEM",
    )
    parser.add_argument("--show", type=int, default=160)
    parser.add_argument("--index", action="append", type=int, default=[])
    parser.add_argument("--include-correct", action="store_true")
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

    constants = load_cosine_constants([args.constants])
    chop67 = Quantization(67, "chop")
    rn64 = Quantization(64, "rn")
    final_quantizations = {
        mode: Quantization(64, mode) for mode in ROUNDING_MODES
    }
    one = constants["one"]
    records = []

    for specification in args.corpus:
        tag, input_text, capture_text, stem = specification.split(",")
        input_path = pathlib.Path(input_text)
        capture_directory = pathlib.Path(capture_text)
        inputs = [
            tuple(int(field, 16) for field in line.split())
            for line in input_path.read_text().splitlines()
            if line.strip()
        ]
        captures = {
            mode: [
                parse_capture(line, "cos")
                for line in (
                    capture_directory / f"{stem}_{mode}_status.txt"
                ).read_text().splitlines()
            ]
            for mode in ROUNDING_MODES
        }
        paired = None
        if all(
            (capture_directory / f"fsincos_{mode}_status.txt").exists()
            for mode in ROUNDING_MODES
        ):
            paired = {
                mode: [
                    parse_capture(line, "cos")
                    for line in (
                        capture_directory / f"fsincos_{mode}_status.txt"
                    ).read_text().splitlines()
                ]
                for mode in ROUNDING_MODES
            }

        for index, (sign_exponent, significand) in enumerate(inputs):
            if args.index and index not in args.index:
                continue
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
            left_exact = multiply_exact(exact_from_p6(square), exact_from_p6(negative))
            left = quantize_exact(left_exact, chop67)[0]
            left_shift = left_exact.significand.bit_length() - 67
            left_discarded = left_exact.significand & ((1 << left_shift) - 1)

            positive = multiply(fourth, constants["C6"], chop67).value
            positive = add(constants["C4"], positive, rn64).value
            positive = multiply(fourth, positive, chop67).value
            positive = add(constants["C2"], positive, rn64).value
            right_exact = multiply_exact(exact_from_p6(fourth), exact_from_p6(positive))
            right = quantize_exact(right_exact, chop67)[0]

            expected = {}
            for mode in ROUNDING_MODES:
                captured = captures[mode][index]
                assert captured is not None
                output, status = captured
                expected[mode] = (output, bool(status & CONDITION_C1))

            distance = abs(left.scale - right.scale)
            active = bool(
                (square.mantissa & 7)
                and (
                    ((left_discarded << 3) >> left_shift)
                    or (
                        distance == 7
                        and ((left_discarded << 5) >> left_shift)
                    )
                )
            )
            affine = square.mantissa & 7
            if active:
                affine += 8 - distance
            else:
                affine = 0

            def score(payload: int) -> tuple[int, int]:
                active_left = left
                if payload:
                    active_left = add_exact(
                        left,
                        ExactFP(
                            left.sign ^ int(payload < 0),
                            abs(payload),
                            left.scale - 8,
                        ),
                    )
                correction = materialize_exact(add_exact(active_left, right), chop67).value
                output_misses = c1_misses = 0
                for mode in ROUNDING_MODES:
                    result = add(one, correction, final_quantizations[mode])
                    observed = (
                        extended_from_p6(result.value, mode)[0], result.incremented
                    )
                    output_misses += observed[0] != expected[mode][0]
                    c1_misses += observed[1] != expected[mode][1]
                return output_misses, c1_misses

            costs = {delta: score(affine + delta) for delta in range(-8, 9)}
            if costs[0] == (0, 0) and not args.include_correct:
                continue
            accepted = tuple(delta for delta, cost in costs.items() if cost == (0, 0))
            grid_scale = left.scale - 8
            lane_values = {}
            for source, exact in (
                ("chop", right),
                ("exact", right_exact),
            ):
                for mode in MODES:
                    lane = align_integer(exact, grid_scale, mode) & 0xFF
                    lane_values[f"{source}-{mode}"] = lane
            left_tail8 = (left_discarded << 8) >> left_shift
            right_shift = right_exact.significand.bit_length() - 67
            right_discarded = right_exact.significand & ((1 << right_shift) - 1)
            right_tail8 = (right_discarded << 8) >> right_shift
            records.append(
                {
                    "tag": tag,
                    "index": index,
                    "distance": distance,
                    "ylow": square.mantissa & 7,
                    "affine": affine,
                    "accepted": accepted,
                    "cost": costs[0],
                    "lanes": lane_values,
                    "left_tail8": left_tail8,
                    "right_tail8": right_tail8,
                    "negative_low": negative.mantissa & 0xFF,
                    "positive_low": positive.mantissa & 0xFF,
                    "square_low": square.mantissa & 0xFF,
                    "fourth_low": fourth.mantissa & 0xFF,
                    "paired_relation": (
                        tuple(
                            0
                            if paired[mode][index][0] == expected[mode][0]
                            else (
                                -1
                                if paired[mode][index][0] < expected[mode][0]
                                else 1
                            )
                            for mode in ROUNDING_MODES
                        )
                        if paired is not None else None
                    ),
                }
            )

    print(f"h385 affine residual inputs={len(records)}")
    print("by corpus:", dict(sorted(collections.Counter(r["tag"] for r in records).items())))
    print(
        "by distance:",
        dict(sorted(collections.Counter(r["distance"] for r in records).items())),
    )
    print(
        "accepted delta intervals:",
        collections.Counter(r["accepted"] for r in records).most_common(24),
    )
    for record in records[: args.show]:
        lane_text = " ".join(
            f"{name}={value:02x}/{centered_byte(value - record['affine']):+d}"
            for name, value in record["lanes"].items()
        )
        print(
            f"  {record['tag']}:{record['index']} d={record['distance']} "
            f"y={record['ylow']} p={record['affine']} accepted={record['accepted']} "
            f"cost={record['cost']} lt={record['left_tail8']:02x} "
            f"rt={record['right_tail8']:02x} n={record['negative_low']:02x} "
            f"q={record['positive_low']:02x} s={record['square_low']:02x} "
            f"f={record['fourth_low']:02x} pair={record['paired_relation']} {lane_text}"
        )


if __name__ == "__main__":
    main()
