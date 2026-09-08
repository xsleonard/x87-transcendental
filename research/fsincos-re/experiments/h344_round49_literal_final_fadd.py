#!/usr/bin/env python3
"""Re-test the literal final FADD bus after Round 49.

The earlier h278 pass was dominated by an incorrect shared-sine product.
This pass freezes Round 49's carrier-interval product and replaces only the
following abstract away67 combine with the complete P5-style alignment,
carry, borrow, sticky, normalization, and materialization grammar.
"""

from __future__ import annotations

import h58_constraint_search as h58
import h60_round16_parity as h60
import h200_p5_fadd_bitvector as h200
import h206_p5_fadd_complete as h206
import h207_tang_literal_fadd as h207
import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230
import h278_trig_final_literal_fadd as h278
import h333_p6_carrier_metadata_semantics as h333


ROUND49 = h333.CANDIDATES["interval-low1-last-interior"]


def local_value(point, cosine_lane: bool, candidate):
    prepared = point.prepared.joint.observed.point
    _, cosine_tail = h230.state(point, h228.CANDIDATE)
    if cosine_lane:
        lead, cross = prepared.cos_t, prepared.sin_t
    else:
        lead, cross = prepared.sin_t, prepared.cos_t
    q_product = h226.quantize(
        h58.mul_exact(lead, cosine_tail), "odd67"
    )
    p_product = h333.p_product(
        cross, h333.universal_carrier(point), ROUND49
    )
    if cosine_lane:
        p_product = h58.neg(p_product)
    correction, _ = h206.fadd(
        h200.normalized_bus(q_product),
        h200.normalized_bus(p_product),
        candidate.mode,
        normalize=candidate.normalize,
    )
    return h58.add_exact(
        lead, h278.materialize(correction, candidate.action)
    )


def hidden_values(point, candidate):
    sine = local_value(point, False, candidate)
    cosine = local_value(point, True, candidate)
    if point.prepared.joint.observed.point.raw.sign:
        sine = h58.neg(sine)
    return h60.rotate(
        (sine, cosine), point.prepared.joint.observed.signed_n
    )


def score(points, candidate):
    totals = [h226.ZERO_JOINT, h226.ZERO_JOINT]
    for point in points:
        values = (
            h333.hidden_values(point, ROUND49)
            if candidate is None
            else hidden_values(point, candidate)
        )
        metric = h226.metric_for(point, values)
        split = int(not h207.h131.is_train(point.prepared.joint.observed))
        totals[split] = h226.add_metric(totals[split], metric)
    return tuple(totals)


def sample(points, controls: int = 512):
    residuals = []
    correct = []
    for point in points:
        metric = h226.metric_for(
            point, h333.hidden_values(point, ROUND49)
        )
        (residuals if metric != h226.ZERO_JOINT else correct).append(point)
    correct.sort(key=lambda point: (
        point.prepared.joint.observed.point.raw.sig
        ^ (point.prepared.joint.observed.index << 11)
        ^ point.prepared.joint.observed.signed_n
    ))
    return residuals + correct[:controls]


def main() -> None:
    complete = h228.points("sweep")
    selected = sample(complete)
    baseline = score(selected, None)
    ranked = []
    invalid = 0
    for candidate in h278.CANDIDATES:
        try:
            values = score(selected, candidate)
        except ValueError:
            invalid += 1
            continue
        ranked.append((
            h226.regressions(values, baseline),
            h226.objective(values),
            candidate.short(),
            candidate,
            values,
        ))
    ranked.sort()
    print(
        "h344 Round-49 literal final FADD: "
        f"candidates={len(h278.CANDIDATES)} selected={len(selected)} "
        f"complete={len(complete)} baseline={h226.objective(baseline)} "
        f"invalid={invalid}"
    )
    for item in ranked[:20]:
        print(
            f"  sample regressions={item[0]} objective={item[1]} {item[2]}"
        )
    complete_baseline = score(complete, None)
    finalists = []
    for _, _, _, candidate, selected_values in ranked[:20]:
        values = score(complete, candidate)
        finalists.append((
            h226.regressions(values, complete_baseline),
            h226.objective(values),
            candidate.short(),
            h226.no_worse(selected_values, baseline),
            values,
        ))
    finalists.sort()
    print(f"complete checked={len(finalists)}")
    for item in finalists:
        print(
            f"  regressions={item[0]} objective={item[1]} "
            f"{item[2]} sample-no-worse={item[3]} values={item[4]}"
        )


if __name__ == "__main__":
    main()
