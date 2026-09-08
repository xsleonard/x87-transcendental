#!/usr/bin/env python3
"""Search jammed sticky positions on FCOS terminal-product carriers."""

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
    parser.add_argument("--maximum-depth", type=int, default=32)
    parser.add_argument("--control-count", type=int, default=2048)
    parser.add_argument("--full-top", type=int, default=32)
    parser.add_argument("--census-only", action="store_true")
    parser.add_argument(
        "--evaluate-pair", action="append", default=[], metavar="LEFT,RIGHT"
    )
    parser.add_argument("--schedule-search", action="store_true")
    parser.add_argument(
        "--evaluate-schedule", action="append", default=[], metavar="D7,D8,D9"
    )
    parser.add_argument("--conditional-search", action="store_true")
    parser.add_argument(
        "--evaluate-conditional", action="append", default=[], metavar="DEPTH,TOPBITS"
    )
    parser.add_argument("--y64-sticky-search", action="store_true")
    parser.add_argument(
        "--evaluate-y64-sticky", action="append", default=[], metavar="DEPTH,TOPBITS"
    )
    parser.add_argument("--payload-search", action="store_true")
    parser.add_argument(
        "--evaluate-payload", action="append", default=[], metavar="DEPTH,MODE"
    )
    parser.add_argument("--partial-product-search", action="store_true")
    parser.add_argument(
        "--evaluate-partial-product",
        action="append",
        default=[],
        metavar="DEPTH,FRACTION_BITS,MODE",
    )
    parser.add_argument("--affine-payload-search", action="store_true")
    parser.add_argument(
        "--evaluate-affine-payload", action="append", default=[], metavar="DEPTH,A,B"
    )
    parser.add_argument("--trigger-search", action="store_true")
    parser.add_argument("--decomposed-product-search", action="store_true")
    parser.add_argument("--dual-payload-search", action="store_true")
    parser.add_argument("--compensated-payload-search", action="store_true")
    parser.add_argument("--left-compensated-payload-search", action="store_true")
    parser.add_argument("--square-tail-adjustment-search", action="store_true")
    parser.add_argument(
        "--evaluate-square-tail-adjustment",
        action="append",
        default=[],
        metavar="LOW,HIGH",
    )
    parser.add_argument(
        "--evaluate-compensated-payload",
        action="append",
        default=[],
        metavar="RIGHT_BITS,BIAS",
    )
    parser.add_argument(
        "--evaluate-dual-payload",
        action="append",
        default=[],
        metavar="LEFT_DEPTH,RIGHT_DEPTH",
    )
    parser.add_argument(
        "--evaluate-decomposed-product",
        action="append",
        default=[],
        metavar="MAIN_BITS,PARTIAL_MODE",
    )
    parser.add_argument(
        "--evaluate-trigger",
        action="append",
        default=[],
        metavar="DEPTH,MODE,TAIL_MIN,Y_MIN,Y_MAX",
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
    depths = (0, *range(1, args.maximum_depth + 1))

    def carrier_values(exact):
        chopped, inexact, _ = quantize_exact(exact, chop67)
        values = [chopped]
        for depth in depths[1:]:
            sticky = ExactFP(chopped.sign, int(inexact), chopped.scale - depth)
            values.append(add_exact(chopped, sticky))
        return tuple(values)

    prepared = []
    baseline_misses = []
    for index, (sign_exponent, significand) in enumerate(inputs):
        if direct_region(sign_exponent, significand) != "small":
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
        left = carrier_values(left_exact)
        left_shift = left_exact.significand.bit_length() - 67
        left_discarded = left_exact.significand & ((1 << left_shift) - 1)
        left_prefix_values = tuple(
            (left_discarded << bits) >> left_shift
            for bits in range(1, 17)
        )
        left_prefix_nonzero = tuple(bool(value) for value in left_prefix_values)

        positive = multiply(tmp2, constants["C6"], chop67).value
        positive = add(constants["C4"], positive, rn64).value
        positive = multiply(tmp2, positive, chop67).value
        positive = add(constants["C2"], positive, rn64).value
        right_exact = multiply_exact(
            exact_from_p6(tmp2), exact_from_p6(positive)
        )
        right = carrier_values(right_exact)

        expected = {}
        for mode in ROUNDING_MODES:
            captured = captures[mode][index]
            assert captured is not None
            output, status = captured
            expected[mode] = (output, bool(status & CONDITION_C1))
        record = (
            left,
            right,
            expected,
            abs(left[0].scale - right[0].scale),
            left_prefix_nonzero,
            tmp1.mantissa & 7,
            left_prefix_values,
            negative.mantissa,
            negative,
            tmp1,
            positive,
            tmp2,
            right_exact,
            square_exact,
        )
        prepared.append(record)
        correction = materialize_exact(add_exact(left[0], right[0]), chop67).value
        if any(
            (
                extended_from_p6(
                    (result := add(one, correction, final_quantizations[mode])).value,
                    mode,
                )[0],
                result.incremented,
            )
            != expected[mode]
            for mode in ROUNDING_MODES
        ):
            baseline_misses.append(record)

    exact = [record for record in prepared if record not in baseline_misses]
    control_count = min(args.control_count, len(exact))
    selected = baseline_misses + [
        exact[(index * len(exact)) // control_count] for index in range(control_count)
    ]

    def score(points, left_depth, right_depth):
        output_misses = c1_misses = input_misses = 0
        for left, right, expected, _expdiff, _prefixes, _tmp1_low3, _prefix_values, _xmant, _negative, _tmp1, _positive, _tmp2, _right_exact, _square_exact in points:
            correction = materialize_exact(
                add_exact(left[left_depth], right[right_depth]), chop67
            ).value
            any_miss = False
            for mode in ROUNDING_MODES:
                result = add(one, correction, final_quantizations[mode])
                observed = (
                    extended_from_p6(result.value, mode)[0], result.incremented
                )
                output_miss = observed[0] != expected[mode][0]
                c1_miss = observed[1] != expected[mode][1]
                output_misses += output_miss
                c1_misses += c1_miss
                any_miss |= output_miss or c1_miss
            input_misses += any_miss
        return output_misses, c1_misses, input_misses

    def score_schedule(points, schedule):
        output_misses = c1_misses = input_misses = 0
        for left, right, expected, expdiff, _prefixes, _tmp1_low3, _prefix_values, _xmant, _negative, _tmp1, _positive, _tmp2, _right_exact, _square_exact in points:
            left_depth = schedule.get(expdiff, 0)
            correction = materialize_exact(
                add_exact(left[left_depth], right[0]), chop67
            ).value
            any_miss = False
            for mode in ROUNDING_MODES:
                result = add(one, correction, final_quantizations[mode])
                observed = (
                    extended_from_p6(result.value, mode)[0], result.incremented
                )
                output_miss = observed[0] != expected[mode][0]
                c1_miss = observed[1] != expected[mode][1]
                output_misses += output_miss
                c1_misses += c1_miss
                any_miss |= output_miss or c1_miss
            input_misses += any_miss
        return output_misses, c1_misses, input_misses

    def score_conditional(points, depth, top_bits):
        output_misses = c1_misses = input_misses = 0
        for left, right, expected, _expdiff, prefixes, _tmp1_low3, _prefix_values, _xmant, _negative, _tmp1, _positive, _tmp2, _right_exact, _square_exact in points:
            active_depth = depth if prefixes[top_bits - 1] else 0
            correction = materialize_exact(
                add_exact(left[active_depth], right[0]), chop67
            ).value
            any_miss = False
            for mode in ROUNDING_MODES:
                result = add(one, correction, final_quantizations[mode])
                observed = (
                    extended_from_p6(result.value, mode)[0], result.incremented
                )
                output_miss = observed[0] != expected[mode][0]
                c1_miss = observed[1] != expected[mode][1]
                output_misses += output_miss
                c1_misses += c1_miss
                any_miss |= output_miss or c1_miss
            input_misses += any_miss
        return output_misses, c1_misses, input_misses

    def score_y64_sticky(points, depth, top_bits):
        output_misses = c1_misses = input_misses = 0
        for left, right, expected, _expdiff, prefixes, tmp1_low3, _prefix_values, _xmant, _negative, _tmp1, _positive, _tmp2, _right_exact, _square_exact in points:
            active = bool(tmp1_low3) and prefixes[top_bits - 1]
            correction = materialize_exact(
                add_exact(left[depth if active else 0], right[0]), chop67
            ).value
            any_miss = False
            for mode in ROUNDING_MODES:
                result = add(one, correction, final_quantizations[mode])
                observed = (
                    extended_from_p6(result.value, mode)[0], result.incremented
                )
                output_miss = observed[0] != expected[mode][0]
                c1_miss = observed[1] != expected[mode][1]
                output_misses += output_miss
                c1_misses += c1_miss
                any_miss |= output_miss or c1_miss
            input_misses += any_miss
        return output_misses, c1_misses, input_misses

    payload_modes = (
        "one", "ylow", "yinv", "ypop", "tail", "tailpop",
        "and", "or", "xor", "mul", "ysquare", "gray", "bitrev",
        "low2", "high2", "signed3", "booth0",
    )

    def payload_value(mode, ylow, tail3):
        if mode == "one":
            return 1
        if mode == "ylow":
            return ylow
        if mode == "yinv":
            return 8 - ylow
        if mode == "ypop":
            return bin(ylow).count("1")
        if mode == "tail":
            return tail3
        if mode == "tailpop":
            return bin(tail3).count("1")
        if mode == "and":
            return ylow & tail3
        if mode == "or":
            return ylow | tail3
        if mode == "xor":
            return ylow ^ tail3
        if mode == "mul":
            return ylow * tail3
        if mode == "ysquare":
            return ylow * ylow
        if mode == "gray":
            return ylow ^ (ylow >> 1)
        if mode == "bitrev":
            return ((ylow & 1) << 2) | (ylow & 2) | ((ylow & 4) >> 2)
        if mode == "low2":
            return ylow & 3
        if mode == "high2":
            return ylow >> 1
        if mode == "signed3":
            return ylow if ylow < 4 else ylow - 8
        if mode == "booth0":
            return (0, 1, -2, -1)[ylow & 3]
        raise ValueError(mode)

    def score_payload(points, depth, payload_mode):
        output_misses = c1_misses = input_misses = 0
        for left, right, expected, _expdiff, _prefixes, ylow, prefix_values, _xmant, _negative, _tmp1, _positive, _tmp2, _right_exact, _square_exact in points:
            tail3 = prefix_values[2]
            payload = payload_value(payload_mode, ylow, tail3) if ylow and tail3 else 0
            active_left = left[0]
            if payload:
                contribution = ExactFP(
                    left[0].sign ^ int(payload < 0),
                    abs(payload),
                    left[0].scale - depth,
                )
                active_left = add_exact(active_left, contribution)
            correction = materialize_exact(
                add_exact(active_left, right[0]), chop67
            ).value
            any_miss = False
            for mode in ROUNDING_MODES:
                result = add(one, correction, final_quantizations[mode])
                observed = (
                    extended_from_p6(result.value, mode)[0], result.incremented
                )
                output_miss = observed[0] != expected[mode][0]
                c1_miss = observed[1] != expected[mode][1]
                output_misses += output_miss
                c1_misses += c1_miss
                any_miss |= output_miss or c1_miss
            input_misses += any_miss
        return output_misses, c1_misses, input_misses

    def score_dual_payload(points, left_depth, right_depth):
        output_misses = c1_misses = input_misses = 0
        for left, right, expected, _expdiff, _prefixes, ylow, prefix_values, _xmant, _negative, _tmp1, _positive, tmp2, right_exact, _square_exact in points:
            left_tail3 = prefix_values[2]
            active_left = left[0]
            if ylow and left_tail3:
                active_left = add_exact(
                    active_left,
                    ExactFP(active_left.sign, ylow, active_left.scale - left_depth),
                )
            right_shift = right_exact.significand.bit_length() - 67
            right_discarded = (
                right_exact.significand & ((1 << right_shift) - 1)
                if right_shift > 0 else 0
            )
            right_tail3 = (
                (right_discarded << 3) >> right_shift if right_shift > 0 else 0
            )
            right_low3 = tmp2.mantissa & 7
            active_right = right[0]
            if right_low3 and right_tail3:
                active_right = add_exact(
                    active_right,
                    ExactFP(
                        active_right.sign,
                        right_low3,
                        active_right.scale - right_depth,
                    ),
                )
            correction = materialize_exact(
                add_exact(active_left, active_right), chop67
            ).value
            any_miss = False
            for mode in ROUNDING_MODES:
                result = add(one, correction, final_quantizations[mode])
                observed = (
                    extended_from_p6(result.value, mode)[0], result.incremented
                )
                output_miss = observed[0] != expected[mode][0]
                c1_miss = observed[1] != expected[mode][1]
                output_misses += output_miss
                c1_misses += c1_miss
                any_miss |= output_miss or c1_miss
            input_misses += any_miss
        return output_misses, c1_misses, input_misses

    def score_compensated_payload(points, right_bits, bias):
        output_misses = c1_misses = input_misses = 0
        for left, right, expected, _expdiff, _prefixes, ylow, prefix_values, _xmant, _negative, _tmp1, _positive, _tmp2, right_exact, _square_exact in points:
            left_tail3 = prefix_values[2]
            right_shift = right_exact.significand.bit_length() - 67
            right_discarded = (
                right_exact.significand & ((1 << right_shift) - 1)
                if right_shift > 0 else 0
            )
            right_prefix = (
                (right_discarded << right_bits) >> right_shift
                if right_shift > 0 else 0
            )
            payload = (
                ylow + bias - right_prefix if ylow and left_tail3 else 0
            )
            active_left = left[0]
            if payload:
                active_left = add_exact(
                    active_left,
                    ExactFP(
                        active_left.sign ^ int(payload < 0),
                        abs(payload),
                        active_left.scale - 8,
                    ),
                )
            correction = materialize_exact(
                add_exact(active_left, right[0]), chop67
            ).value
            any_miss = False
            for mode in ROUNDING_MODES:
                result = add(one, correction, final_quantizations[mode])
                observed = (
                    extended_from_p6(result.value, mode)[0], result.incremented
                )
                output_miss = observed[0] != expected[mode][0]
                c1_miss = observed[1] != expected[mode][1]
                output_misses += output_miss
                c1_misses += c1_miss
                any_miss |= output_miss or c1_miss
            input_misses += any_miss
        return output_misses, c1_misses, input_misses

    def score_left_compensated_payload(points, left_bits, bias, direction):
        output_misses = c1_misses = input_misses = 0
        for left, right, expected, _expdiff, _prefixes, ylow, prefix_values, _xmant, _negative, _tmp1, _positive, _tmp2, _right_exact, _square_exact in points:
            left_prefix = prefix_values[left_bits - 1]
            payload = (
                ylow + direction * (left_prefix - bias)
                if ylow and prefix_values[2] else 0
            )
            active_left = left[0]
            if payload:
                active_left = add_exact(
                    active_left,
                    ExactFP(
                        active_left.sign ^ int(payload < 0),
                        abs(payload),
                        active_left.scale - 8,
                    ),
                )
            correction = materialize_exact(
                add_exact(active_left, right[0]), chop67
            ).value
            any_miss = False
            for mode in ROUNDING_MODES:
                result = add(one, correction, final_quantizations[mode])
                observed = (
                    extended_from_p6(result.value, mode)[0], result.incremented
                )
                output_miss = observed[0] != expected[mode][0]
                c1_miss = observed[1] != expected[mode][1]
                output_misses += output_miss
                c1_misses += c1_miss
                any_miss |= output_miss or c1_miss
            input_misses += any_miss
        return output_misses, c1_misses, input_misses

    def score_square_tail_adjustment(points, low, high, direction):
        output_misses = c1_misses = input_misses = 0
        for left, right, expected, _expdiff, _prefixes, ylow, prefix_values, _xmant, _negative, _tmp1, _positive, _tmp2, _right_exact, square_exact in points:
            square_shift = square_exact.significand.bit_length() - 67
            square_discarded = (
                square_exact.significand & ((1 << square_shift) - 1)
                if square_shift > 0 else 0
            )
            square_tail8 = (
                (square_discarded << 8) >> square_shift
                if square_shift > 0 else 0
            )
            adjustment = -1 if square_tail8 < low else (1 if square_tail8 >= high else 0)
            adjustment *= direction
            payload = (
                ylow + adjustment if ylow and prefix_values[2] else 0
            )
            active_left = left[0]
            if payload:
                active_left = add_exact(
                    active_left,
                    ExactFP(
                        active_left.sign ^ int(payload < 0),
                        abs(payload),
                        active_left.scale - 8,
                    ),
                )
            correction = materialize_exact(
                add_exact(active_left, right[0]), chop67
            ).value
            any_miss = False
            for mode in ROUNDING_MODES:
                result = add(one, correction, final_quantizations[mode])
                observed = (
                    extended_from_p6(result.value, mode)[0], result.incremented
                )
                output_miss = observed[0] != expected[mode][0]
                c1_miss = observed[1] != expected[mode][1]
                output_misses += output_miss
                c1_misses += c1_miss
                any_miss |= output_miss or c1_miss
            input_misses += any_miss
        return output_misses, c1_misses, input_misses

    def score_trigger(points, depth, payload_mode, tail_min, y_min, y_max):
        output_misses = c1_misses = input_misses = 0
        for left, right, expected, _expdiff, _prefixes, ylow, prefix_values, _xmant, _negative, _tmp1, _positive, _tmp2, _right_exact, _square_exact in points:
            tail3 = prefix_values[2]
            payload = (
                payload_value(payload_mode, ylow, tail3)
                if y_min <= ylow <= y_max and tail3 >= tail_min else 0
            )
            active_left = left[0]
            if payload:
                contribution = ExactFP(
                    left[0].sign ^ int(payload < 0),
                    abs(payload),
                    left[0].scale - depth,
                )
                active_left = add_exact(active_left, contribution)
            correction = materialize_exact(
                add_exact(active_left, right[0]), chop67
            ).value
            any_miss = False
            for mode in ROUNDING_MODES:
                result = add(one, correction, final_quantizations[mode])
                observed = (
                    extended_from_p6(result.value, mode)[0], result.incremented
                )
                output_miss = observed[0] != expected[mode][0]
                c1_miss = observed[1] != expected[mode][1]
                output_misses += output_miss
                c1_misses += c1_miss
                any_miss |= output_miss or c1_miss
            input_misses += any_miss
        return output_misses, c1_misses, input_misses

    def rounded_partial_payload(ylow, xmant, fraction_bits, mode):
        numerator = ylow * xmant << fraction_bits
        denominator = 1 << 66
        retained, remainder = divmod(numerator, denominator)
        if remainder:
            if mode == "ceil":
                retained += 1
            elif mode == "rn":
                doubled = remainder << 1
                if doubled > denominator or (
                    doubled == denominator and (retained & 1)
                ):
                    retained += 1
            elif mode != "chop":
                raise ValueError(mode)
        return retained

    def score_partial_product(points, depth, fraction_bits, partial_mode):
        output_misses = c1_misses = input_misses = 0
        for left, right, expected, _expdiff, _prefixes, ylow, prefix_values, xmant, _negative, _tmp1, _positive, _tmp2, _right_exact, _square_exact in points:
            tail3 = prefix_values[2]
            payload = (
                rounded_partial_payload(ylow, xmant, fraction_bits, partial_mode)
                if ylow and tail3 else 0
            )
            active_left = (
                add_exact(
                    left[0],
                    ExactFP(
                        left[0].sign,
                        payload,
                        left[0].scale - depth - fraction_bits,
                    ),
                )
                if payload else left[0]
            )
            correction = materialize_exact(
                add_exact(active_left, right[0]), chop67
            ).value
            any_miss = False
            for mode in ROUNDING_MODES:
                result = add(one, correction, final_quantizations[mode])
                observed = (
                    extended_from_p6(result.value, mode)[0], result.incremented
                )
                output_miss = observed[0] != expected[mode][0]
                c1_miss = observed[1] != expected[mode][1]
                output_misses += output_miss
                c1_misses += c1_miss
                any_miss |= output_miss or c1_miss
            input_misses += any_miss
        return output_misses, c1_misses, input_misses

    def score_decomposed_product(points, main_bits, main_mode, partial_mode):
        output_misses = c1_misses = input_misses = 0
        main_quantization = Quantization(main_bits, main_mode)
        for left, right, expected, _expdiff, _prefixes, ylow, _prefix_values, _xmant, negative, tmp1, _positive, _tmp2, _right_exact, _square_exact in points:
            high_tmp1 = P6Value.from_fields(
                tmp1.sign, tmp1.exponent, tmp1.mantissa & ~7
            )
            main_exact = multiply_exact(
                exact_from_p6(high_tmp1), exact_from_p6(negative)
            )
            active_left = quantize_exact(main_exact, main_quantization)[0]
            if ylow and partial_mode != "none":
                tmp1_exact = exact_from_p6(tmp1)
                partial = multiply_exact(
                    ExactFP(tmp1.sign, ylow, tmp1_exact.scale),
                    exact_from_p6(negative),
                )
                if partial_mode.startswith("chop"):
                    partial = quantize_exact(
                        partial,
                        Quantization(int(partial_mode[4:]), "chop"),
                    )[0]
                elif partial_mode.startswith("rn"):
                    partial = quantize_exact(
                        partial,
                        Quantization(int(partial_mode[2:]), "rn"),
                    )[0]
                elif partial_mode != "exact":
                    raise ValueError(partial_mode)
                active_left = add_exact(active_left, partial)
            correction = materialize_exact(
                add_exact(active_left, right[0]), chop67
            ).value
            any_miss = False
            for mode in ROUNDING_MODES:
                result = add(one, correction, final_quantizations[mode])
                observed = (
                    extended_from_p6(result.value, mode)[0], result.incremented
                )
                output_miss = observed[0] != expected[mode][0]
                c1_miss = observed[1] != expected[mode][1]
                output_misses += output_miss
                c1_misses += c1_miss
                any_miss |= output_miss or c1_miss
            input_misses += any_miss
        return output_misses, c1_misses, input_misses

    def score_affine_payload(points, depth, multiplier, bias):
        output_misses = c1_misses = input_misses = 0
        for left, right, expected, _expdiff, _prefixes, ylow, prefix_values, _xmant, _negative, _tmp1, _positive, _tmp2, _right_exact, _square_exact in points:
            tail3 = prefix_values[2]
            payload = multiplier * ylow + bias if ylow and tail3 else 0
            active_left = left[0]
            if payload:
                active_left = add_exact(
                    active_left,
                    ExactFP(
                        active_left.sign ^ int(payload < 0),
                        abs(payload),
                        active_left.scale - depth,
                    ),
                )
            correction = materialize_exact(
                add_exact(active_left, right[0]), chop67
            ).value
            any_miss = False
            for mode in ROUNDING_MODES:
                result = add(one, correction, final_quantizations[mode])
                observed = (
                    extended_from_p6(result.value, mode)[0], result.incremented
                )
                output_miss = observed[0] != expected[mode][0]
                c1_miss = observed[1] != expected[mode][1]
                output_misses += output_miss
                c1_misses += c1_miss
                any_miss |= output_miss or c1_miss
            input_misses += any_miss
        return output_misses, c1_misses, input_misses

    print(
        f"h375 inputs={len(prepared)} baseline-input-misses={len(baseline_misses)} "
        f"selected={len(selected)}"
    )
    if args.schedule_search:
        schedule_depths = range(min(13, len(depths)))
        ranked_schedules = sorted(
            (
                *score_schedule(selected, {7: depth7, 8: depth8, 9: depth9}),
                depth7,
                depth8,
                depth9,
            )
            for depth7 in schedule_depths
            for depth8 in schedule_depths
            for depth9 in schedule_depths
        )
        print("selected expdiff schedules:")
        for output, c1, input_misses, depth7, depth8, depth9 in ranked_schedules[:24]:
            print(
                f"  d7={depth7} d8={depth8} d9={depth9} "
                f"output={output} C1={c1} inputs={input_misses}"
            )
        print("full expdiff schedules:")
        full_schedules = sorted(
            (
                *score_schedule(prepared, {7: depth7, 8: depth8, 9: depth9}),
                depth7,
                depth8,
                depth9,
            )
            for _, _, _, depth7, depth8, depth9 in ranked_schedules[:24]
        )
        for output, c1, input_misses, depth7, depth8, depth9 in full_schedules:
            print(
                f"  d7={depth7} d8={depth8} d9={depth9} "
                f"output={output} C1={c1} inputs={input_misses}"
            )
        return
    if args.evaluate_pair:
        print("requested pairs:")
        for specification in args.evaluate_pair:
            left_text, right_text = specification.split(",", 1)
            left_depth = depths.index(int(left_text))
            right_depth = depths.index(int(right_text))
            output, c1, input_misses = score(prepared, left_depth, right_depth)
            print(
                f"  left={left_text} right={right_text} output={output} "
                f"C1={c1} inputs={input_misses}"
            )
        return
    if args.evaluate_schedule:
        print("requested expdiff schedules:")
        for specification in args.evaluate_schedule:
            depth7, depth8, depth9 = (int(value) for value in specification.split(","))
            output, c1, input_misses = score_schedule(
                prepared, {7: depth7, 8: depth8, 9: depth9}
            )
            print(
                f"  d7={depth7} d8={depth8} d9={depth9} output={output} "
                f"C1={c1} inputs={input_misses}"
            )
        return
    if args.evaluate_conditional:
        print("requested conditional sticky routes:")
        for specification in args.evaluate_conditional:
            depth, top_bits = (int(value) for value in specification.split(","))
            output, c1, input_misses = score_conditional(
                prepared, depth, top_bits
            )
            print(
                f"  depth={depth} topbits={top_bits} output={output} "
                f"C1={c1} inputs={input_misses}"
            )
        return
    if args.evaluate_y64_sticky:
        print("requested Y64-loss sticky routes:")
        for specification in args.evaluate_y64_sticky:
            depth, top_bits = (int(value) for value in specification.split(","))
            output, c1, input_misses = score_y64_sticky(
                prepared, depth, top_bits
            )
            print(
                f"  depth={depth} topbits={top_bits} output={output} "
                f"C1={c1} inputs={input_misses}"
            )
        return
    if args.evaluate_payload:
        print("requested Y64 payload routes:")
        for specification in args.evaluate_payload:
            depth_text, payload_mode = specification.split(",", 1)
            output, c1, input_misses = score_payload(
                prepared, int(depth_text), payload_mode
            )
            print(
                f"  depth={depth_text} mode={payload_mode} output={output} "
                f"C1={c1} inputs={input_misses}"
            )
        return
    if args.evaluate_dual_payload:
        print("requested dual terminal-product payload routes:")
        for specification in args.evaluate_dual_payload:
            left_text, right_text = specification.split(",", 1)
            output, c1, input_misses = score_dual_payload(
                prepared, int(left_text), int(right_text)
            )
            print(
                f"  left={left_text} right={right_text} output={output} "
                f"C1={c1} inputs={input_misses}"
            )
        return
    if args.evaluate_compensated_payload:
        print("requested compensated terminal-product payload routes:")
        for specification in args.evaluate_compensated_payload:
            bits_text, bias_text = specification.split(",", 1)
            output, c1, input_misses = score_compensated_payload(
                prepared, int(bits_text), int(bias_text)
            )
            print(
                f"  rightbits={bits_text} bias={bias_text} output={output} "
                f"C1={c1} inputs={input_misses}"
            )
        return
    if args.evaluate_square_tail_adjustment:
        print("requested square-tail payload adjustment routes:")
        for specification in args.evaluate_square_tail_adjustment:
            low_text, high_text = specification.split(",", 1)
            output, c1, input_misses = score_square_tail_adjustment(
                prepared, int(low_text), int(high_text), 1
            )
            print(
                f"  low={low_text} high={high_text} output={output} "
                f"C1={c1} inputs={input_misses}"
            )
        return
    if args.evaluate_trigger:
        print("requested Y64 payload trigger routes:")
        for specification in args.evaluate_trigger:
            depth_text, payload_mode, tail_text, ymin_text, ymax_text = (
                specification.split(",", 4)
            )
            output, c1, input_misses = score_trigger(
                prepared,
                int(depth_text),
                payload_mode,
                int(tail_text),
                int(ymin_text),
                int(ymax_text),
            )
            print(
                f"  depth={depth_text} mode={payload_mode} "
                f"tail>={tail_text} y={ymin_text}..{ymax_text} "
                f"output={output} C1={c1} inputs={input_misses}"
            )
        return
    if args.evaluate_partial_product:
        print("requested split partial-product routes:")
        for specification in args.evaluate_partial_product:
            depth_text, fraction_text, mode = specification.split(",", 2)
            output, c1, input_misses = score_partial_product(
                prepared, int(depth_text), int(fraction_text), mode
            )
            print(
                f"  depth={depth_text} fraction={fraction_text} mode={mode} "
                f"output={output} C1={c1} inputs={input_misses}"
            )
        return
    if args.evaluate_decomposed_product:
        print("requested split multiplier-product routes:")
        for specification in args.evaluate_decomposed_product:
            main_text, main_mode, partial_mode = specification.split(",", 2)
            output, c1, input_misses = score_decomposed_product(
                prepared, int(main_text), main_mode, partial_mode
            )
            print(
                f"  main={main_mode}{main_text} partial={partial_mode} "
                f"output={output} C1={c1} inputs={input_misses}"
            )
        return
    if args.evaluate_affine_payload:
        print("requested affine Y64 payload routes:")
        for specification in args.evaluate_affine_payload:
            depth, multiplier, bias = (
                int(value) for value in specification.split(",")
            )
            output, c1, input_misses = score_affine_payload(
                prepared, depth, multiplier, bias
            )
            print(
                f"  depth={depth} a={multiplier} b={bias} output={output} "
                f"C1={c1} inputs={input_misses}"
            )
        return
    if args.affine_payload_search:
        ranked_affine = sorted(
            (
                *score_affine_payload(selected, depth, multiplier, bias),
                depth,
                multiplier,
                bias,
            )
            for depth in range(5, 13)
            for multiplier in range(-4, 9)
            for bias in range(-12, 13)
            if multiplier or bias
        )
        print("selected affine Y64 payload routes:")
        for output, c1, input_misses, depth, multiplier, bias in ranked_affine[:24]:
            print(
                f"  depth={depth} a={multiplier} b={bias} output={output} "
                f"C1={c1} inputs={input_misses}"
            )
        print("full affine Y64 payload routes:")
        full_affine = sorted(
            (
                *score_affine_payload(prepared, depth, multiplier, bias),
                depth,
                multiplier,
                bias,
            )
            for _, _, _, depth, multiplier, bias in ranked_affine[: args.full_top]
        )
        for output, c1, input_misses, depth, multiplier, bias in full_affine:
            print(
                f"  depth={depth} a={multiplier} b={bias} output={output} "
                f"C1={c1} inputs={input_misses}"
            )
        return
    if args.partial_product_search:
        ranked_partial = sorted(
            (
                *score_partial_product(selected, depth, fraction_bits, mode),
                depth,
                fraction_bits,
                mode,
            )
            for depth in range(5, 12)
            for fraction_bits in range(0, 11)
            for mode in ("chop", "rn", "ceil")
        )
        print("selected split partial-product routes:")
        for output, c1, input_misses, depth, fraction_bits, mode in ranked_partial[:24]:
            print(
                f"  depth={depth} fraction={fraction_bits} mode={mode} "
                f"output={output} C1={c1} inputs={input_misses}"
            )
        print("full split partial-product routes:")
        full_partial = sorted(
            (
                *score_partial_product(prepared, depth, fraction_bits, mode),
                depth,
                fraction_bits,
                mode,
            )
            for _, _, _, depth, fraction_bits, mode in ranked_partial[:32]
        )
        for output, c1, input_misses, depth, fraction_bits, mode in full_partial:
            print(
                f"  depth={depth} fraction={fraction_bits} mode={mode} "
                f"output={output} C1={c1} inputs={input_misses}"
            )
        return
    if args.decomposed_product_search:
        partial_modes = (
            "none", "exact", "chop64", "chop65", "chop66", "chop67",
            "rn64", "rn65", "rn66", "rn67",
        )
        ranked_decomposed = sorted(
            (
                *score_decomposed_product(selected, bits, mode, partial),
                bits,
                mode,
                partial,
            )
            for bits in range(63, 68)
            for mode in ("chop", "rn", "away", "odd")
            for partial in partial_modes
        )
        print("selected split multiplier-product routes:")
        for output, c1, input_misses, bits, mode, partial in ranked_decomposed[:24]:
            print(
                f"  main={mode}{bits} partial={partial} output={output} "
                f"C1={c1} inputs={input_misses}"
            )
        print("full split multiplier-product routes:")
        full_decomposed = sorted(
            (
                *score_decomposed_product(prepared, bits, mode, partial),
                bits,
                mode,
                partial,
            )
            for _, _, _, bits, mode, partial in ranked_decomposed[: args.full_top]
        )
        for output, c1, input_misses, bits, mode, partial in full_decomposed:
            print(
                f"  main={mode}{bits} partial={partial} output={output} "
                f"C1={c1} inputs={input_misses}"
            )
        return
    if args.dual_payload_search:
        ranked_dual = sorted(
            (*score_dual_payload(selected, left_depth, right_depth), left_depth, right_depth)
            for left_depth in range(6, 11)
            for right_depth in range(1, 18)
        )
        print("selected dual terminal-product payload routes:")
        for output, c1, input_misses, left_depth, right_depth in ranked_dual[:24]:
            print(
                f"  left={left_depth} right={right_depth} output={output} "
                f"C1={c1} inputs={input_misses}"
            )
        print("full dual terminal-product payload routes:")
        full_dual = sorted(
            (*score_dual_payload(prepared, left_depth, right_depth), left_depth, right_depth)
            for _, _, _, left_depth, right_depth in ranked_dual[: args.full_top]
        )
        for output, c1, input_misses, left_depth, right_depth in full_dual:
            print(
                f"  left={left_depth} right={right_depth} output={output} "
                f"C1={c1} inputs={input_misses}"
            )
        return
    if args.compensated_payload_search:
        ranked_compensated = sorted(
            (
                *score_compensated_payload(selected, bits, bias),
                bits,
                bias,
            )
            for bits in range(1, 9)
            for bias in range(-2, (1 << bits) + 3)
        )
        print("selected compensated terminal-product payload routes:")
        for output, c1, input_misses, bits, bias in ranked_compensated[:24]:
            print(
                f"  rightbits={bits} bias={bias} output={output} "
                f"C1={c1} inputs={input_misses}"
            )
        print("full compensated terminal-product payload routes:")
        full_compensated = sorted(
            (
                *score_compensated_payload(prepared, bits, bias),
                bits,
                bias,
            )
            for _, _, _, bits, bias in ranked_compensated[: args.full_top]
        )
        for output, c1, input_misses, bits, bias in full_compensated:
            print(
                f"  rightbits={bits} bias={bias} output={output} "
                f"C1={c1} inputs={input_misses}"
            )
        return
    if args.left_compensated_payload_search:
        ranked_left_compensated = sorted(
            (
                *score_left_compensated_payload(selected, bits, bias, direction),
                bits,
                bias,
                direction,
            )
            for bits in range(1, 9)
            for bias in range(-2, (1 << bits) + 3)
            for direction in (-1, 1)
        )
        print("selected left-tail compensated payload routes:")
        for output, c1, input_misses, bits, bias, direction in ranked_left_compensated[:24]:
            print(
                f"  leftbits={bits} bias={bias} direction={direction:+d} "
                f"output={output} C1={c1} inputs={input_misses}"
            )
        print("full left-tail compensated payload routes:")
        full_left_compensated = sorted(
            (
                *score_left_compensated_payload(prepared, bits, bias, direction),
                bits,
                bias,
                direction,
            )
            for _, _, _, bits, bias, direction in ranked_left_compensated[: args.full_top]
        )
        for output, c1, input_misses, bits, bias, direction in full_left_compensated:
            print(
                f"  leftbits={bits} bias={bias} direction={direction:+d} "
                f"output={output} C1={c1} inputs={input_misses}"
            )
        return
    if args.square_tail_adjustment_search:
        thresholds = range(0, 257, 8)
        ranked_square_tail = sorted(
            (
                *score_square_tail_adjustment(selected, low, high, direction),
                low,
                high,
                direction,
            )
            for low in thresholds
            for high in thresholds
            if low <= high
            for direction in (-1, 1)
        )
        print("selected square-tail payload adjustment routes:")
        for output, c1, input_misses, low, high, direction in ranked_square_tail[:24]:
            print(
                f"  low={low} high={high} direction={direction:+d} "
                f"output={output} C1={c1} inputs={input_misses}"
            )
        print("full square-tail payload adjustment routes:")
        full_square_tail = sorted(
            (
                *score_square_tail_adjustment(prepared, low, high, direction),
                low,
                high,
                direction,
            )
            for _, _, _, low, high, direction in ranked_square_tail[: args.full_top]
        )
        for output, c1, input_misses, low, high, direction in full_square_tail:
            print(
                f"  low={low} high={high} direction={direction:+d} "
                f"output={output} C1={c1} inputs={input_misses}"
            )
        return
    if args.trigger_search:
        ranked_triggers = sorted(
            (
                *score_trigger(selected, depth, "ylow", tail_min, y_min, y_max),
                depth,
                tail_min,
                y_min,
                y_max,
            )
            for depth in range(6, 11)
            for tail_min in range(1, 8)
            for y_min in range(1, 8)
            for y_max in range(y_min, 8)
        )
        print("selected Y64 payload triggers:")
        for output, c1, input_misses, depth, tail_min, y_min, y_max in ranked_triggers[:24]:
            print(
                f"  depth={depth} tail>={tail_min} y={y_min}..{y_max} "
                f"output={output} C1={c1} inputs={input_misses}"
            )
        print("full Y64 payload triggers:")
        full_triggers = sorted(
            (
                *score_trigger(prepared, depth, "ylow", tail_min, y_min, y_max),
                depth,
                tail_min,
                y_min,
                y_max,
            )
            for _, _, _, depth, tail_min, y_min, y_max in ranked_triggers[: args.full_top]
        )
        for output, c1, input_misses, depth, tail_min, y_min, y_max in full_triggers:
            print(
                f"  depth={depth} tail>={tail_min} y={y_min}..{y_max} "
                f"output={output} C1={c1} inputs={input_misses}"
            )
        return
    if args.payload_search:
        ranked_payloads = sorted(
            (*score_payload(selected, depth, mode), depth, mode)
            for depth in range(3, 14)
            for mode in payload_modes
        )
        print("selected Y64 payload routes:")
        for output, c1, input_misses, depth, mode in ranked_payloads[:24]:
            print(
                f"  depth={depth} mode={mode} output={output} "
                f"C1={c1} inputs={input_misses}"
            )
        print("full Y64 payload routes:")
        full_payloads = sorted(
            (*score_payload(prepared, depth, mode), depth, mode)
            for _, _, _, depth, mode in (
                ranked_payloads if args.full_top == 0 else ranked_payloads[: args.full_top]
            )
        )
        for output, c1, input_misses, depth, mode in full_payloads:
            print(
                f"  depth={depth} mode={mode} output={output} "
                f"C1={c1} inputs={input_misses}"
            )
        return
    if args.y64_sticky_search:
        ranked_y64 = sorted(
            (*score_y64_sticky(selected, depth, top_bits), depth, top_bits)
            for depth in range(1, min(13, len(depths)))
            for top_bits in range(1, 17)
        )
        print("selected Y64-loss sticky routes:")
        for output, c1, input_misses, depth, top_bits in ranked_y64[:24]:
            print(
                f"  depth={depth} topbits={top_bits} output={output} "
                f"C1={c1} inputs={input_misses}"
            )
        print("full Y64-loss sticky routes:")
        full_y64 = sorted(
            (*score_y64_sticky(prepared, depth, top_bits), depth, top_bits)
            for _, _, _, depth, top_bits in ranked_y64[:24]
        )
        for output, c1, input_misses, depth, top_bits in full_y64:
            print(
                f"  depth={depth} topbits={top_bits} output={output} "
                f"C1={c1} inputs={input_misses}"
            )
        return
    if args.conditional_search:
        ranked_conditional = sorted(
            (*score_conditional(selected, depth, top_bits), depth, top_bits)
            for depth in range(1, min(13, len(depths)))
            for top_bits in range(1, 17)
        )
        print("selected conditional sticky routes:")
        for output, c1, input_misses, depth, top_bits in ranked_conditional[:24]:
            print(
                f"  depth={depth} topbits={top_bits} output={output} "
                f"C1={c1} inputs={input_misses}"
            )
        print("full conditional sticky routes:")
        full_conditional = sorted(
            (*score_conditional(prepared, depth, top_bits), depth, top_bits)
            for _, _, _, depth, top_bits in ranked_conditional[:24]
        )
        for output, c1, input_misses, depth, top_bits in full_conditional:
            print(
                f"  depth={depth} topbits={top_bits} output={output} "
                f"C1={c1} inputs={input_misses}"
            )
        return
    if not args.census_only:
        ranked = sorted(
            (*score(selected, left_depth, right_depth), left_depth, right_depth)
            for left_depth in range(len(depths))
            for right_depth in range(len(depths))
        )
        print(f"pairs={len(ranked)}")
        print("selected ranking:")
        for output, c1, input_misses, left_depth, right_depth in ranked[:24]:
            print(
                f"  left={depths[left_depth]} right={depths[right_depth]} "
                f"output={output} C1={c1} inputs={input_misses}"
            )
        print("full-corpus ranking:")
        full = sorted(
            (*score(prepared, left_depth, right_depth), depths[left_depth], depths[right_depth])
            for _, _, _, left_depth, right_depth in ranked[: args.full_top]
        )
        for output, c1, input_misses, left_depth, right_depth in full:
            print(
                f"  left={left_depth} right={right_depth} "
                f"output={output} C1={c1} inputs={input_misses}"
            )
    print("left-sticky depth census:")
    for left_depth in range(len(depths)):
        output, c1, input_misses = score(prepared, left_depth, 0)
        print(
            f"  left={depths[left_depth]} output={output} "
            f"C1={c1} inputs={input_misses}"
        )
    print("focused two-carrier census:")
    focused = []
    for left_depth in range(5, min(9, len(depths))):
        for right_depth in range(min(13, len(depths))):
            focused.append(
                (*score(prepared, left_depth, right_depth), depths[left_depth], depths[right_depth])
            )
    for output, c1, input_misses, left_depth, right_depth in sorted(focused)[:24]:
        print(
            f"  left={left_depth} right={right_depth} output={output} "
            f"C1={c1} inputs={input_misses}"
        )


if __name__ == "__main__":
    main()
