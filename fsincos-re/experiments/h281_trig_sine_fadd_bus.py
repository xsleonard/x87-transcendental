#!/usr/bin/env python3
"""Replace the empirical shared-sine bias with a literal retained FADD bus.

h280 traces 719 of 730 frozen residual lanes through a small change in the
shared ``sin(a)`` state.  The current state is RN64(a + P*a^3) followed by an
empirical 4/32- or 5/32-ulp bias.  This pass instead routes the solved chop67
P product and the residual through the complete FADD bus, optionally keeping
the old family bias only as a control.  The downstream table graph is frozen.
"""

from __future__ import annotations

import dataclasses

import h58_constraint_search as h58
import h60_round16_parity as h60
import h79_table_state_bias as h79
import h110_fsin_standalone as h110
import h200_p5_fadd_bitvector as h200
import h206_p5_fadd_complete as h206
import h218_fadd_residual_programs as h218
import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230
import h278_trig_final_literal_fadd as h278


ACTIONS = ("retain", "rn64", "chop64", "away64", "odd64", "odd67")


@dataclasses.dataclass(frozen=True)
class Candidate:
    mode: str
    normalize: bool
    action: str
    keep_bias: bool

    def short(self) -> str:
        return (
            f"sine-FADD={self.mode}/"
            f"{'norm' if self.normalize else 'raw'}/{self.action} "
            f"bias={'family' if self.keep_bias else 'none'}"
        )


CANDIDATES = tuple(
    Candidate(mode, normalize, action, keep_bias)
    for mode in h206.MODES
    for normalize in (False, True)
    for action in ACTIONS
    for keep_bias in (False, True)
)


def materialize(bus: h206.Bus, action: str) -> h58.FP:
    if action == "retain":
        return bus.value()
    if action == "odd67":
        return h110.quantize(bus.value(), h110.Quant(67, "odd"))
    return h110.quantize(
        bus.value(), h110.Quant(64, action[:-2])
    )


def state(point, candidate: Candidate):
    observed = point.prepared.joint.observed
    base = point.prepared.base
    a = observed.point.a
    state_candidate = h228.CANDIDATE
    square = h230.quantize(
        h58.mul_exact(a, a), state_candidate.square
    )
    p = h230.horner(
        h58.S4,
        square,
        base.p_coefficients,
        state_candidate.p_horner_product,
        state_candidate.p_horner_sum,
    )
    p_square = h230.quantize(
        h58.mul_exact(p, square), state_candidate.p_square
    )
    p_times_a = h230.quantize(
        h58.mul_exact(p_square, a), state_candidate.p_times_a
    )
    bus, _ = h206.fadd(
        h200.normalized_bus(a),
        h200.normalized_bus(p_times_a),
        candidate.mode,
        normalize=candidate.normalize,
    )
    sine = materialize(bus, candidate.action)
    if candidate.keep_bias:
        sine = h79.bias_toward_zero(
            sine, 5 if observed.family == "wide" else 4
        )
    _, cosine_tail = h230.state(point, state_candidate)
    return sine, cosine_tail


def local_value(point, cosine_lane: bool, candidate: Candidate):
    prepared = point.prepared.joint.observed.point
    sine, cosine_tail = state(point, candidate)
    if cosine_lane:
        lead, cross = prepared.cos_t, prepared.sin_t
    else:
        lead, cross = prepared.sin_t, prepared.cos_t
    q_product = h226.quantize(
        h58.mul_exact(lead, cosine_tail), "odd67"
    )
    p_product = h226.quantize(
        h58.mul_exact(cross, sine), "chop67"
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


def score(datasets, candidate: Candidate | None):
    totals = []
    for _, points in datasets:
        total = h226.ZERO_JOINT
        for point in points:
            values = (
                h230.hidden_values(point, h228.CANDIDATE)
                if candidate is None
                else hidden_values(point, candidate)
            )
            total = h226.add_metric(total, h226.metric_for(point, values))
        totals.append(total)
    return tuple(totals)


def main() -> None:
    complete = h218.datasets()
    selected = [
        h278.sample_dataset(name, points) for name, points in complete
    ]
    baseline = score(selected, None)
    print(
        "h281 retained sine FADD: "
        f"candidates={len(CANDIDATES)} "
        f"selected={sum(len(points) for _, points in selected)} "
        f"complete={sum(len(points) for _, points in complete)}"
    )
    print(f"baseline selected objective={h226.objective(baseline)}")
    ranked = []
    invalid = 0
    for candidate in CANDIDATES:
        try:
            values = score(selected, candidate)
        except ValueError:
            invalid += 1
            continue
        ranked.append(
            (
                h226.regressions(values, baseline),
                h226.objective(values),
                candidate.short(),
                candidate,
                values,
            )
        )
    ranked.sort()
    print(f"ranked={len(ranked)} invalid={invalid}")
    for item in ranked[:24]:
        print(f"  regressions={item[0]} objective={item[1]} {item[2]}")

    complete_baseline = score(complete, None)
    finalists = []
    for _, _, _, candidate, selected_values in ranked[:24]:
        if not h226.no_worse(selected_values, baseline):
            continue
        values = score(complete, candidate)
        finalists.append(
            (
                h226.regressions(values, complete_baseline),
                h226.objective(values),
                candidate.short(),
            )
        )
    print(f"complete checked={len(finalists)}")
    for item in sorted(finalists):
        print(f"  regressions={item[0]} objective={item[1]} {item[2]}")


if __name__ == "__main__":
    main()
