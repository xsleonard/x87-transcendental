#!/usr/bin/env python3
"""Intersect FPTAN residual corrections with FSIN/FCOS sibling intervals.

Standalone RN/RD/RU values and C1 constrain each reconstructed sine/cosine
carrier independently.  FPTAN constrains their quotient.  For each h269
residual this pass enumerates small retained-unit changes to the h260 pair and
reports only changes satisfying all three standalone modes, both standalone
C1 streams, and all three tangent result/C1 observations.  Paired FSINCOS is
also checked as an independent visible-result consistency gate.
"""

from __future__ import annotations

import pathlib

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h245_fptan_shared_state as h245
import h260_fptan_multiplier_input_format as h260
import h268_fptan_residual_neighborhood as h268
import h271_fptan_scan_residuals as h271


ROOT = pathlib.Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "capture-kit-captures" / "skylake-fptan-h269"
INPUTS = CAPTURE / "fptan_h269_mismatch_inputs.txt"


def parse_single(line: str) -> tuple[tuple[int, int], bool]:
    fields = line.split()
    if len(fields) != 5 or fields[0] != "OK" or fields[3] != "SW":
        raise ValueError(line)
    return (
        (int(fields[1], 16), int(fields[2], 16)),
        bool(int(fields[4], 16) & 0x0200),
    )


def parse_pair(line: str) -> tuple[tuple[int, int], tuple[int, int], bool]:
    fields = line.split()
    if len(fields) != 7 or fields[0] != "OK" or fields[5] != "SW":
        raise ValueError(line)
    return (
        (int(fields[1], 16), int(fields[2], 16)),
        (int(fields[3], 16), int(fields[4], 16)),
        bool(int(fields[6], 16) & 0x0200),
    )


def captures():
    result = {"fptan": h271.captures()}
    for instruction in ("fsin", "fcos", "fsincos"):
        parser = parse_pair if instruction == "fsincos" else parse_single
        result[instruction] = {
            rc: [
                parser(line)
                for line in (
                    CAPTURE / f"fptan_h269_mismatch_{instruction}_{rc}_status.txt"
                )
                .read_text()
                .splitlines()
            ]
            for rc in h58.RCS
        }
    return result


def adjusted(value: h58.FP, delta: int) -> h58.FP:
    return value[0], value[1] + delta, value[2]


def single_metric(value: h58.FP, hardware, index: int):
    modes = 0
    c1 = 0
    for rc in h58.RCS:
        predicted = h58.x87_round(value, rc)
        expected, expected_c1 = hardware[rc][index]
        mismatch = predicted != expected
        modes += mismatch
        if not mismatch:
            predicted_c1 = h110.compare_magnitude(expected, value) > 0
            c1 += predicted_c1 != expected_c1
    return modes, c1


def tangent_metric(sine: h58.FP, cosine: h58.FP, hardware, index: int):
    return h271.metric(sine, cosine, hardware, index)


def main() -> None:
    points, operands = h268.points(INPUTS)
    hardware = captures()
    for index, (point, operand) in enumerate(zip(points, operands)):
        sine, cosine = h260.values(point, h260.Candidate("rn64", "exact", "exact"))
        allowed_sine = [
            delta
            for delta in range(-16, 17)
            if single_metric(adjusted(sine, delta), hardware["fsin"], index)
            == (0, 0)
        ]
        allowed_cosine = [
            delta
            for delta in range(-16, 17)
            if single_metric(adjusted(cosine, delta), hardware["fcos"], index)
            == (0, 0)
        ]
        joint = [
            (sine_delta, cosine_delta)
            for sine_delta in allowed_sine
            for cosine_delta in allowed_cosine
            if tangent_metric(
                adjusted(sine, sine_delta),
                adjusted(cosine, cosine_delta),
                hardware["fptan"],
                index,
            )
            == (0, 0)
        ]
        paired_equal = all(
            hardware["fsincos"][rc][index][:2]
            == (
                hardware["fsin"][rc][index][0],
                hardware["fcos"][rc][index][0],
            )
            for rc in h58.RCS
        )
        minimum = min(abs(a) + abs(b) for a, b in joint)
        minimal = [
            pair for pair in joint if abs(pair[0]) + abs(pair[1]) == minimum
        ]
        print(
            f"{index} input={operand[0]:04x}:{operand[1]:016x} "
            f"paired-equal={paired_equal}"
        )
        print(f"  sine allowed={allowed_sine}")
        print(f"  cosine allowed={allowed_cosine}")
        print(f"  joint count={len(joint)} minimal={minimal}")


if __name__ == "__main__":
    main()
