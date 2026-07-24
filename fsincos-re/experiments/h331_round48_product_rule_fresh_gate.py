#!/usr/bin/env python3
"""Gate the narrow p-product predicate on three fresh hardware captures."""

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
import h330_round48_product_rule_gate as h330


DATASETS = (
    ("h307", h308.CAPTURE, h308.captures),
    ("h314", h315.CAPTURE, h315.captures),
    ("h320", h321.CAPTURE, h321.captures),
)
RULE = "combine8-normalization-low"


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
        if candidate:
            lane_selection = tuple(
                h330.selected(point, lane, RULE) for lane in (0, 1)
            )
            hidden = h330.hidden_values(
                point, h330.RULES[RULE], lane_selection
            )
            counts["active-lanes"] += sum(lane_selection)
        else:
            hidden = h322.hidden_values(point)
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
            f"{name}: inputs={len(points)} active-lanes="
            f"{candidate['active-lanes']} result "
            f"{baseline['result']} -> {candidate['result']} C1 "
            f"{baseline['c1']} -> {candidate['c1']}"
        )


if __name__ == "__main__":
    main()
