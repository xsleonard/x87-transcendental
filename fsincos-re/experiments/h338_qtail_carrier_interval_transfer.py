#!/usr/bin/env python3
"""Transfer h333's RN64-carrier interval semantics to the Q-tail FMUL.

The cosine-tail state is materialized at RN64 and immediately consumed by
the other table-reconstruction multiply.  This pass applies each complete
h333 carrier interpretation to that edge while freezing the successful
Round-49 shared-sine product.  No per-input selector is introduced.
"""

from __future__ import annotations

import argparse

import h58_constraint_search as h58
import h60_round16_parity as h60
import h207_tang_literal_fadd as h207
import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230
import h333_p6_carrier_metadata_semantics as h333


P_CANDIDATE = h333.CANDIDATES["interval-low1-last-interior"]


def carrier_from_rn64(value: h58.FP):
    sign, significand, scale = value
    carrier = sign, (significand << 3) - 1, scale - 3
    if carrier[1] & 7 != 7:
        raise AssertionError(carrier)
    return carrier


def local_value(point, cosine_lane: bool, q_candidate):
    prepared = point.prepared.joint.observed.point
    _, cosine_tail = h230.state(point, h228.CANDIDATE)
    if cosine_lane:
        lead, cross = prepared.cos_t, prepared.sin_t
    else:
        lead, cross = prepared.sin_t, prepared.cos_t
    q_product = (
        h226.quantize(h58.mul_exact(lead, cosine_tail), "odd67")
        if q_candidate is None
        else h333.p_product(
            lead, carrier_from_rn64(cosine_tail), q_candidate
        )
    )
    p_product = h333.p_product(
        cross, h333.universal_carrier(point), P_CANDIDATE
    )
    if cosine_lane:
        p_product = h58.neg(p_product)
    correction = h226.quantize(
        h58.add_exact(q_product, p_product), "away67"
    )
    return h58.add_exact(lead, correction)


def hidden_values(point, q_candidate):
    sine = local_value(point, False, q_candidate)
    cosine = local_value(point, True, q_candidate)
    if point.prepared.joint.observed.point.raw.sign:
        sine = h58.neg(sine)
    return h60.rotate(
        (sine, cosine), point.prepared.joint.observed.signed_n
    )


def score(points, candidate):
    totals = [h226.ZERO_JOINT, h226.ZERO_JOINT]
    changed = 0
    for index, point in enumerate(points):
        baseline_values = h333.hidden_values(point, P_CANDIDATE)
        values = hidden_values(point, candidate)
        metric = h226.metric_for(point, values)
        split = int(not h207.h131.is_train(point.prepared.joint.observed))
        totals[split] = h226.add_metric(totals[split], metric)
        changed += values != baseline_values
        if index % 512 == 0:
            h230.state.cache_clear()
    return tuple(totals), changed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=("sweep", "dense"), default="sweep")
    parser.add_argument("--candidate", choices=tuple(h333.CANDIDATES))
    args = parser.parse_args()
    points = h228.points(args.scope)
    baseline, _ = score(points, None)
    selected = (
        (h333.CANDIDATES[args.candidate],)
        if args.candidate
        else tuple(h333.CANDIDATES.values())
    )
    ranked = []
    for candidate in selected:
        values, changed = score(points, candidate)
        ranked.append((
            h226.objective(values),
            h226.regressions(values, baseline),
            candidate.name,
            changed,
            values,
        ))
    ranked.sort()
    print(
        "h338 Q-tail carrier transfer: "
        f"scope={args.scope} points={len(points)} "
        f"baseline={h226.objective(baseline)} candidates={len(ranked)}"
    )
    for objective, regressions, name, changed, values in ranked[:80]:
        print(
            f"  {name}: objective={objective} regressions={regressions} "
            f"changed-values={changed}/{len(points)} values={values}"
        )


if __name__ == "__main__":
    main()
