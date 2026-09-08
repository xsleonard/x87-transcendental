#!/usr/bin/env python3
"""Cross-validate literal multiplier-vector gates at one FCOS collision."""

from __future__ import annotations

import argparse
import collections
import itertools
import pathlib
import sys

from h382_fcos_literal_csa_carrier import bit, literal_csa_product


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
    parser.add_argument("--radius", type=int, default=64)
    parser.add_argument("--top", type=int, default=80)
    parser.add_argument("--normal-only", action="store_true")
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
    records = []
    corpus_baselines = collections.defaultdict(lambda: [0, 0])

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
            square = multiply(magnitude, magnitude, chop67).value
            if (square.mantissa & 7) != 6:
                continue
            fourth = multiply(square, square, chop67).value

            negative = multiply(fourth, constants["C5"], chop67).value
            negative = add(constants["C3"], negative, rn64).value
            negative = multiply(fourth, negative, chop67).value
            negative = add(constants["C1"], negative, rn64).value
            left_exact = multiply_exact(exact_from_p6(square), exact_from_p6(negative))
            left = quantize_exact(left_exact, chop67)[0]
            if not tail_prefix(left_exact, 3):
                continue

            positive = multiply(fourth, constants["C6"], chop67).value
            positive = add(constants["C4"], positive, rn64).value
            positive = multiply(fourth, positive, chop67).value
            positive = add(constants["C2"], positive, rn64).value
            right_exact = multiply_exact(exact_from_p6(fourth), exact_from_p6(positive))
            right = quantize_exact(right_exact, chop67)[0]
            if abs(left.scale - right.scale) != 8 or not tail_prefix(right_exact, 2):
                continue
            payload = 6
            lane_shift = (left.scale - 8) - right.scale
            lane = (
                right.significand >> lane_shift
                if lane_shift >= 0 else right.significand << -lane_shift
            ) & 0xFF
            if lane != payload:
                continue

            expected = {}
            for mode in ROUNDING_MODES:
                captured = captures[mode][index]
                assert captured is not None
                output, status = captured
                expected[mode] = (output, bool(status & CONDITION_C1))

            def cost(candidate_payload: int) -> tuple[int, int]:
                active_left = add_exact(
                    left,
                    ExactFP(left.sign, candidate_payload, left.scale - 8),
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

            baseline = cost(payload)
            candidate = cost(payload - 1)
            corpus_baselines[tag][0] += baseline[0]
            corpus_baselines[tag][1] += baseline[1]
            if baseline == candidate:
                continue

            assert (negative.mantissa & 7) == 0
            physical = square.mantissa * (negative.mantissa >> 3)
            shift = physical.bit_length() - 67
            normal = literal_csa_product(square.mantissa, negative.mantissa >> 3)
            reverse = literal_csa_product(
                square.mantissa, negative.mantissa >> 3, True
            )
            features = {}
            for name, vector in (
                ("s", normal[0]),
                ("c", normal[1]),
                ("p", normal[0] ^ normal[1]),
                ("g", normal[0] & normal[1]),
                ("rs", reverse[0]),
                ("rc", reverse[1]),
                ("rp", reverse[0] ^ reverse[1]),
                ("rg", reverse[0] & reverse[1]),
            ):
                if args.normal_only and name.startswith("r"):
                    continue
                for offset in range(-args.radius, args.radius + 1):
                    features[f"{name}{offset:+d}"] = bit(vector, shift + offset)
            for name, vectors in (("ci", normal[:2]), ("rci", reverse[:2])):
                if args.normal_only and name.startswith("r"):
                    continue
                for offset in range(-args.radius, args.radius + 1):
                    position = shift + offset
                    if position <= 0:
                        carry = 0
                    else:
                        mask = (1 << position) - 1
                        carry = (
                            ((vectors[0] & mask) + (vectors[1] & mask))
                            >> position
                        ) & 1
                    features[f"{name}{offset:+d}"] = carry
            records.append((tag, index, baseline, candidate, features))

    print(f"h390 sensitive-collisions={len(records)}")
    print("baseline by corpus:")
    for tag in sorted(corpus_baselines):
        print(
            f"  {tag}: output={corpus_baselines[tag][0]} "
            f"C1={corpus_baselines[tag][1]}"
        )
    print("sensitive rows:")
    for tag, index, baseline, candidate, _ in records:
        print(f"  {tag}:{index} base={baseline} decrement={candidate}")
    if not records:
        return

    universe = (1 << len(records)) - 1
    names = tuple(records[0][4])
    feature_masks = {
        name: sum(
            int(record[4][name]) << index for index, record in enumerate(records)
        )
        for name in names
    }
    gates = {}
    for name, mask in feature_masks.items():
        gates.setdefault(mask, name)
        gates.setdefault(universe ^ mask, f"!{name}")
    for first, second in itertools.combinations(names, 2):
        mask = feature_masks[first] ^ feature_masks[second]
        gates.setdefault(mask, f"{first}^{second}")
        gates.setdefault(universe ^ mask, f"!({first}^{second})")

    tags = tuple(sorted(corpus_baselines))
    ranked = []
    for mask, name in gates.items():
        per_tag = {tag: [0, 0] for tag in tags}
        triggered = collections.Counter()
        for record_index, (tag, _, baseline, candidate, _) in enumerate(records):
            if not (mask >> record_index) & 1:
                continue
            triggered[tag] += 1
            per_tag[tag][0] += candidate[0] - baseline[0]
            per_tag[tag][1] += candidate[1] - baseline[1]
        if any(output > 0 or c1 > 0 for output, c1 in per_tag.values()):
            continue
        improved = tuple(
            tag for tag, (output, c1) in per_tag.items()
            if output < 0 or c1 < 0
        )
        if "h389" not in improved or len(improved) < 2:
            continue
        ranked.append(
            (
                sum(value[0] for value in per_tag.values()),
                sum(value[1] for value in per_tag.values()),
                mask.bit_count(),
                name,
                improved,
                {tag: tuple(per_tag[tag]) for tag in tags},
                dict(triggered),
            )
        )
    ranked.sort()
    print(f"zero-regression gates={len(ranked)} unique_masks={len(gates)}")
    for output, c1, count, name, improved, per_tag, triggered in ranked[: args.top]:
        print(
            f"  delta=({output},{c1}) count={count} gate={name} "
            f"improved={improved} per_tag={per_tag} triggered={triggered}"
        )


if __name__ == "__main__":
    main()
