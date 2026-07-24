#!/usr/bin/env python3
"""Localize the 80 post-Round-48 paired-FSINCOS residuals.

The Round-48 shared-sine proxy exactly reproduces the structured sweep except
for 39 sine and 41 cosine lanes.  h327 maps every current proxy to one common
67-bit numeric carrier, leaving only a dependent-multiply low-unit effect to
interpret.  This pass asks whether the remaining hardware intervals are
reachable by small signed changes at each named final-graph node.

The perturbations are causal diagnostics, not candidate model rules.  A node
is credited only when propagating its changed value through the frozen graph
produces the complete captured RN/RD/RU and C1 interval for a residual lane.
"""

from __future__ import annotations

import collections

import h58_constraint_search as h58
import h60_round16_parity as h60
import h79_table_state_bias as h79
import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230
import h283_trig_sine_bias_selector as h283
import h322_trig_narrow_sine_fraction3_rule as h322
import h326_p6_tmp_sine_projection as h326


ZERO = (0, 0, 0)
UNIT_DELTAS = tuple(delta for delta in range(-8, 9) if delta)
BIAS_DELTAS = tuple(delta for delta in range(-16, 17) if delta)
NODES = (
    "sine_bias",
    "cosine_tail",
    "q_product",
    "p_product",
    "correction",
)


def adjust(value: h58.FP, delta: int) -> h58.FP:
    sign, significand, exponent = value
    if significand + delta <= 0:
        raise ValueError((value, delta))
    return sign, significand + delta, exponent


def state(point, target: str, delta: int):
    rn64 = h283.state_inputs(point)[-1]
    numerator = h326.numerator(point)
    if target == "sine_bias":
        numerator += delta
    if numerator < 0:
        raise ValueError(numerator)
    sine = h79.bias_toward_zero(rn64, numerator, 8)
    _, cosine_tail = h230.state(point, h228.CANDIDATE)
    if target == "cosine_tail":
        cosine_tail = adjust(cosine_tail, delta)
    return sine, cosine_tail


def local_value(point, cosine_lane: bool, target: str, delta: int):
    prepared = point.prepared.joint.observed.point
    sine, cosine_tail = state(point, target, delta)
    if cosine_lane:
        lead, cross = prepared.cos_t, prepared.sin_t
    else:
        lead, cross = prepared.sin_t, prepared.cos_t
    q_product = h226.quantize(
        h58.mul_exact(lead, cosine_tail), "odd67"
    )
    if target == "q_product":
        q_product = adjust(q_product, delta)
    p_product = h226.quantize(
        h58.mul_exact(cross, sine), "chop67"
    )
    if cosine_lane:
        p_product = h58.neg(p_product)
    if target == "p_product":
        p_product = adjust(p_product, delta)
    correction = h226.quantize(
        h58.add_exact(q_product, p_product), "away67"
    )
    if target == "correction":
        correction = adjust(correction, delta)
    return h58.add_exact(lead, correction)


def hidden_values(point, target: str, delta: int):
    sine = local_value(point, False, target, delta)
    cosine = local_value(point, True, target, delta)
    if point.prepared.joint.observed.point.raw.sign:
        sine = h58.neg(sine)
    return h60.rotate(
        (sine, cosine), point.prepared.joint.observed.signed_n
    )


def main() -> None:
    points = h228.points("sweep")
    residuals = 0
    reachable_any = 0
    counts = collections.Counter()
    nearest = collections.Counter()
    unreachable = collections.Counter()
    for point in points:
        baseline = h226.metric_for(point, h322.hidden_values(point))
        if baseline == h226.ZERO_JOINT:
            continue
        observed = point.prepared.joint.observed
        for lane in (0, 1):
            if baseline[lane] == ZERO:
                continue
            residuals += 1
            reached = set()
            for node in NODES:
                deltas = BIAS_DELTAS if node == "sine_bias" else UNIT_DELTAS
                exact = [
                    delta
                    for delta in deltas
                    if h226.metric_for(
                        point, hidden_values(point, node, delta)
                    )[lane]
                    == ZERO
                ]
                if not exact:
                    continue
                reached.add(node)
                counts[node] += 1
                choice = min(exact, key=lambda value: (abs(value), value))
                nearest[node, choice] += 1
            if reached:
                reachable_any += 1
            else:
                unreachable[
                    "cosine" if lane else "sine",
                    observed.source,
                    observed.family,
                    observed.point.cell,
                ] += 1
    print(
        "h328 Round-48 causal localization: "
        f"reachable={reachable_any}/{residuals}"
    )
    for node in NODES:
        distribution = {
            delta: count
            for (name, delta), count in sorted(nearest.items())
            if name == node
        }
        print(
            f"  {node:12s}: {counts[node]:2d}/{residuals} "
            f"nearest={distribution}"
        )
    if unreachable:
        print("unreachable strata:")
        for key, count in sorted(unreachable.items()):
            print(f"  {key}: {count}")


if __name__ == "__main__":
    main()
