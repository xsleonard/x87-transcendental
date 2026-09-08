#!/usr/bin/env python3
"""Search literal retained-grid choices at FCOS's terminal subtraction."""

from __future__ import annotations

import argparse
import pathlib
import sys


MODES = ("chop", "ceil", "rn", "odd")


def align_integer(exact, grid_scale: int, mode: str) -> int:
    """Materialize one magnitude on a fixed-point FADD input grid."""
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
                if remainder > half or (
                    remainder == half and (magnitude & 1)
                ):
                    magnitude += 1
            elif mode == "halfup":
                if remainder >= 1 << (shift - 1):
                    magnitude += 1
            elif mode == "odd":
                magnitude |= 1
            elif mode != "chop":
                raise ValueError(mode)
    return -magnitude if exact.sign else magnitude


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("constants", type=pathlib.Path, help="public sibling-constants.json")
    parser.add_argument("inputs", type=pathlib.Path)
    parser.add_argument("capture_directory", type=pathlib.Path)
    parser.add_argument("capture_stem")
    parser.add_argument("--minimum-depth", type=int, default=5)
    parser.add_argument("--maximum-depth", type=int, default=12)
    parser.add_argument("--top", type=int, default=40)
    parser.add_argument("--show-route-misses", type=int, default=0)
    parser.add_argument("--evaluate", action="append", default=[])
    parser.add_argument("--payload-affine-search", action="store_true")
    parser.add_argument("--evaluate-payload-affine", action="append", default=[])
    parser.add_argument("--tail-replay-search", action="store_true")
    parser.add_argument("--lane-borrow-search", action="store_true")
    parser.add_argument("--evaluate-lane-borrow", action="append", default=[])
    parser.add_argument("--resolution-search", action="store_true")
    parser.add_argument("--evaluate-resolution", action="append", default=[])
    parser.add_argument("--activation-search", action="store_true")
    parser.add_argument("--evaluate-activation", action="append", type=int, default=[])
    parser.add_argument("--activation-distance-search", action="store_true")
    parser.add_argument("--evaluate-activation-distance", action="append", default=[])
    parser.add_argument("--right-lane-replacement-search", action="store_true")
    parser.add_argument("--evaluate-right-lane-replacement", action="append", default=[])
    parser.add_argument("--right-lane-delta-search", action="store_true")
    parser.add_argument("--evaluate-right-lane-delta", action="append", default=[])
    parser.add_argument("--evaluate-right-tail-gate", action="append", default=[])
    parser.add_argument("--evaluate-left-tail-gate", action="append", default=[])
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
    prepared = []

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
        left_prefixes = tuple(
            (left_discarded << bits) >> left_shift for bits in range(1, 17)
        )
        payload = (tmp1.mantissa & 7) if tail3 else 0
        active_left = left
        if payload:
            active_left = add_exact(
                left, ExactFP(left.sign, payload, left.scale - 8)
            )

        positive = multiply(tmp2, constants["C6"], chop67).value
        positive = add(constants["C4"], positive, rn64).value
        positive = multiply(tmp2, positive, chop67).value
        positive = add(constants["C2"], positive, rn64).value
        right_product_exact = multiply_exact(
            exact_from_p6(tmp2), exact_from_p6(positive)
        )
        right = quantize_exact(right_product_exact, chop67)[0]
        left_tail = add_exact(left_exact, negate(left))
        right_tail = add_exact(right_product_exact, negate(right))
        right_shift = right_product_exact.significand.bit_length() - 67
        right_discarded = (
            right_product_exact.significand & ((1 << right_shift) - 1)
            if right_shift > 0 else 0
        )
        right_prefixes = tuple(
            (right_discarded << bits) >> right_shift
            for bits in range(1, 9)
        )

        expected = {}
        for mode in ROUNDING_MODES:
            captured = captures[mode][index]
            assert captured is not None
            output, status = captured
            expected[mode] = (output, bool(status & CONDITION_C1))
        prepared.append(
            (
                left,
                payload,
                active_left,
                left.scale,
                right,
                expected,
                abs(left.scale - right.scale),
                left_tail,
                right_tail,
                left_prefixes,
                tmp1.mantissa & 7,
                index,
                right_prefixes,
            )
        )

    routes = [("exact", 8, "exact", "exact")]
    if args.evaluate:
        for specification in args.evaluate:
            depth_text, left_mode, right_mode = specification.split(",")
            depth = int(depth_text)
            routes.append(
                (f"grid{depth}-{left_mode}-{right_mode}", depth, left_mode, right_mode)
            )
    elif args.evaluate_payload_affine:
        for specification in args.evaluate_payload_affine:
            bias_text, slope_text, clamp = specification.split(",")
            bias = int(bias_text)
            slope = int(slope_text)
            routes.append(
                (
                    f"payload-b{bias:+d}-s{slope:+d}-{clamp}",
                    -1000 + bias,
                    str(slope),
                    clamp,
                )
            )
    elif args.evaluate_lane_borrow:
        for specification in args.evaluate_lane_borrow:
            source, mode, minus_text, plus_text = specification.split(",")
            routes.append(
                (
                    f"lane-{source}-{mode}-m{int(minus_text):+d}-p{int(plus_text):+d}",
                    -3000,
                    f"{source},{mode},{int(minus_text)}",
                    str(int(plus_text)),
                )
            )
    elif args.evaluate_resolution:
        for specification in args.evaluate_resolution:
            source, mode, radius_text, tie = specification.split(",")
            routes.append(
                (
                    f"resolve-{source}-{mode}-r{int(radius_text)}-{tie}",
                    -4000,
                    f"{source},{mode},{int(radius_text)}",
                    tie,
                )
            )
    elif args.evaluate_activation:
        routes.extend(
            (f"activation-top{bits}", -5000, str(bits), "none")
            for bits in args.evaluate_activation
        )
    elif args.evaluate_activation_distance:
        for specification in args.evaluate_activation_distance:
            distance_text, bits_text = specification.split(",")
            routes.append(
                (
                    f"activation-d{int(distance_text)}-top{int(bits_text)}",
                    -5000,
                    f"{int(distance_text)},{int(bits_text)}",
                    "none",
                )
            )
    elif args.evaluate_right_lane_replacement:
        for specification in args.evaluate_right_lane_replacement:
            distance_text, mode, radius_text = specification.split(",")
            routes.append(
                (
                    f"right-lane-d{int(distance_text)}-{mode}-r{int(radius_text)}",
                    -6000,
                    f"{int(distance_text)},{mode},{int(radius_text)}",
                    "none",
                )
            )
    elif args.evaluate_right_lane_delta:
        for specification in args.evaluate_right_lane_delta:
            distance_text, mode, delta_text = specification.split(",")
            routes.append(
                (
                    f"right-delta-d{int(distance_text)}-{mode}-{int(delta_text):+d}",
                    -7000,
                    f"{int(distance_text)},{mode},{int(delta_text)}",
                    "none",
                )
            )
    elif args.evaluate_right_tail_gate:
        for specification in args.evaluate_right_tail_gate:
            distance_text, mode, delta_text, ylow_text, bits_text = specification.split(",")
            routes.append(
                (
                    f"right-tail-d{int(distance_text)}-{mode}-{int(delta_text):+d}"
                    f"-y{int(ylow_text)}-t{int(bits_text)}",
                    -8000,
                    ",".join((distance_text, mode, delta_text, ylow_text, bits_text)),
                    "none",
                )
            )
    elif args.evaluate_left_tail_gate:
        for specification in args.evaluate_left_tail_gate:
            fields = specification.split(",")
            if len(fields) == 6:
                (
                    distance_text,
                    mode,
                    lane_delta_text,
                    ylow_text,
                    bits_text,
                    payload_delta_text,
                ) = fields
                source = "left"
                threshold_text = "1"
            elif len(fields) == 7:
                (
                    distance_text,
                    mode,
                    lane_delta_text,
                    ylow_text,
                    bits_text,
                    threshold_text,
                    payload_delta_text,
                ) = fields
                source = "left"
            else:
                (
                    distance_text,
                    mode,
                    lane_delta_text,
                    ylow_text,
                    source,
                    bits_text,
                    threshold_text,
                    payload_delta_text,
                ) = fields
            routes.append(
                (
                    f"left-tail-d{int(distance_text)}-{mode}"
                    f"-lane{int(lane_delta_text):+d}-y{int(ylow_text)}"
                    f"-{source}-t{int(bits_text)}>={int(threshold_text)}"
                    f"-p{int(payload_delta_text):+d}",
                    -9000,
                    ",".join(
                        (
                            distance_text,
                            mode,
                            lane_delta_text,
                            ylow_text,
                            source,
                            bits_text,
                            threshold_text,
                            payload_delta_text,
                        )
                    ),
                    "none",
                )
            )
    else:
        if args.tail_replay_search:
            routes.extend(
                (
                    f"tail-{source}-grid{depth}-{mode}",
                    -2000 + depth,
                    source,
                    mode,
                )
                for source in ("left", "right", "both")
                for depth in range(5, 13)
                for mode in MODES
            )
            routes.append(("affine-exact", -2000, "none", "chop"))
        elif args.lane_borrow_search:
            routes.extend(
                (
                    f"lane-{source}-{mode}-m{minus:+d}-p{plus:+d}",
                    -3000,
                    f"{source},{mode},{minus}",
                    str(plus),
                )
                for source in ("chop", "exact")
                for mode in MODES
                for minus in range(-2, 3)
                for plus in range(-2, 3)
            )
            routes.append(("affine-exact", -2000, "none", "chop"))
        elif args.resolution_search:
            routes.extend(
                (
                    f"resolve-{source}-{mode}-r{radius}-{tie}",
                    -4000,
                    f"{source},{mode},{radius}",
                    tie,
                )
                for source in ("chop", "exact")
                for mode in MODES
                for radius in range(4)
                for tie in ("down", "up", "tail", "reverse-tail", "none")
            )
            routes.append(("affine-exact", -2000, "none", "chop"))
        elif args.activation_search:
            routes.extend(
                (f"activation-top{bits}", -5000, str(bits), "none")
                for bits in range(1, 17)
            )
            routes.append(("affine-exact", -2000, "none", "chop"))
        elif args.activation_distance_search:
            routes.extend(
                (
                    f"activation-d{selected_distance}-top{bits}",
                    -5000,
                    f"{selected_distance},{bits}",
                    "none",
                )
                for selected_distance in range(7, 11)
                for bits in range(1, 17)
            )
            routes.append(("affine-exact", -2000, "none", "chop"))
        elif args.right_lane_replacement_search:
            routes.extend(
                (
                    f"right-lane-d{selected_distance}-{mode}-r{radius}",
                    -6000,
                    f"{selected_distance},{mode},{radius}",
                    "none",
                )
                for selected_distance in range(7, 11)
                for mode in (*MODES, "halfup")
                for radius in range(1, 5)
            )
            routes.append(("affine-exact", -2000, "none", "chop"))
        elif args.right_lane_delta_search:
            routes.extend(
                (
                    f"right-delta-d{selected_distance}-{mode}-{selected_delta:+d}",
                    -7000,
                    f"{selected_distance},{mode},{selected_delta}",
                    "none",
                )
                for selected_distance in range(7, 11)
                for mode in (*MODES, "halfup")
                for selected_delta in range(-4, 5)
                if selected_delta
            )
            routes.append(("affine-exact", -2000, "none", "chop"))
        elif args.payload_affine_search:
            routes.extend(
                (
                    f"payload-b{bias:+d}-s{slope:+d}-{clamp}",
                    -1000 + bias,
                    str(slope),
                    clamp,
                )
                for bias in range(-4, 5)
                for slope in range(-3, 4)
                for clamp in ("raw", "zero", "seven")
            )
        else:
            routes.extend(
                (f"grid{depth}-{left_mode}-{right_mode}", depth, left_mode, right_mode)
                for depth in range(args.minimum_depth, args.maximum_depth + 1)
                for left_mode in MODES
                for right_mode in MODES
            )
    scores = []
    distance_scores = []
    for route_name, depth, left_mode, right_mode in routes:
        output_misses = c1_misses = input_misses = 0
        shown_route_misses = 0
        by_distance = {
            distance: [0, 0, 0] for distance in sorted({row[6] for row in prepared})
        }
        for (
            base_left,
            payload,
            left,
            left_base_scale,
            right,
            expected,
            distance,
            left_tail,
            right_tail,
            left_prefixes,
            ylow,
            input_index,
            right_prefixes,
        ) in prepared:
            if depth <= -8900:
                (
                    selected_text,
                    lane_mode,
                    lane_delta_text,
                    ylow_text,
                    source,
                    bits_text,
                    threshold_text,
                    payload_delta_text,
                ) = left_mode.split(",")
                active = bool(
                    payload or (
                        distance == 7 and ylow and left_prefixes[4]
                    )
                )
                affine_payload = ylow + 8 - distance if active else 0
                adjusted_payload = affine_payload
                lane_integer = align_integer(
                    right, base_left.scale - 8, lane_mode
                )
                lane_payload = lane_integer & 0xFF
                difference = (lane_payload - affine_payload) & 0xFF
                if difference >= 128:
                    difference -= 256

                # Preserve the independently validated distance-10 resolution.
                if (
                    active
                    and distance == 10
                    and ylow == 6
                    and right_prefixes[0]
                    and difference == -2
                ):
                    adjusted_payload = lane_payload

                if (
                    active
                    and distance == 8
                    and ylow == 7
                    and left_prefixes[2] >= 3
                    and difference == 0
                ):
                    adjusted_payload -= 1

                if (
                    active
                    and distance == int(selected_text)
                    and ylow == int(ylow_text)
                    and (
                        left_prefixes
                        if source == "left" else right_prefixes
                    )[int(bits_text) - 1] >= int(threshold_text)
                    and difference == int(lane_delta_text)
                ):
                    adjusted_payload += int(payload_delta_text)
                adjusted_left = base_left
                if active and adjusted_payload:
                    adjusted_left = add_exact(
                        base_left,
                        ExactFP(
                            base_left.sign ^ int(adjusted_payload < 0),
                            abs(adjusted_payload),
                            base_left.scale - 8,
                        ),
                    )
                combined = add_exact(adjusted_left, right)
            elif route_name == "exact":
                combined = add_exact(left, right)
            elif depth <= -7900:
                (
                    selected_text,
                    lane_mode,
                    delta_text,
                    ylow_text,
                    bits_text,
                ) = left_mode.split(",")
                active = bool(
                    payload or (
                        distance == 7 and ylow and left_prefixes[4]
                    )
                )
                affine_payload = ylow + 8 - distance if active else 0
                adjusted_payload = affine_payload
                if (
                    active
                    and distance == int(selected_text)
                    and ylow == int(ylow_text)
                    and right_prefixes[int(bits_text) - 1]
                ):
                    lane_integer = align_integer(
                        right, base_left.scale - 8, lane_mode
                    )
                    lane_payload = lane_integer & 0xFF
                    difference = (lane_payload - affine_payload) & 0xFF
                    if difference >= 128:
                        difference -= 256
                    if difference == int(delta_text):
                        adjusted_payload = lane_payload
                adjusted_left = base_left
                if active and adjusted_payload:
                    adjusted_left = add_exact(
                        base_left,
                        ExactFP(
                            base_left.sign ^ int(adjusted_payload < 0),
                            abs(adjusted_payload),
                            base_left.scale - 8,
                        ),
                    )
                combined = add_exact(adjusted_left, right)
            elif depth <= -6900:
                selected_text, lane_mode, delta_text = left_mode.split(",")
                active = bool(
                    payload or (
                        distance == 7 and ylow and left_prefixes[4]
                    )
                )
                affine_payload = ylow + 8 - distance if active else 0
                adjusted_payload = affine_payload
                if active and distance == int(selected_text):
                    lane_integer = align_integer(
                        right, base_left.scale - 8, lane_mode
                    )
                    lane_payload = lane_integer & 0xFF
                    difference = (lane_payload - affine_payload) & 0xFF
                    if difference >= 128:
                        difference -= 256
                    if difference == int(delta_text):
                        adjusted_payload = lane_payload
                adjusted_left = base_left
                if active and adjusted_payload:
                    adjusted_left = add_exact(
                        base_left,
                        ExactFP(
                            base_left.sign ^ int(adjusted_payload < 0),
                            abs(adjusted_payload),
                            base_left.scale - 8,
                        ),
                    )
                combined = add_exact(adjusted_left, right)
            elif depth <= -5900:
                selected_text, lane_mode, radius_text = left_mode.split(",")
                active = bool(
                    payload or (
                        distance == 7 and ylow and left_prefixes[4]
                    )
                )
                affine_payload = ylow + 8 - distance if active else 0
                adjusted_payload = affine_payload
                if active and distance == int(selected_text):
                    lane_integer = align_integer(
                        right, base_left.scale - 8, lane_mode
                    )
                    lane_payload = lane_integer & 0xFF
                    difference = (lane_payload - affine_payload) & 0xFF
                    if difference >= 128:
                        difference -= 256
                    if abs(difference) <= int(radius_text):
                        adjusted_payload = affine_payload + difference
                adjusted_left = base_left
                if active and adjusted_payload:
                    adjusted_left = add_exact(
                        base_left,
                        ExactFP(
                            base_left.sign ^ int(adjusted_payload < 0),
                            abs(adjusted_payload),
                            base_left.scale - 8,
                        ),
                    )
                combined = add_exact(adjusted_left, right)
            elif depth <= -4900:
                if "," in left_mode:
                    selected_text, top_text = left_mode.split(",")
                    top_bits = int(top_text) if distance == int(selected_text) else 3
                else:
                    top_bits = int(left_mode)
                active = bool(ylow and left_prefixes[top_bits - 1])
                adjusted_payload = ylow + 8 - distance if active else 0
                adjusted_left = base_left
                if adjusted_payload:
                    adjusted_left = add_exact(
                        base_left,
                        ExactFP(
                            base_left.sign ^ int(adjusted_payload < 0),
                            abs(adjusted_payload),
                            base_left.scale - 8,
                        ),
                    )
                combined = add_exact(adjusted_left, right)
            elif depth <= -3900:
                source, lane_mode, radius_text = left_mode.split(",")
                radius = int(radius_text)
                affine_payload = payload + 8 - distance
                lane_value = right if source == "chop" else add_exact(right, right_tail)
                lane_integer = align_integer(
                    lane_value, base_left.scale - 8, lane_mode
                )
                difference = (lane_integer - affine_payload) & 0xFF
                if difference >= 128:
                    difference -= 256
                delta = 0
                if payload and abs(difference) <= radius:
                    if difference < 0:
                        delta = -1
                    elif difference > 0:
                        delta = 1
                    elif right_mode == "down":
                        delta = -1
                    elif right_mode == "up":
                        delta = 1
                    elif right_mode in ("tail", "reverse-tail"):
                        tail_sum = add_exact(left_tail, right_tail)
                        delta = -1 if tail_sum.sign else 1
                        if right_mode == "reverse-tail":
                            delta = -delta
                    elif right_mode != "none":
                        raise ValueError(right_mode)
                adjusted_payload = affine_payload + delta
                adjusted_left = base_left
                if payload and adjusted_payload:
                    adjusted_left = add_exact(
                        base_left,
                        ExactFP(
                            base_left.sign ^ int(adjusted_payload < 0),
                            abs(adjusted_payload),
                            base_left.scale - 8,
                        ),
                    )
                combined = add_exact(adjusted_left, right)
            elif depth <= -2900:
                source, lane_mode, minus_text = left_mode.split(",")
                minus_offset = int(minus_text)
                plus_offset = int(right_mode)
                affine_payload = payload + 8 - distance
                adjusted_payload = affine_payload
                lane_value = right
                if source == "exact":
                    lane_value = add_exact(right, right_tail)
                lane_scale = base_left.scale - 8
                lane_integer = align_integer(lane_value, lane_scale, lane_mode)
                lane_low = lane_integer & 0xFF
                if payload and lane_low == ((affine_payload + minus_offset) & 0xFF):
                    adjusted_payload -= 1
                elif payload and lane_low == ((affine_payload + plus_offset) & 0xFF):
                    adjusted_payload += 1
                adjusted_left = base_left
                if payload and adjusted_payload:
                    adjusted_left = add_exact(
                        base_left,
                        ExactFP(
                            base_left.sign ^ int(adjusted_payload < 0),
                            abs(adjusted_payload),
                            base_left.scale - 8,
                        ),
                    )
                combined = add_exact(adjusted_left, right)
            elif depth <= -1900:
                affine_payload = payload + 8 - distance
                affine_left = base_left
                if payload and affine_payload:
                    affine_left = add_exact(
                        base_left,
                        ExactFP(
                            base_left.sign ^ int(affine_payload < 0),
                            abs(affine_payload),
                            base_left.scale - 8,
                        ),
                    )
                combined = add_exact(affine_left, right)
                if left_mode in ("left", "both"):
                    combined = add_exact(combined, left_tail)
                if left_mode in ("right", "both"):
                    combined = add_exact(combined, right_tail)
                if left_mode != "none":
                    grid_scale = left_base_scale - (depth + 2000)
                    shift = grid_scale - combined.scale
                    if shift > 0:
                        retained, remainder = divmod(
                            combined.significand, 1 << shift
                        )
                        if remainder:
                            if right_mode == "ceil":
                                retained += 1
                            elif right_mode == "rn":
                                half = 1 << (shift - 1)
                                if remainder > half or (
                                    remainder == half and (retained & 1)
                                ):
                                    retained += 1
                            elif right_mode == "odd":
                                retained |= 1
                            elif right_mode != "chop":
                                raise ValueError(right_mode)
                        combined = ExactFP(
                            combined.sign, retained, grid_scale
                        )
            elif depth <= -900:
                adjusted_payload = payload + (depth + 1000) + int(left_mode) * (
                    distance - 8
                )
                if right_mode == "zero":
                    adjusted_payload = max(0, adjusted_payload)
                elif right_mode == "seven":
                    adjusted_payload = min(7, max(0, adjusted_payload))
                elif right_mode != "raw":
                    raise ValueError(right_mode)
                adjusted_left = base_left
                if payload and adjusted_payload:
                    adjusted_left = add_exact(
                        base_left,
                        ExactFP(
                            base_left.sign ^ int(adjusted_payload < 0),
                            abs(adjusted_payload),
                            base_left.scale - 8,
                        ),
                    )
                combined = add_exact(adjusted_left, right)
            else:
                grid_scale = left_base_scale - depth
                raw = align_integer(left, grid_scale, left_mode) + align_integer(
                    right, grid_scale, right_mode
                )
                combined = ExactFP(int(raw < 0), abs(raw), grid_scale)
            correction = materialize_exact(combined, chop67).value
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
                by_distance[distance][0] += output_miss
                by_distance[distance][1] += c1_miss
                any_miss |= output_miss or c1_miss
            if any_miss and shown_route_misses < args.show_route_misses:
                print(
                    f"miss route={route_name} index={input_index} "
                    f"d={distance} y={ylow} "
                    f"p={payload} prefix5={left_prefixes[4]:x}"
                )
                shown_route_misses += 1
            input_misses += any_miss
            by_distance[distance][2] += any_miss
        scores.append(
            (output_misses, c1_misses, input_misses, route_name)
        )
        for distance, distance_score in by_distance.items():
            distance_scores.append((*distance_score, route_name, distance))

    scores.sort()
    print(f"h383 inputs={len(prepared)} routes={len(routes)}")
    for output, c1, input_misses, route_name in scores[: args.top]:
        print(
            f"  {route_name}: output={output} C1={c1} inputs={input_misses}"
        )
    if (
        not args.evaluate
        and not args.evaluate_payload_affine
        and not args.payload_affine_search
        and not args.tail_replay_search
        and not args.lane_borrow_search
        and not args.evaluate_lane_borrow
        and not args.resolution_search
        and not args.evaluate_resolution
        and not args.activation_search
        and not args.evaluate_activation
        and not args.activation_distance_search
        and not args.evaluate_activation_distance
        and not args.right_lane_replacement_search
        and not args.evaluate_right_lane_replacement
        and not args.right_lane_delta_search
        and not args.evaluate_right_lane_delta
        and not args.evaluate_right_tail_gate
        and not args.evaluate_left_tail_gate
    ):
        print("best by grid depth:")
        for depth in range(args.minimum_depth, args.maximum_depth + 1):
            best = min(
                score for score in scores if score[3].startswith(f"grid{depth}-")
            )
            print(
                f"  depth={depth}: {best[3]} output={best[0]} "
                f"C1={best[1]} inputs={best[2]}"
            )
        print("best by exponent distance:")
        for distance in sorted({item[4] for item in distance_scores}):
            best = min(item for item in distance_scores if item[4] == distance)
            print(
                f"  d={distance}: {best[3]} output={best[0]} "
                f"C1={best[1]} inputs={best[2]}"
            )


if __name__ == "__main__":
    main()
