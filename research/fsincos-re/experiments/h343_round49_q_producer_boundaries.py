#!/usr/bin/env python3
"""Re-test uniform Q-producer boundaries under the Round-49 final graph.

All reachable Round-49 paired residuals can be removed by decreasing the
cosine-tail state.  Earlier Q-boundary searches were scored while the much
larger shared-sine product error was still present.  This pass changes only
one modeled Q operation class at a time: the three Horner products, the three
Horner sums, or the terminal Q-times-square materialization.
"""

from __future__ import annotations

import dataclasses

import h58_constraint_search as h58
import h60_round16_parity as h60
import h207_tang_literal_fadd as h207
import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230
import h333_p6_carrier_metadata_semantics as h333


ROUND49 = h333.CANDIDATES["interval-low1-last-interior"]
FIELDS = ("q_horner_product", "q_horner_sum", "q_tail")


def local_value(point, cosine_lane: bool, candidate):
    prepared = point.prepared.joint.observed.point
    _, cosine_tail = h230.state(point, candidate)
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
    correction = h226.quantize(
        h58.add_exact(q_product, p_product), "away67"
    )
    return h58.add_exact(lead, correction)


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
    changed = 0
    for point in points:
        baseline_values = h333.hidden_values(point, ROUND49)
        values = (
            baseline_values
            if candidate == h228.CANDIDATE
            else hidden_values(point, candidate)
        )
        metric = h226.metric_for(point, values)
        split = int(not h207.h131.is_train(point.prepared.joint.observed))
        totals[split] = h226.add_metric(totals[split], metric)
        changed += values != baseline_values
    return tuple(totals), changed


def main() -> None:
    points = h228.points("sweep")
    baseline, _ = score(points, h228.CANDIDATE)
    ranked = []
    for field in FIELDS:
        current = getattr(h228.CANDIDATE, field)
        for action in h230.ACTIONS:
            if action == current:
                continue
            candidate = dataclasses.replace(
                h228.CANDIDATE, **{field: action}
            )
            values, changed = score(points, candidate)
            ranked.append((
                h226.objective(values),
                h226.regressions(values, baseline),
                field,
                action,
                changed,
                values,
            ))
            h230.state.cache_clear()
    ranked.sort()
    print(
        "h343 Round-49 Q-producer boundaries: "
        f"points={len(points)} baseline={h226.objective(baseline)} "
        f"candidates={len(ranked)}"
    )
    for objective, regressions, field, action, changed, values in ranked[:80]:
        print(
            f"  {field}={action}: objective={objective} "
            f"regressions={regressions} changed-values="
            f"{changed}/{len(points)} values={values}"
        )


if __name__ == "__main__":
    main()
