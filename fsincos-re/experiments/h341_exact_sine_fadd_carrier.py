#!/usr/bin/env python3
"""Materialize the sine-to-FMUL carrier directly from the exact FADD.

Round 49 interprets the three P6 low carrier positions from RN64's open
interval.  This pass tests the literal alternative: round the exact
``a + P*a^3`` result once at 64--72 significant bits and multiply that state
with the established chop67 product operation.  The same state rule is used
for both lanes and every point.
"""

from __future__ import annotations

import dataclasses

import h58_constraint_search as h58
import h60_round16_parity as h60
import h110_fsin_standalone as h110
import h207_tang_literal_fadd as h207
import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230
import h283_trig_sine_bias_selector as h283
import h333_p6_carrier_metadata_semantics as h333


@dataclasses.dataclass(frozen=True)
class Candidate:
    bits: int
    mode: str

    @property
    def name(self):
        return "exact" if not self.bits else f"{self.mode}{self.bits}"


CANDIDATES = (
    Candidate(0, "exact"),
    *(
        Candidate(bits, mode)
        for bits in range(64, 73)
        for mode in ("rn", "chop", "away", "odd")
    ),
)
ROUND49 = h333.CANDIDATES["interval-low1-last-interior"]


def sine_state(point, candidate: Candidate):
    exact_sum = h283.state_inputs(point)[-2]
    if not candidate.bits:
        return exact_sum
    return h110.quantize(
        exact_sum, h110.Quant(candidate.bits, candidate.mode)
    )


def local_value(point, cosine_lane: bool, candidate: Candidate):
    prepared = point.prepared.joint.observed.point
    _, cosine_tail = h230.state(point, h228.CANDIDATE)
    if cosine_lane:
        lead, cross = prepared.cos_t, prepared.sin_t
    else:
        lead, cross = prepared.sin_t, prepared.cos_t
    q_product = h226.quantize(
        h58.mul_exact(lead, cosine_tail), "odd67"
    )
    p_product = h226.quantize(
        h58.mul_exact(cross, sine_state(point, candidate)), "chop67"
    )
    if cosine_lane:
        p_product = h58.neg(p_product)
    correction = h226.quantize(
        h58.add_exact(q_product, p_product), "away67"
    )
    return h58.add_exact(lead, correction)


def hidden_values(point, candidate: Candidate):
    sine = local_value(point, False, candidate)
    cosine = local_value(point, True, candidate)
    if point.prepared.joint.observed.point.raw.sign:
        sine = h58.neg(sine)
    return h60.rotate(
        (sine, cosine), point.prepared.joint.observed.signed_n
    )


def score(points, candidate: Candidate | None):
    totals = [h226.ZERO_JOINT, h226.ZERO_JOINT]
    changed = 0
    for index, point in enumerate(points):
        baseline_values = h333.hidden_values(point, ROUND49)
        values = (
            baseline_values
            if candidate is None
            else hidden_values(point, candidate)
        )
        metric = h226.metric_for(point, values)
        split = int(not h207.h131.is_train(point.prepared.joint.observed))
        totals[split] = h226.add_metric(totals[split], metric)
        changed += values != baseline_values
        if index % 512 == 0:
            h230.state.cache_clear()
    return tuple(totals), changed


def main() -> None:
    points = h228.points("sweep")
    baseline, _ = score(points, None)
    ranked = []
    for candidate in CANDIDATES:
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
        "h341 exact sine-FADD carrier: "
        f"points={len(points)} baseline={h226.objective(baseline)}"
    )
    for objective, regressions, name, changed, values in ranked:
        print(
            f"  {name}: objective={objective} regressions={regressions} "
            f"changed-values={changed}/{len(points)} values={values}"
        )


if __name__ == "__main__":
    main()
