#!/usr/bin/env python3
"""Search asymmetric 67-by-64 input routing at FCOS terminal FMUL sites."""

from __future__ import annotations

import argparse
import dataclasses
import pathlib
import sys


@dataclasses.dataclass(frozen=True)
class Route:
    y_operand: int | None
    y_mode: str = "chop"
    output_mode: str = "chop"

    def short(self) -> str:
        if self.y_operand is None:
            return "symmetric/chop67"
        return f"op{self.y_operand}->Y64/{self.y_mode}/O67={self.output_mode}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("constants", type=pathlib.Path, help="public sibling-constants.json")
    parser.add_argument("inputs", type=pathlib.Path)
    parser.add_argument("capture_directory", type=pathlib.Path)
    parser.add_argument("capture_stem")
    parser.add_argument("--control-count", type=int, default=2048)
    parser.add_argument("--full-top", type=int, default=24)
    args = parser.parse_args()

    uop_directory = pathlib.Path(__file__).resolve().parents[1] / "uop-re"
    sys.path.insert(0, str(uop_directory))
    from p6_arithmetic import (  # pylint: disable=import-outside-toplevel
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
    one = constants["one"]
    modes = ("rn", "chop", "away", "odd")
    routes = (Route(None),) + tuple(
        Route(y_operand, y_mode, output_mode)
        for y_operand in (0, 1)
        for y_mode in modes
        for output_mode in modes
    )

    def routed_product(operands, route):
        values = [exact_from_p6(operand) for operand in operands]
        if route.y_operand is not None:
            values[route.y_operand] = quantize_exact(
                values[route.y_operand], Quantization(64, route.y_mode)
            )[0]
        exact = multiply_exact(*values)
        return quantize_exact(
            exact, Quantization(67, route.output_mode)
        )[0]

    prepared = []
    baseline_misses = []
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

        positive = multiply(tmp2, constants["C6"], chop67).value
        positive = add(constants["C4"], positive, rn64).value
        positive = multiply(tmp2, positive, chop67).value
        positive = add(constants["C2"], positive, rn64).value

        left_values = tuple(
            routed_product((tmp1, negative), route) for route in routes
        )
        right_values = tuple(
            routed_product((tmp2, positive), route) for route in routes
        )
        expected = {}
        for mode in ROUNDING_MODES:
            captured = captures[mode][index]
            assert captured is not None
            output, status = captured
            expected[mode] = (output, bool(status & CONDITION_C1))
        record = (left_values, right_values, expected)
        prepared.append(record)

        correction = materialize_exact(
            add_exact(left_values[0], right_values[0]), chop67
        ).value
        if any(
            (
                extended_from_p6(
                    (result := add(one, correction, Quantization(64, mode))).value,
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

    def score(points, left_index, right_index):
        output_misses = c1_misses = input_misses = 0
        for left_values, right_values, expected in points:
            correction = materialize_exact(
                add_exact(left_values[left_index], right_values[right_index]),
                chop67,
            ).value
            any_miss = False
            for mode in ROUNDING_MODES:
                result = add(one, correction, Quantization(64, mode))
                observed = (
                    extended_from_p6(result.value, mode)[0],
                    result.incremented,
                )
                output_miss = observed[0] != expected[mode][0]
                c1_miss = observed[1] != expected[mode][1]
                output_misses += output_miss
                c1_misses += c1_miss
                any_miss |= output_miss or c1_miss
            input_misses += any_miss
        return output_misses, c1_misses, input_misses

    ranked = sorted(
        (
            *score(selected, left_index, right_index),
            routes[left_index].short(),
            routes[right_index].short(),
            left_index,
            right_index,
        )
        for left_index in range(len(routes))
        for right_index in range(len(routes))
    )
    print(
        f"h374 inputs={len(prepared)} baseline-input-misses={len(baseline_misses)} "
        f"selected={len(selected)} routes={len(routes)} pairs={len(ranked)}"
    )
    print("selected ranking:")
    for output, c1, input_misses, left, right, _, _ in ranked[:24]:
        print(
            f"  L={left} R={right} output={output} C1={c1} inputs={input_misses}"
        )
    print("full-corpus ranking:")
    full = sorted(
        (
            *score(prepared, left_index, right_index),
            left,
            right,
        )
        for _, _, _, left, right, left_index, right_index in ranked[: args.full_top]
    )
    for output, c1, input_misses, left, right in full:
        print(
            f"  L={left} R={right} output={output} C1={c1} inputs={input_misses}"
        )


if __name__ == "__main__":
    main()
