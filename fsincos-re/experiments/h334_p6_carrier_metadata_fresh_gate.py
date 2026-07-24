#!/usr/bin/env python3
"""Gate h333's carrier-interval multiplier rule on fresh captures.

The three input sets were generated to discriminate earlier narrow shared-sine
fraction rules and were not used to discover h333's interval semantics.  This
pass compares complete FSIN, FCOS, and FSINCOS RN/RD/RU results and C1.
"""

from __future__ import annotations

import collections

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h286_ingest_trig_sine_bias_capture as h286
import h307_trig_narrow_sine_fraction_discriminator as h307
import h308_ingest_trig_narrow_sine_fraction_capture as h308
import h315_ingest_trig_narrow_sine_fraction2_capture as h315
import h321_ingest_trig_narrow_sine_fraction3_capture as h321
import h322_trig_narrow_sine_fraction3_rule as h322
import h333_p6_carrier_metadata_semantics as h333


DATASETS = (
    ("h307", h308.CAPTURE, h308.captures),
    ("h314", h315.CAPTURE, h315.captures),
    ("h320", h321.CAPTURE, h321.captures),
)
CANDIDATE = h333.CANDIDATES["interval-low1-last-interior"]


def expected(hidden, instruction: str, rc: str):
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


def score(points, hardware, candidate: bool):
    counts = collections.Counter()
    for index, point in enumerate(points):
        hidden = (
            h333.hidden_values(point, CANDIDATE)
            if candidate
            else h322.hidden_values(point)
        )
        counts["changed-inputs"] += candidate and (
            hidden != h322.hidden_values(point)
        )
        for instruction in ("fsin", "fcos", "fsincos"):
            for rc in h58.RCS:
                predicted, predicted_c1 = expected(hidden, instruction, rc)
                actual, actual_c1 = h286.hardware_values(
                    hardware[instruction][rc][index], instruction
                )
                misses = sum(
                    got != want for got, want in zip(predicted, actual)
                )
                counts["result"] += misses
                counts["c1"] += int(
                    not misses and predicted_c1 != actual_c1
                )
    return counts


def main() -> None:
    for name, capture, load_hardware in DATASETS:
        operands = [
            tuple(int(field, 16) for field in line.split())
            for line in (capture / "inputs.txt").read_text().splitlines()
        ]
        points = []
        for index, (se, sig) in enumerate(operands):
            point = h307.point_from_input(index, se, sig)
            if point is None:
                raise SystemExit(f"{name} line {index + 1} is not narrow-table")
            points.append(point)
        hardware = load_hardware()
        baseline = score(points, hardware, False)
        candidate = score(points, hardware, True)
        print(
            f"{name}: inputs={len(points)} changed-inputs="
            f"{candidate['changed-inputs']} result "
            f"{baseline['result']} -> {candidate['result']} C1 "
            f"{baseline['c1']} -> {candidate['c1']}"
        )


if __name__ == "__main__":
    main()
