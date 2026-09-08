#!/usr/bin/env python3
"""Trace h269's signed unit labels through the shared sine-state producer.

h273 shows that all seven FPTAN residuals are fixed by a one-unit change at
the RN64 read of the shared sine state.  This pass propagates small retained-
unit perturbations from each P-chain producer through the remaining graph.
It also prints the exact discarded bits at every materialization so a later
separator can be based on carry/guard/sticky state rather than input identity.
"""

from __future__ import annotations

import dataclasses
import pathlib

import h58_constraint_search as h58
import h79_table_state_bias as h79
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
    "p_product_1",
    "p_sum_1",
    "p_product_2",
    "p_sum_2",
    "p_product_3",
    "p_sum_3",
    "p_square",
    "p_times_a",
    "sine_add",
)
CANDIDATE = h260.LEGACY_STATE


@dataclasses.dataclass(frozen=True)
class Step:
    name: str
    exact: h58.FP
    value: h58.FP


def adjust(value: h58.FP, name: str, target: str, delta: int) -> h58.FP:
    if name != target or not delta:
        return value
    return value[0], value[1] + delta, value[2]


def state(point, target: str = "", delta: int = 0):
    observed = point.prepared.joint.observed
    base = point.prepared.base
    a = observed.point.a
    square = h230.quantize(
        h58.mul_exact(a, a), CANDIDATE.square
    )
    value = h230.h227.coefficient(
        h58.S4[0], base.p_coefficients[0], True
    )
    steps = []
    for index, row in enumerate(h58.S4[1:], 1):
        exact = h58.mul_exact(value, square)
        name = f"p_product_{index}"
        value = adjust(
            h230.quantize(exact, CANDIDATE.p_horner_product),
            name,
            target,
            delta,
        )
        steps.append(Step(name, exact, value))
        exact = h58.add_exact(
            value,
            h230.h227.coefficient(
                row, base.p_coefficients[index], True
            ),
        )
        name = f"p_sum_{index}"
        value = adjust(
            h230.quantize(exact, CANDIDATE.p_horner_sum),
            name,
            target,
            delta,
        )
        steps.append(Step(name, exact, value))

    exact = h58.mul_exact(value, square)
    p_square = adjust(
        h230.quantize(exact, CANDIDATE.p_square),
        "p_square",
        target,
        delta,
    )
    steps.append(Step("p_square", exact, p_square))
    exact = h58.mul_exact(p_square, a)
    p_times_a = adjust(
        h230.quantize(exact, CANDIDATE.p_times_a),
        "p_times_a",
        target,
        delta,
    )
    steps.append(Step("p_times_a", exact, p_times_a))
    exact = h58.add_exact(a, p_times_a)
    sine_add = adjust(
        h230.quantize(exact, CANDIDATE.sine_add),
        "sine_add",
        target,
        delta,
    )
    steps.append(Step("sine_add", exact, sine_add))
    sine = h79.bias_toward_zero(sine_add, 5)
    return sine, tuple(steps)


def fptan_values(point, sine_state: h58.FP):
    prepared = point.prepared.joint.observed.point
    _, cosine_tail = h230.state(point, CANDIDATE)
    sine = h260.quantize(sine_state, "rn64")
    negative_sine = h58.neg(sine)
    negative_table_sine = h58.neg(prepared.sin_t)

    denominator_partial = h260.h246.sub(
        h260.h246.mul(
            negative_table_sine,
            negative_sine,
            h260.SHARED_RESULT,
        ),
        h260.h246.mul(
            prepared.cos_t,
            cosine_tail,
            h260.SHARED_RESULT,
        ),
        h260.SHARED_RESULT,
    )
    denominator = h260.h246.sub(
        prepared.cos_t, denominator_partial, h260.SHARED_RESULT
    )
    numerator_partial = h260.h246.sub(
        h260.h246.mul(
            prepared.cos_t,
            negative_sine,
            h260.SHARED_RESULT,
        ),
        h260.h246.mul(
            prepared.sin_t,
            cosine_tail,
            h260.SHARED_RESULT,
        ),
        h260.SHARED_RESULT,
    )
    numerator = h260.h246.sub(
        prepared.sin_t, numerator_partial, h260.SHARED_RESULT
    )
    if prepared.raw.sign:
        numerator = h58.neg(numerator)
    return h230.h60.rotate(
        (numerator, denominator),
        point.prepared.joint.observed.signed_n,
    )


def discarded(step: Step):
    shift = step.exact[1].bit_length() - step.value[1].bit_length()
    # Quantized widths differ, so derive the actual binary scale movement.
    shift = max(0, step.value[2] - step.exact[2])
    remainder = step.exact[1] & ((1 << shift) - 1) if shift else 0
    return shift, remainder, step.value[1] & 0xFF


def main() -> None:
    points, operands = h268.points(INPUTS)
    hardware = h271.captures()
    by_node = {node: [] for node in NODES}
    for index, (point, operand) in enumerate(zip(points, operands)):
        _, baseline_steps = state(point)
        solutions = []
        for node in NODES:
            deltas = []
            for delta in (-2, -1, 1, 2):
                sine, _ = state(point, node, delta)
                numerator, denominator = fptan_values(point, sine)
                if h271.metric(
                    numerator, denominator, hardware, index
                ) == (0, 0):
                    deltas.append(delta)
            if deltas:
                solutions.append((node, deltas))
                by_node[node].append((index, deltas))
        print(f"{index} input={operand[0]:04x}:{operand[1]:016x}")
        for step in baseline_steps:
            shift, remainder, low = discarded(step)
            print(
                f"  {step.name}: shift={shift} remainder={remainder:x} "
                f"retained-low={low:02x} sign={step.value[0]}"
            )
        print(f"  causal={solutions}")
    print("nodes reaching all residuals:")
    for node, rows in by_node.items():
        if len(rows) == len(points):
            print(f"  {node}: {rows}")


if __name__ == "__main__":
    main()
