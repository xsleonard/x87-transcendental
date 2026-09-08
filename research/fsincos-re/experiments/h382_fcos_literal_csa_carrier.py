#!/usr/bin/env python3
"""Test literal radix-8/CSA multiplier state against FCOS carrier deltas."""

from __future__ import annotations

import argparse
import collections
import itertools
import pathlib
import sys


WIDTH = 144
MASK = (1 << WIDTH) - 1


def csa3(a: int, b: int, c: int) -> tuple[int, int]:
    """Return sum and already-shifted carry vectors modulo WIDTH bits."""
    total = (a ^ b ^ c) & MASK
    carry = (((a & b) | (a & c) | (b & c)) << 1) & MASK
    return total, carry


def csa4(a: int, b: int, c: int, d: int) -> tuple[int, int]:
    first_sum, first_carry = csa3(a, b, c)
    return csa3(first_sum, first_carry, d)


def booth_digit(window: int) -> int:
    """Decode one overlapping four-bit radix-8 multiplier window."""
    return (
        (window & 1)
        + ((window >> 1) & 1)
        + 2 * ((window >> 2) & 1)
        - 4 * ((window >> 3) & 1)
    )


def reduce_tree(
    inputs: list[int],
) -> tuple[int, int, tuple[tuple[int, int], ...]]:
    """Reduce 24 inputs with the documented six/three/one/one tree."""
    assert len(inputs) == 24
    level1 = tuple(
        csa4(*inputs[start : start + 4]) for start in range(0, 24, 4)
    )
    level2 = tuple(
        csa4(*level1[index], *level1[index + 1])
        for index in range(0, 6, 2)
    )
    level3 = csa4(*level2[0], *level2[1])
    final = csa4(*level3, *level2[2])
    return final[0], final[1], level1 + level2 + (level3, final)


def literal_csa_product(
    multiplicand: int, multiplier: int, reverse_products: bool = False
) -> tuple[int, int, tuple[tuple[int, int], ...]]:
    """Build the sign-generated Booth rows and reduce the literal CSA tree."""
    digits = []
    for group in range(22):
        low = 3 * group - 1
        window = 0
        for lane in range(4):
            source_bit = low + lane
            if source_bit >= 0:
                window |= ((multiplier >> source_bit) & 1) << lane
        digits.append(booth_digit(window))

    # Each generated row has the complemented sign bit shown in the 70-bit
    # partial-product forms, preceded by the two sign-generation ones.  A
    # negative row is one's complement; its +1 correction occupies a free
    # low bit of the next, three-place-shifted row.
    products = []
    for group, digit in enumerate(digits):
        magnitude = abs(digit) * multiplicand
        if digit >= 0:
            partial70 = (1 << 69) | magnitude
        else:
            partial70 = (1 << 69) - 1 - magnitude
        products.append((((3 << 70) | partial70) << (3 * group)) & MASK)
    for group, digit in enumerate(digits[:-1]):
        if digit < 0:
            correction_bit = 3 * group
            assert not bit(products[group + 1], correction_bit)
            products[group + 1] |= 1 << correction_bit
    assert digits[-1] >= 0

    if reverse_products:
        products.reverse()
    result = reduce_tree(products + [1 << 69, 0])
    # The sign-generate constants sum to exactly bit 135, leaving the low
    # 135 bits equal to the unsigned significand product.
    assert ((result[0] + result[1]) & ((1 << 135) - 1)) == (
        multiplicand * multiplier
    )
    return result


