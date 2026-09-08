#!/usr/bin/env python3
"""Search a fractional retained tail in the final FCOS polynomial combine.

The scalar model materializes both terminal products at 67 bits before their
signed combine.  This experiment retains a dyadic fraction of the discarded
tail of the negative terminal product, then performs the usual chopped
67-bit combine.  It is a compact proxy for a partially propagated multiplier
carrier rather than a change to either polynomial coefficient.
"""

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
    parser.add_argument("--fraction-bits", type=int, default=10)
    parser.add_argument("--control-count", type=int, default=8192)
    parser.add_argument("--full-top", type=int, default=16)
    parser.add_argument("--region", choices=("small", "all"), default="small")
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
        negate,
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

    prepared = []
    baseline_misses = []
    for index, (sign_exponent, significand) in enumerate(inputs):
        region = direct_region(sign_exponent, significand)
        if region is None or (args.region != "all" and region != args.region):
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
        tail = add_exact(left_exact, negate(left))

        positive = multiply(tmp2, constants["C6"], chop67).value
        positive = add(constants["C4"], positive, rn64).value
        positive = multiply(tmp2, positive, chop67).value
        positive = add(constants["C2"], positive, rn64).value
        right_exact = multiply_exact(exact_from_p6(tmp2), exact_from_p6(positive))
        right = quantize_exact(right_exact, chop67)[0]
        base = add_exact(left, right)

        expected = {}
        for mode in ROUNDING_MODES:
            captured = captures[mode][index]
            assert captured is not None
            output, status = captured
            expected[mode] = (output, bool(status & CONDITION_C1))
        record = (base, tail, expected)
        prepared.append(record)

        correction = materialize_exact(base, chop67).value
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
    denominator = 1 << args.fraction_bits

    final_quantizations = {
        mode: Quantization(64, mode) for mode in ROUNDING_MODES
    }

    def record_score(correction, expected):
        output_misses = c1_misses = 0
        any_miss = False
        for mode in ROUNDING_MODES:
            result = add(one, correction, final_quantizations[mode])
            observed = (
                extended_from_p6(result.value, mode)[0],
                result.incremented,
            )
            output_miss = observed[0] != expected[mode][0]
            c1_miss = observed[1] != expected[mode][1]
            output_misses += output_miss
            c1_misses += c1_miss
            any_miss |= output_miss or c1_miss
        return output_misses, c1_misses, int(any_miss)

    def correction_at(base, tail, numerator):
        if numerator and not tail.is_zero:
            retained_tail = ExactFP(
                tail.sign,
                tail.significand * numerator,
                tail.scale - args.fraction_bits,
            )
            combined = add_exact(base, retained_tail)
        else:
            combined = base
        return materialize_exact(combined, chop67).value

    def score_curve(points):
        """Score every fraction by recording monotone correction transitions."""

        deltas = [[0, 0, 0] for _ in range(denominator + 1)]
        baseline = [0, 0, 0]
        transition_count = 0
        for base, tail, expected in points:
            cache = {
                0: correction_at(base, tail, 0),
                denominator: correction_at(base, tail, denominator),
            }
            initial_score = record_score(cache[0], expected)
            for metric in range(3):
                baseline[metric] += initial_score[metric]

            transitions = []

            def locate(low, high):
                low_value = cache[low]
                high_value = cache[high]
                if low_value == high_value:
                    return
                if high == low + 1:
                    transitions.append((high, low_value, high_value))
                    return
                middle = (low + high) // 2
                cache.setdefault(middle, correction_at(base, tail, middle))
                locate(low, middle)
                locate(middle, high)

            locate(0, denominator)
            transitions.sort()
            transition_count += len(transitions)
            current_score = initial_score
            for numerator, _old_value, new_value in transitions:
                new_score = record_score(new_value, expected)
                for metric in range(3):
                    deltas[numerator][metric] += (
                        new_score[metric] - current_score[metric]
                    )
                current_score = new_score

        scores = []
        current = baseline
        for numerator in range(denominator + 1):
            if numerator:
                current = [
                    current[metric] + deltas[numerator][metric]
                    for metric in range(3)
                ]
            scores.append((*current, numerator))
        return scores, transition_count

    def score(points, numerator):
        output_misses = c1_misses = input_misses = 0
        for base, tail, expected in points:
            correction = correction_at(base, tail, numerator)
            record_output, record_c1, record_input = record_score(
                correction, expected
            )
            output_misses += record_output
            c1_misses += record_c1
            input_misses += record_input
        return output_misses, c1_misses, input_misses

    selected_curve, selected_transitions = score_curve(selected)
    ranked = sorted(selected_curve)
    print(
        f"h371 inputs={len(prepared)} baseline-input-misses={len(baseline_misses)} "
        f"selected={len(selected)} fractions={denominator + 1} "
        f"selected-transitions={selected_transitions}"
    )
    print("selected ranking:")
    for output, c1, input_misses, numerator in ranked[:24]:
        print(
            f"  alpha={numerator}/{denominator} output={output} "
            f"C1={c1} inputs={input_misses}"
        )
    print("full-corpus curve ranking:")
    full_curve, full_transitions = score_curve(prepared)
    full_ranked = sorted(full_curve)
    print(f"full-transitions={full_transitions}")
    for output, c1, input_misses, numerator in full_ranked:
        print(
            f"  alpha={numerator}/{denominator} output={output} "
            f"C1={c1} inputs={input_misses}"
        )
        if numerator == full_ranked[min(23, len(full_ranked) - 1)][3]:
            break

if __name__ == "__main__":
    main()
