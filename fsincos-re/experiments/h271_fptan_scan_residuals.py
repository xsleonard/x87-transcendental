#!/usr/bin/env python3
"""Analyze signed carrier corrections for the seven h269 FPTAN residuals.

The million-input RD scan adds five independent failures to the two old
controls.  This pass uses the follow-up RN/RD/RU status capture to solve the
small integer correction interval for the post-quadrant numerator and
denominator, then prints the corresponding local reconstruction low-bit
state.  Corrections are diagnostics; no per-input rule is promoted here.
"""

from __future__ import annotations

import pathlib

import h58_constraint_search as h58
import h245_fptan_shared_state as h245
import h268_fptan_residual_neighborhood as h268


ROOT = pathlib.Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "capture-kit-captures" / "skylake-fptan-h269"
INPUTS = CAPTURE / "fptan_h269_mismatch_inputs.txt"


def captures():
    return {
        rc: [
            h245.parse(line)
            for line in (CAPTURE / f"fptan_h269_mismatch_{rc}_status.txt")
            .read_text()
            .splitlines()
        ]
        for rc in h58.RCS
    }


def adjusted(value: h58.FP, delta: int) -> h58.FP:
    if value[1] + delta <= 0:
        raise ValueError((value, delta))
    return value[0], value[1] + delta, value[2]


def metric(numerator: h58.FP, denominator: h58.FP, hardware, index: int):
    modes = 0
    c1 = 0
    for rc in h58.RCS:
        predicted, increment = h245.round_div(numerator, denominator, rc)
        expected, sw = hardware[rc][index]
        if expected is None:
            raise AssertionError("h269 table input returned C2")
        modes += predicted != expected
        if predicted == expected:
            c1 += increment != bool(sw & 0x0200)
    return modes, c1


def local_selected(point, item: h268.Trace):
    quadrant = point.prepared.joint.observed.signed_n & 3
    if quadrant & 1:
        return (
            "cosine",
            item.denominator_final_exact,
            item.denominator,
            item.denominator_partial_exact,
            item.denominator_partial,
        )
    return (
        "sine",
        item.numerator_final_exact,
        item.numerator,
        item.numerator_partial_exact,
        item.numerator_partial,
    )


def main() -> None:
    points, operands = h268.points(INPUTS)
    hardware = captures()
    for index, (point, operand) in enumerate(zip(points, operands)):
        item = h268.trace(point)
        numerator, denominator = h268.rotated_values(point, item)
        baseline = metric(numerator, denominator, hardware, index)
        solutions = []
        for numerator_delta in range(-8, 9):
            for denominator_delta in range(-8, 9):
                candidate = metric(
                    adjusted(numerator, numerator_delta),
                    adjusted(denominator, denominator_delta),
                    hardware,
                    index,
                )
                if candidate == (0, 0):
                    solutions.append((numerator_delta, denominator_delta))
        minimum = min(abs(a) + abs(b) for a, b in solutions)
        minimal = [
            pair for pair in solutions if abs(pair[0]) + abs(pair[1]) == minimum
        ]
        lane, final_exact, final, partial_exact, partial = local_selected(
            point, item
        )
        final_bits = h268.discarded(final_exact, final)
        partial_bits = h268.discarded(partial_exact, partial)
        observed = point.prepared.joint.observed
        print(
            f"{index} input={operand[0]:04x}:{operand[1]:016x} "
            f"source={observed.source} n={observed.signed_n} lane={lane} "
            f"baseline={baseline} minimal={minimal}"
        )
        print(
            f"  quotient numerator={numerator[0]}:{numerator[1]:x}:2^{numerator[2]} "
            f"denominator={denominator[0]}:{denominator[1]:x}:2^{denominator[2]}"
        )
        print(
            f"  selected-final shift={final_bits[0]} "
            f"remainder={final_bits[1]:x} retained-low={final_bits[2]:02x}; "
            f"partial shift={partial_bits[0]} "
            f"remainder={partial_bits[1]:x} retained-low={partial_bits[2]:02x}"
        )
        print(f"  {h268.remainder_summary(item)}")


if __name__ == "__main__":
    main()