def bit(value: int, position: int) -> int:
    return 0 if position < 0 else (value >> position) & 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("constants", type=pathlib.Path, help="public sibling-constants.json")
    parser.add_argument("inputs", type=pathlib.Path)
    parser.add_argument("capture_directory", type=pathlib.Path)
    parser.add_argument("capture_stem")
    parser.add_argument("--radius", type=int, default=24)
    parser.add_argument("--top", type=int, default=32)
    parser.add_argument("--distance-scaled", action="store_true")
    parser.add_argument(
        "--collision",
        help="restrict the bit census to DISTANCE,YLOW aligned-lane collisions",
    )
    parser.add_argument("--right-prefix-bits", type=int, default=0)
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
    records = []

    for index, (sign_exponent, significand) in enumerate(inputs):
        if sign_exponent >> 15 or direct_region(sign_exponent, significand) != "small":
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
        left_discarded = left_exact.significand & ((1 << left_shift) - 1)
        tail3 = (left_discarded << 3) >> left_shift

        positive = multiply(tmp2, constants["C6"], chop67).value
        positive = add(constants["C4"], positive, rn64).value
        positive = multiply(tmp2, positive, chop67).value
        positive = add(constants["C2"], positive, rn64).value
        right_product_exact = multiply_exact(
            exact_from_p6(tmp2), exact_from_p6(positive)
        )
        right = quantize_exact(right_product_exact, chop67)[0]
        right_shift = right_product_exact.significand.bit_length() - 67
        right_discarded = (
            right_product_exact.significand & ((1 << right_shift) - 1)
            if right_shift > 0 else 0
        )

        expected = {}
        for mode in ROUNDING_MODES:
            captured = captures[mode][index]
            assert captured is not None
            output, status = captured
            expected[mode] = (output, bool(status & CONDITION_C1))

        def payload_matches(payload: int) -> bool:
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
            observed = {}
            for mode in ROUNDING_MODES:
                result = add(one, correction, final_quantizations[mode])
                observed[mode] = (
                    extended_from_p6(result.value, mode)[0], result.incremented
                )
            return observed == expected

        distance = abs(left.scale - right.scale)
        nominal = (tmp1.mantissa & 7) if tail3 else 0
        if args.distance_scaled and nominal:
            nominal += 8 - distance
        if payload_matches(nominal):
            delta = 0
        elif payload_matches(nominal - 1):
            delta = -1
        elif payload_matches(nominal + 1):
            delta = 1
        else:
            continue

        assert (negative.mantissa & 7) == 0
        sum_vector, carry_vector, levels = literal_csa_product(
            tmp1.mantissa, negative.mantissa >> 3
        )
        reverse_sum, reverse_carry, reverse_levels = literal_csa_product(
            tmp1.mantissa, negative.mantissa >> 3, True
        )
        physical_product = tmp1.mantissa * (negative.mantissa >> 3)
        physical_shift = physical_product.bit_length() - 67
        records.append(
            (
                index,
                delta,
                physical_shift,
                sum_vector,
                carry_vector,
                levels,
                reverse_sum,
                reverse_carry,
                reverse_levels,
                distance,
                tmp1.mantissa & 7,
                negative.mantissa & 0xFF,
                right.significand & 0xFF,
                nominal,
                (
                    (right_discarded << args.right_prefix_bits) >> right_shift
                    if right_shift > 0 and args.right_prefix_bits else 0
                ),
            )
        )

    if args.collision:
        distance_text, ylow_text = args.collision.split(",")
        selected_distance = int(distance_text)
        selected_ylow = int(ylow_text)
        records = [
            record for record in records
            if record[9] == selected_distance
            and record[10] == selected_ylow
            and record[12] == (record[13] & 0xFF)
            and (not args.right_prefix_bits or record[14])
        ]

    census = collections.Counter(record[1] for record in records)
    print(f"h382 classified={len(records)} deltas={dict(sorted(census.items()))}")
    print(
        "delta/exponent-distance="
        f"{dict(sorted(collections.Counter((record[1], record[9]) for record in records).items()))}"
    )
    print("residual rows:")
    for record in records:
        if record[1]:
            print(
                f"  row={record[0]} delta={record[1]:+d} d={record[9]} "
                f"ylow={record[10]} payload={record[13]} "
                f"nlow={record[11]:02x} rlow={record[12]:02x}"
            )

    feature_values: dict[str, list[int]] = {}
    offsets = range(-args.radius, args.radius + 1)
    for name, vector_index in (("s", 3), ("c", 4), ("rs", 6), ("rc", 7)):
        for offset in offsets:
            feature_values[f"{name}{offset:+d}"] = [
                bit(record[vector_index], record[2] + offset) for record in records
            ]
    feature_values.update(
        {
            f"p{offset:+d}": [
                bit(record[3] ^ record[4], record[2] + offset)
                for record in records
            ]
            for offset in offsets
        }
    )
    feature_values.update(
        {
            f"rp{offset:+d}": [
                bit(record[6] ^ record[7], record[2] + offset)
                for record in records
            ]
            for offset in offsets
        }
    )
    feature_values.update(
        {
            f"rg{offset:+d}": [
                bit(record[6] & record[7], record[2] + offset)
                for record in records
            ]
            for offset in offsets
        }
    )
    feature_values.update(
        {
            f"g{offset:+d}": [
                bit(record[3] & record[4], record[2] + offset)
                for record in records
            ]
            for offset in offsets
        }
    )
    targets = [record[1] for record in records]
    universe = (1 << len(records)) - 1
    target_masks = {
        target: sum(1 << index for index, value in enumerate(targets) if value == target)
        for target in (-1, 0, 1)
    }
    residual_count = (target_masks[-1] | target_masks[1]).bit_count()
    feature_masks = {
        name: sum(1 << index for index, value in enumerate(values) if value)
        for name, values in feature_values.items()
    }

    def difference_errors(first: int, second: int) -> tuple[int, int, int, int]:
        positive = first & (universe ^ second)
        negative = (universe ^ first) & second
        nonzero = positive | negative
        correct_positive = (positive & target_masks[1]).bit_count()
        correct_negative = (negative & target_masks[-1]).bit_count()
        correct_zero = ((universe ^ nonzero) & target_masks[0]).bit_count()
        residual = residual_count - correct_positive - correct_negative
        false_nonzero = (nonzero & target_masks[0]).bit_count()
        missed_nonzero = (
            (universe ^ nonzero) & (target_masks[-1] | target_masks[1])
        ).bit_count()
        return (
            len(records) - correct_positive - correct_negative - correct_zero,
            residual,
            false_nonzero,
            missed_nonzero,
        )

    ranked = []
    names = tuple(feature_values)
    for first_name, second_name in itertools.product(names, repeat=2):
        ranked.append(
            (
                difference_errors(
                    feature_masks[first_name], feature_masks[second_name]
                ),
                first_name,
                second_name,
            )
        )
    ranked.sort()
    print("best direct bit differences (total/residual/false/missed):")
    for score, first_name, second_name in ranked[: args.top]:
        print(f"  {score}: {first_name}-{second_name}")
    print("best residual-covering bit differences:")
    for score, first_name, second_name in sorted(
        ranked, key=lambda item: (item[0][1], item[0][0])
    )[: args.top]:
        print(f"  {score}: {first_name}-{second_name}")

    learned = []
    for first_name, second_name in itertools.combinations(names, 2):
        first = feature_masks[first_name]
        second = feature_masks[second_name]
        table = {}
        predictions = {-1: 0, 0: 0, 1: 0}
        conflicts = 0
        for a, b in itertools.product((0, 1), repeat=2):
            key_mask = (first if a else universe ^ first) & (
                second if b else universe ^ second
            )
            counts = {
                target: (key_mask & target_masks[target]).bit_count()
                for target in (-1, 0, 1)
            }
            selected = max(counts, key=lambda target: (counts[target], target == 0))
            table[a, b] = selected
            predictions[selected] |= key_mask
            conflicts += key_mask.bit_count() - counts[selected]
        correct = sum(
            (predictions[target] & target_masks[target]).bit_count()
            for target in (-1, 0, 1)
        )
        residual_correct = sum(
            (predictions[target] & target_masks[target]).bit_count()
            for target in (-1, 1)
        )
        false_nonzero = (
            (predictions[-1] | predictions[1]) & target_masks[0]
        ).bit_count()
        missed_nonzero = (
            predictions[0] & (target_masks[-1] | target_masks[1])
        ).bit_count()
        score = (
            len(records) - correct,
            residual_count - residual_correct,
            false_nonzero,
            missed_nonzero,
        )
        learned.append((score, conflicts, first_name, second_name, table))
    learned.sort()
    print("best learned two-bit tables:")
    for score, conflicts, first_name, second_name, table in learned[: args.top]:
        print(
            f"  {score} conflicts={conflicts}: {first_name},{second_name} "
            f"table={table}"
        )
    print("best residual-covering learned two-bit tables:")
    for score, conflicts, first_name, second_name, table in sorted(
        learned, key=lambda item: (item[0][1], item[0][0])
    )[: args.top]:
        print(
            f"  {score} conflicts={conflicts}: {first_name},{second_name} "
            f"table={table}"
        )


if __name__ == "__main__":
    main()
