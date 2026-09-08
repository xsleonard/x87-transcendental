#!/usr/bin/env python3
"""Localize the 13 post-Round-49 paired table residuals."""

from __future__ import annotations

import collections

import h58_constraint_search as h58
import h60_round16_parity as h60
import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230
import h333_p6_carrier_metadata_semantics as h333


ZERO = (0, 0, 0)
DELTAS = tuple(delta for delta in range(-8, 9) if delta)
NODES = ("cosine_tail", "q_product", "p_product", "correction")
CANDIDATE = h333.CANDIDATES["interval-low1-last-interior"]


def adjust(value: h58.FP, delta: int) -> h58.FP:
    sign, significand, exponent = value
    if significand + delta <= 0:
        raise ValueError((value, delta))
    return sign, significand + delta, exponent


def local_value(point, cosine_lane: bool, target: str, delta: int):
    prepared = point.prepared.joint.observed.point
    _, cosine_tail = h230.state(point, h228.CANDIDATE)
    if target == "cosine_tail":
        cosine_tail = adjust(cosine_tail, delta)
    if cosine_lane:
        lead, cross = prepared.cos_t, prepared.sin_t
    else:
        lead, cross = prepared.sin_t, prepared.cos_t
    q_product = h226.quantize(
        h58.mul_exact(lead, cosine_tail), "odd67"
    )
    if target == "q_product":
        q_product = adjust(q_product, delta)
    product = h333.p_product(
        cross, h333.universal_carrier(point), CANDIDATE
    )
    if cosine_lane:
        product = h58.neg(product)
    if target == "p_product":
        product = adjust(product, delta)
    correction = h226.quantize(
        h58.add_exact(q_product, product), "away67"
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
    residuals = 0
    reachable_any = 0
    counts = collections.Counter()
    nearest = collections.Counter()
    unreachable = collections.Counter()
    for point in h228.points("sweep"):
        baseline = h226.metric_for(
            point, h333.hidden_values(point, CANDIDATE)
        )
        if baseline == h226.ZERO_JOINT:
            continue
        observed = point.prepared.joint.observed
        for lane in (0, 1):
            if baseline[lane] == ZERO:
                continue
            residuals += 1
            reached = set()
            for node in NODES:
                exact = [
                    delta
                    for delta in DELTAS
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
        "h337 Round-49 causal localization: "
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
