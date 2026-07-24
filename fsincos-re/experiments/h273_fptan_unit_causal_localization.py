#!/usr/bin/env python3
"""Localize each h269 FPTAN residual with propagated unit perturbations.

Unlike scalar materialization searches, a retained-unit perturbation at an
upstream node is propagated through every downstream operation.  The search
tests the shared sine input read, all four products, both partial and final
subtractions, and the two final divide inputs.  A node is interesting only if
small signed changes can explain every residual; the direction is left for a
later carry/sticky discriminator.
"""

from __future__ import annotations

import pathlib

import h58_constraint_search as h58
import h230_p6_microop_materialization_search as h230
import h260_fptan_multiplier_input_format as h260
import h268_fptan_residual_neighborhood as h268
import h271_fptan_scan_residuals as h271


ROOT = pathlib.Path(__file__).resolve().parents[1]
INPUTS = (
    ROOT
    / "capture-kit-captures"
    / "skylake-fptan-h269"
    / "fptan_h269_mismatch_inputs.txt"
)
NODES = (
    "sine_read",
    "denominator_sine_product",
    "denominator_tail_product",
    "denominator_partial",
    "denominator_final",
    "numerator_sine_product",
    "numerator_tail_product",
    "numerator_partial",
    "numerator_final",
    "quotient_numerator",
    "quotient_denominator",
)


def adjust(value: h58.FP, node: str, target: str, delta: int) -> h58.FP:
    if node != target or not delta:
        return value
    if value[1] + delta <= 0:
        raise ValueError((value, delta))
    return value[0], value[1] + delta, value[2]


def values(point, target: str, delta: int):
    observed = point.prepared.joint.observed
    prepared = observed.point
    sine, cosine_tail = h230.state(point, h260.LEGACY_STATE)
    sine = adjust(
        h260.quantize(sine, "rn64"), "sine_read", target, delta
    )
    negative_sine = h58.neg(sine)
    negative_table_sine = h58.neg(prepared.sin_t)

    denominator_sine_product = adjust(
        h260.h246.mul(
            negative_table_sine,
            negative_sine,
            h260.SHARED_RESULT,
        ),
        "denominator_sine_product",
        target,
        delta,
    )
    denominator_tail_product = adjust(
        h260.h246.mul(
            prepared.cos_t,
            cosine_tail,
            h260.SHARED_RESULT,
        ),
        "denominator_tail_product",
        target,
        delta,
    )
    denominator_partial = adjust(
        h260.h246.sub(
            denominator_sine_product,
            denominator_tail_product,
            h260.SHARED_RESULT,
        ),
        "denominator_partial",
        target,
        delta,
    )
    denominator = adjust(
        h260.h246.sub(
            prepared.cos_t,
            denominator_partial,
            h260.SHARED_RESULT,
        ),
        "denominator_final",
        target,
        delta,
    )

    numerator_sine_product = adjust(
        h260.h246.mul(
            prepared.cos_t,
            negative_sine,
            h260.SHARED_RESULT,
        ),
        "numerator_sine_product",
        target,
        delta,
    )
    numerator_tail_product = adjust(
        h260.h246.mul(
            prepared.sin_t,
            cosine_tail,
            h260.SHARED_RESULT,
        ),
        "numerator_tail_product",
        target,
        delta,
    )
    numerator_partial = adjust(
        h260.h246.sub(
            numerator_sine_product,
            numerator_tail_product,
            h260.SHARED_RESULT,
        ),
        "numerator_partial",
        target,
        delta,
    )
    numerator = adjust(
        h260.h246.sub(
            prepared.sin_t,
            numerator_partial,
            h260.SHARED_RESULT,
        ),
        "numerator_final",
        target,
        delta,
    )
    if prepared.raw.sign:
        numerator = h58.neg(numerator)
    numerator, denominator = h230.h60.rotate(
        (numerator, denominator), observed.signed_n
    )
    numerator = adjust(
        numerator, "quotient_numerator", target, delta
    )
    denominator = adjust(
        denominator, "quotient_denominator", target, delta
    )
    return numerator, denominator


def main() -> None:
    points, operands = h268.points(INPUTS)
    hardware = h271.captures()
    by_node = {node: [] for node in NODES}
    for index, (point, operand) in enumerate(zip(points, operands)):
        solutions = []
        for node in NODES:
            deltas = []
            for delta in range(-4, 5):
                numerator, denominator = values(point, node, delta)
                if h271.metric(numerator, denominator, hardware, index) == (0, 0):
                    deltas.append(delta)
            if deltas:
                solutions.append((node, deltas))
                by_node[node].append((index, deltas))
        print(f"{index} input={operand[0]:04x}:{operand[1]:016x}")
        for node, deltas in solutions:
            print(f"  {node}: {deltas}")
    print("nodes reaching all residuals:")
    for node, rows in by_node.items():
        if len(rows) == len(points):
            print(f"  {node}: {rows}")


if __name__ == "__main__":
    main()
