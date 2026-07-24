#!/usr/bin/env python3
"""Resolve the h292 shared-sine carrier offset on a 1/256-ulp grid."""

from __future__ import annotations

import collections

import h58_constraint_search as h58
import h79_table_state_bias as h79
import h110_fsin_standalone as h110
import h283_trig_sine_bias_selector as h283
import h285_trig_sine_bias_discriminator as h285
import h286_ingest_trig_sine_bias_capture as h286
import h291_trig_sine_bias_coordinate_scan as h291
import h293_ingest_trig_coordinate_capture as h293


NUMERATORS = tuple(range(65))
DENOMINATOR_BITS = 8


def predicted(point, numerator: int, instruction: str, rc: str):
    rn64 = h283.state_inputs(point)[-1]
    sine = h79.bias_toward_zero(
        rn64, numerator, DENOMINATOR_BITS
    )
    hidden = h291.hidden_values(point, sine)
    rounded = tuple(h58.x87_round(value, rc) for value in hidden)
    increments = tuple(
        h110.compare_magnitude(output, value) > 0
        for output, value in zip(rounded, hidden)
    )
    if instruction == "fsin":
        return (rounded[0],), increments[0]
    if instruction == "fcos":
        return (rounded[1],), increments[1]
    return rounded, increments[1]


def point_error(point, hardware, index: int, numerator: int):
    result_errors = 0
    c1_errors = 0
    for instruction in ("fsin", "fcos", "fsincos"):
        for rc in h58.RCS:
            values, c1 = predicted(point, numerator, instruction, rc)
            actual, actual_c1 = h286.hardware_values(
                hardware[instruction][rc][index], instruction
            )
            misses = sum(got != want for got, want in zip(values, actual))
            result_errors += misses
            c1_errors += int(not misses and c1 != actual_c1)
    return result_errors, c1_errors


def main() -> None:
    operands = [
        tuple(int(field, 16) for field in line.split())
        for line in (h293.CAPTURE / "inputs.txt").read_text().splitlines()
    ]
    labels = h293.classes()
    hardware = h293.captures()
    points = []
    for index, (se, sig) in enumerate(operands):
        point = h285.point_from_input(index, se, sig)
        if point is None:
            raise SystemExit(f"h292 line {index + 1} is not a table point")
        points.append(point)

    errors = {}
    for numerator in NUMERATORS:
        for index, point in enumerate(points):
            errors[numerator, index] = point_error(
                point, hardware, index, numerator
            )

    for label in ("round43-direct", "next-coordinate"):
        indexes = [index for index, value in enumerate(labels) if value == label]
        ranked = []
        for numerator in NUMERATORS:
            result_errors = sum(
                errors[numerator, index][0] for index in indexes
            )
            c1_errors = sum(
                errors[numerator, index][1] for index in indexes
            )
            ranked.append((result_errors + c1_errors, result_errors, c1_errors, numerator))
        ranked.sort()
        print(f"{label}: inputs={len(indexes)} best 1/256-ulp offsets")
        for total, result_errors, c1_errors, numerator in ranked[:20]:
            print(
                f"  bias={numerator}/256 ({numerator / 8:.3f}/32): "
                f"result={result_errors} C1={c1_errors} total={total}"
            )

        winner_intervals = collections.Counter()
        for index in indexes:
            scores = {
                numerator: sum(errors[numerator, index])
                for numerator in NUMERATORS
            }
            best = min(scores.values())
            winners = [
                numerator for numerator, score in scores.items() if score == best
            ]
            winner_intervals[min(winners), max(winners)] += 1
        print("  pointwise winner intervals:")
        for interval, count in sorted(
            winner_intervals.items(), key=lambda item: (-item[1], item[0])
        )[:24]:
            print(f"    {interval[0]}/256..{interval[1]}/256: {count}")


if __name__ == "__main__":
    main()
