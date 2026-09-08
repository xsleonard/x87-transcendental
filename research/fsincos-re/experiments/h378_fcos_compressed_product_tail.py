#!/usr/bin/env python3
"""Search shifted guard/round/sticky encodings of the FCOS product tail."""

from __future__ import annotations

import argparse
import dataclasses
import pathlib
import sys


@dataclasses.dataclass(frozen=True)
class Candidate:
    shift: int
    retained_bits: int
    jam: bool

    def short(self) -> str:
        return (
            f"shift={self.shift} bits={self.retained_bits} "
            f"jam={int(self.jam)}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("constants", type=pathlib.Path, help="public sibling-constants.json")
    parser.add_argument("inputs", type=pathlib.Path)
    parser.add_argument("capture_directory", type=pathlib.Path)
    parser.add_argument("capture_stem")
    parser.add_argument("--maximum-shift", type=int, default=10)
    parser.add_argument("--maximum-bits", type=int, default=12)
    parser.add_argument("--control-count", type=int, default=2048)
    parser.add_argument("--full-top", type=int, default=32)
    parser.add_argument("--evaluate", action="append", default=[], metavar="SHIFT,BITS,JAM")
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
        left_exact = multiply_exact(exact_from_p6(tmp1), exact_from_p6(negative))
        left = quantize_exact(left_exact, chop67)[0]
        left_shift = left_exact.significand.bit_length() - 67
        left_remainder = left_exact.significand & ((1 << left_shift) - 1)

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
        record = (left, left_remainder, left_shift, right, expected)
        prepared.append(record)
        correction = materialize_exact(add_exact(left, right), chop67).value
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

    def mapped_left(left, remainder, remainder_bits, candidate):
        bits = candidate.retained_bits
        if bits:
            if remainder_bits > bits:
                tail = remainder >> (remainder_bits - bits)
                lower = remainder & ((1 << (remainder_bits - bits)) - 1)
            else:
                tail = remainder << (bits - remainder_bits)
                lower = 0
        else:
            tail = 0
            lower = remainder
        width = candidate.shift + bits
        if candidate.jam:
            tail = (tail << 1) | int(bool(lower))
            width += 1
        if not tail:
            return left
        contribution = ExactFP(left.sign, tail, left.scale - width)
        return add_exact(left, contribution)

    def score(points, candidate):
        output_misses = c1_misses = input_misses = 0
        for left, remainder, remainder_bits, right, expected in points:
            active_left = mapped_left(left, remainder, remainder_bits, candidate)
            correction = materialize_exact(
                add_exact(active_left, right), chop67
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
        f"h378 inputs={len(prepared)} baseline-input-misses={len(baseline_misses)} "
        f"selected={len(selected)}"
    )
    if args.evaluate:
        for specification in args.evaluate:
            shift, bits, jam = (int(value) for value in specification.split(","))
            candidate = Candidate(shift, bits, bool(jam))
            output, c1, input_misses = score(prepared, candidate)
            print(
                f"  {candidate.short()} output={output} C1={c1} inputs={input_misses}"
            )
        return

    candidates = tuple(
        Candidate(shift, bits, bool(jam))
        for shift in range(args.maximum_shift + 1)
        for bits in range(args.maximum_bits + 1)
        for jam in (0, 1)
        if bits or jam
    )
    ranked = sorted(
        (*score(selected, candidate), candidate.short(), candidate)
        for candidate in candidates
    )
    print(f"candidates={len(candidates)} selected ranking:")
    for output, c1, input_misses, _, candidate in ranked[:24]:
        print(
            f"  {candidate.short()} output={output} C1={c1} inputs={input_misses}"
        )
    print("full-corpus ranking:")
    full = sorted(
        (*score(prepared, candidate), candidate.short())
        for _, _, _, _, candidate in ranked[: args.full_top]
    )
    for output, c1, input_misses, description in full:
        print(
            f"  {description} output={output} C1={c1} inputs={input_misses}"
        )


if __name__ == "__main__":
    main()
