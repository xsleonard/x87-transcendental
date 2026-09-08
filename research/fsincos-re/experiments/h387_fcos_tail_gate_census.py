#!/usr/bin/env python3
"""Find cross-corpus FCOS carrier gates from aligned lanes and product tails."""

from __future__ import annotations

import argparse
import collections
import pathlib
import sys


LANE_MODES = ("chop", "ceil", "rn", "odd", "halfup")


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
            elif mode == "halfup":
                if remainder >= 1 << (shift - 1):
                    magnitude += 1
            elif mode != "chop":
                raise ValueError(mode)
    return -magnitude if exact.sign else magnitude


def tail_prefix(exact, bits: int, retained_bits: int = 67) -> int:
    shift = exact.significand.bit_length() - retained_bits
    if shift <= 0:
        return 0
    discarded = exact.significand & ((1 << shift) - 1)
    return (discarded << bits) >> shift


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("constants", type=pathlib.Path, help="public sibling-constants.json")
    parser.add_argument(
        "--corpus",
        action="append",
        required=True,
        help="TAG,INPUT,CAPTURE_DIRECTORY,CAPTURE_STEM",
    )
    parser.add_argument("--top", type=int, default=80)
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
    finals = {mode: Quantization(64, mode) for mode in ROUNDING_MODES}
    one = constants["one"]
    sensitive = []
    corpus_baselines = collections.defaultdict(lambda: [0, 0, 0])

    for specification in args.corpus:
        tag, input_text, capture_text, stem = specification.split(",")
        inputs = [
            tuple(int(field, 16) for field in line.split())
            for line in pathlib.Path(input_text).read_text().splitlines()
            if line.strip()
        ]
        capture_directory = pathlib.Path(capture_text)
        captures = {
            mode: [
                parse_capture(line, "cos")
                for line in (
                    capture_directory / f"{stem}_{mode}_status.txt"
                ).read_text().splitlines()
            ]
            for mode in ROUNDING_MODES
        }

        for index, (sign_exponent, significand) in enumerate(inputs):
            if sign_exponent >> 15 or direct_region(sign_exponent, significand) != "small":
                continue
            value = p6_from_extended(sign_exponent, significand)
            magnitude = P6Value.from_fields(0, value.exponent, value.mantissa)
            square_exact = multiply_exact(
                exact_from_p6(magnitude), exact_from_p6(magnitude)
            )
            square = multiply(magnitude, magnitude, chop67).value
            fourth = multiply(square, square, chop67).value

            negative = multiply(fourth, constants["C5"], chop67).value
            negative = add(constants["C3"], negative, rn64).value
            negative = multiply(fourth, negative, chop67).value
            negative = add(constants["C1"], negative, rn64).value
            left_exact = multiply_exact(exact_from_p6(square), exact_from_p6(negative))
            left = quantize_exact(left_exact, chop67)[0]

            positive = multiply(fourth, constants["C6"], chop67).value
            positive = add(constants["C4"], positive, rn64).value
            positive = multiply(fourth, positive, chop67).value
            positive = add(constants["C2"], positive, rn64).value
            right_exact = multiply_exact(exact_from_p6(fourth), exact_from_p6(positive))
            right = quantize_exact(right_exact, chop67)[0]

            distance = abs(left.scale - right.scale)
            ylow = square.mantissa & 7
            active = bool(
                ylow and (
                    tail_prefix(left_exact, 3)
                    or (distance == 7 and tail_prefix(left_exact, 5))
                )
            )
            if not active:
                continue
            payload = ylow + 8 - distance
            chop_lane = align_integer(right, left.scale - 8, "chop") & 0xFF
            chop_difference = (chop_lane - payload) & 0xFF
            if chop_difference >= 128:
                chop_difference -= 256
            if (
                distance == 10
                and ylow == 6
                and chop_difference == -2
                and tail_prefix(right_exact, 1)
            ):
                payload = chop_lane
            elif (
                distance == 8
                and ylow == 7
                and chop_difference == 0
                and tail_prefix(left_exact, 3) >= 3
            ):
                payload -= 1

            expected = {}
            for mode in ROUNDING_MODES:
                captured = captures[mode][index]
                assert captured is not None
                output, status = captured
                expected[mode] = (output, bool(status & CONDITION_C1))

            def cost(candidate_payload: int) -> tuple[int, int]:
                active_left = left
                if candidate_payload:
                    active_left = add_exact(
                        left,
                        ExactFP(
                            left.sign ^ int(candidate_payload < 0),
                            abs(candidate_payload),
                            left.scale - 8,
                        ),
                    )
                correction = materialize_exact(
                    add_exact(active_left, right), chop67
                ).value
                output_misses = c1_misses = 0
                for mode in ROUNDING_MODES:
                    result = add(one, correction, finals[mode])
                    observed = (
                        extended_from_p6(result.value, mode)[0],
                        result.incremented,
                    )
                    output_misses += observed[0] != expected[mode][0]
                    c1_misses += observed[1] != expected[mode][1]
                return output_misses, c1_misses

            costs = {delta: cost(payload + delta) for delta in range(-3, 4)}
            baseline = costs[0]
            corpus_baselines[tag][0] += baseline[0]
            corpus_baselines[tag][1] += baseline[1]
            corpus_baselines[tag][2] += bool(baseline[0] or baseline[1])
            if all(candidate == baseline for candidate in costs.values()):
                continue
            lane_differences = {}
            for mode in LANE_MODES:
                lane = align_integer(right, left.scale - 8, mode) & 0xFF
                difference = (lane - payload) & 0xFF
                lane_differences[mode] = difference - 256 if difference >= 128 else difference
            sensitive.append(
                (
                    tag,
                    distance,
                    ylow,
                    lane_differences,
                    {
                        "left": tuple(tail_prefix(left_exact, bits) for bits in range(1, 9)),
                        "right": tuple(tail_prefix(right_exact, bits) for bits in range(1, 9)),
                        "square": tuple(tail_prefix(square_exact, bits) for bits in range(1, 9)),
                    },
                    baseline,
                    costs,
                )
            )

    aggregates = {}
    for tag, distance, ylow, lane_differences, tails, baseline, costs in sensitive:
        for lane_mode, lane_difference in lane_differences.items():
            if not -4 <= lane_difference <= 4:
                continue
            for tail_source, prefixes in tails.items():
                for bits, prefix in enumerate(prefixes, 1):
                    for threshold in range(1, prefix + 1):
                        for delta in (-3, -2, -1, 1, 2, 3):
                            candidate_cost = costs[delta]
                            key = (
                                distance,
                                ylow,
                                lane_mode,
                                lane_difference,
                                tail_source,
                                bits,
                                "ge",
                                threshold,
                                delta,
                            )
                            per_tag = aggregates.setdefault(
                                key, collections.defaultdict(lambda: [0, 0, 0, 0])
                            )
                            values = per_tag[tag]
                            values[0] += candidate_cost[0] - baseline[0]
                            values[1] += candidate_cost[1] - baseline[1]
                            values[2] += bool(baseline[0] or baseline[1])
                            values[3] += bool(candidate_cost[0] or candidate_cost[1])
                tail8 = prefixes[7]
                for bit in range(8):
                    state = bool(tail8 & (1 << bit))
                    for delta in (-3, -2, -1, 1, 2, 3):
                        candidate_cost = costs[delta]
                        key = (
                            distance,
                            ylow,
                            lane_mode,
                            lane_difference,
                            tail_source,
                            8,
                            "bit",
                            bit,
                            state,
                            delta,
                        )
                        per_tag = aggregates.setdefault(
                            key, collections.defaultdict(lambda: [0, 0, 0, 0])
                        )
                        values = per_tag[tag]
                        values[0] += candidate_cost[0] - baseline[0]
                        values[1] += candidate_cost[1] - baseline[1]
                        values[2] += bool(baseline[0] or baseline[1])
                        values[3] += bool(candidate_cost[0] or candidate_cost[1])

    survivors = []
    tags = tuple(sorted(corpus_baselines))
    for key, per_tag in aggregates.items():
        deltas = {tag: tuple(per_tag[tag][:2]) for tag in tags}
        if any(output > 0 or c1 > 0 for output, c1 in deltas.values()):
            continue
        improved_tags = tuple(
            tag for tag, (output, c1) in deltas.items() if output < 0 or c1 < 0
        )
        if len(improved_tags) < 2:
            continue
        total_output = sum(value[0] for value in deltas.values())
        total_c1 = sum(value[1] for value in deltas.values())
        survivors.append(
            (
                total_output,
                total_c1,
                -len(improved_tags),
                key,
                improved_tags,
                deltas,
            )
        )
    survivors.sort()
    print(
        f"h387 sensitive={len(sensitive)} candidates={len(aggregates)} "
        f"cross-corpus-zero-regression={len(survivors)}"
    )
    print("baseline by corpus:")
    for tag in tags:
        print(f"  {tag}: output={corpus_baselines[tag][0]} C1={corpus_baselines[tag][1]}")
    for output, c1, _, key, improved_tags, deltas in survivors[: args.top]:
        print(
            f"  delta=({output},{c1}) key={key} "
            f"improved={improved_tags} per_tag={deltas}"
        )
    print("best distinct exponent-distance/ylow classes:")
    seen_classes = set()
    for output, c1, _, key, improved_tags, deltas in survivors:
        carrier_class = key[:2]
        if carrier_class in seen_classes:
            continue
        seen_classes.add(carrier_class)
        print(
            f"  delta=({output},{c1}) class={carrier_class} key={key} "
            f"improved={improved_tags} per_tag={deltas}"
        )


if __name__ == "__main__":
    main()
