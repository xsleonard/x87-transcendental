#!/usr/bin/env python3
"""Propagate retained-unit perturbations through the final P6 trig graph.

h279 shows that a literal final-FADD grammar cannot reach 209 of 730 frozen
residual lanes.  This pass perturbs each named state/product/combine node and
propagates the result forward.  A node is credited only when a small signed
carrier change produces the hardware interval for the residual lane.
"""

from __future__ import annotations

import collections

import h58_constraint_search as h58
import h60_round16_parity as h60
import h218_fadd_residual_programs as h218
import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230


ZERO = (0, 0, 0)
NODES = (
    "sine_state",
    "cosine_tail",
    "q_product",
    "p_product",
    "correction",
)
DELTAS = tuple(delta for delta in range(-8, 9) if delta)


def adjust(value: h58.FP, node: str, target: str, delta: int) -> h58.FP:
    if node != target or not delta:
        return value
    sign, sig, exponent = value
    if sig + delta <= 0:
        raise ValueError((value, delta))
    return sign, sig + delta, exponent


def local_value(point, cosine_lane: bool, target: str, delta: int):
    prepared = point.prepared.joint.observed.point
    sine, cosine_tail = h230.state(point, h228.CANDIDATE)
    sine = adjust(sine, "sine_state", target, delta)
    cosine_tail = adjust(cosine_tail, "cosine_tail", target, delta)
    if cosine_lane:
        lead, cross = prepared.cos_t, prepared.sin_t
    else:
        lead, cross = prepared.sin_t, prepared.cos_t
    q_product = h226.quantize(
        h58.mul_exact(lead, cosine_tail), "odd67"
    )
    q_product = adjust(q_product, "q_product", target, delta)
    p_product = h226.quantize(
        h58.mul_exact(cross, sine), "chop67"
    )
    if cosine_lane:
        p_product = h58.neg(p_product)
    p_product = adjust(p_product, "p_product", target, delta)
    correction = h226.quantize(
        h58.add_exact(q_product, p_product), "away67"
    )
    correction = adjust(correction, "correction", target, delta)
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
    counts = collections.Counter()
    directions = collections.Counter()
    unreachable = collections.Counter()
    residuals = 0
    for name, points in h218.datasets():
        dataset_residuals = 0
        dataset_reachable = 0
        for point in points:
            baseline = h226.metric_for(
                point, h230.hidden_values(point, h228.CANDIDATE)
            )
            if baseline == h226.ZERO_JOINT:
                continue
            node_metrics = {
                (node, delta): h226.metric_for(
                    point, hidden_values(point, node, delta)
                )
                for node in NODES
                for delta in DELTAS
            }
            for cosine in (False, True):
                if cosine and not point.cosine_hardware:
                    continue
                if baseline[cosine] == ZERO:
                    continue
                residuals += 1
                dataset_residuals += 1
                reachable_nodes = set()
                for node in NODES:
                    exact_deltas = [
                        delta
                        for delta in DELTAS
                        if node_metrics[node, delta][cosine] == ZERO
                    ]
                    if exact_deltas:
                        reachable_nodes.add(node)
                        counts[node] += 1
                        nearest = min(exact_deltas, key=lambda value: (abs(value), value))
                        directions[node, nearest] += 1
                if reachable_nodes:
                    dataset_reachable += 1
                else:
                    observed = point.prepared.joint.observed
                    unreachable[
                        "cosine" if cosine else "sine",
                        observed.source,
                        observed.family,
                        observed.point.cell,
                    ] += 1
        print(
            f"{name}: reachable={dataset_reachable}/{dataset_residuals}"
        )
    print(f"joint reachable={residuals - sum(unreachable.values())}/{residuals}")
    for node in NODES:
        print(
            f"  {node:12s}: {counts[node]:4d} "
            f"nearest-deltas={dict(sorted((delta, count) for (name, delta), count in directions.items() if name == node))}"
        )
    if unreachable:
        print("unreachable strata:")
        for key, count in sorted(unreachable.items()):
            print(f"  {key}: {count}")


if __name__ == "__main__":
    main()
