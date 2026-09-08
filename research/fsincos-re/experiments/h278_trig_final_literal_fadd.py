#!/usr/bin/env python3
"""Replay the final P6 trig product combine through a literal FADD bus.

h277 rejects a scalar RN64 interpretation of the final FADD. Scalar
rounding is a behavioral proxy at this edge.  This pass keeps h275's solved producer state
and the currently selected product representatives, but replaces the scalar
away67 product combine with the complete alignment/carry/borrow/sticky bus.

Candidates are first ranked on every current residual plus deterministic
controls from each frozen partition.  The best componentwise non-regressing
candidates are then checked on the complete corpus.
"""

from __future__ import annotations

import dataclasses

import h58_constraint_search as h58
import h60_round16_parity as h60
import h110_fsin_standalone as h110
import h200_p5_fadd_bitvector as h200
import h206_p5_fadd_complete as h206
import h218_fadd_residual_programs as h218
import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230


ACTIONS = (
    "retain",
    "rn64",
    "chop64",
    "away64",
    "odd64",
    "rn67",
    "chop67",
    "away67",
    "odd67",
)


@dataclasses.dataclass(frozen=True)
class Candidate:
    mode: str
    normalize: bool
    action: str

    def short(self) -> str:
        return (
            f"FADD={self.mode}/"
            f"{'norm' if self.normalize else 'raw'}/{self.action}"
        )


CANDIDATES = tuple(
    Candidate(mode, normalize, action)
    for mode in h206.MODES
    for normalize in (False, True)
    for action in ACTIONS
)


def materialize(bus: h206.Bus, action: str) -> h58.FP:
    value = bus.value()
    if action == "retain":
        return value
    bits = int(action[-2:])
    mode = action[:-2]
    return h110.quantize(value, h110.Quant(bits, mode))


def local_value(point, cosine_lane: bool, candidate: Candidate):
    prepared = point.prepared.joint.observed.point
    sine, cosine_tail = h230.state(point, h228.CANDIDATE)
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
    correction, _ = h206.fadd(
        h200.normalized_bus(q_product),
        h200.normalized_bus(p_product),
        candidate.mode,
        normalize=candidate.normalize,
    )
    return h58.add_exact(lead, materialize(correction, candidate.action))


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


def sample_dataset(name, points, controls: int = 128):
    residuals = []
    correct = []
    for point in points:
        metric = h226.metric_for(
            point, h230.hidden_values(point, h228.CANDIDATE)
        )
        (residuals if metric != h226.ZERO_JOINT else correct).append(point)
    correct.sort(
        key=lambda point: (
            point.prepared.joint.observed.point.raw.sig
            ^ (point.prepared.joint.observed.index << 11)
            ^ point.prepared.joint.observed.signed_n
        )
    )
    return name, residuals + correct[:controls]


def main() -> None:
    complete = h218.datasets()
    selected = [sample_dataset(name, points) for name, points in complete]
    baseline = score(selected, None)
    print(
        "h278 literal final FADD: "
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
    for item in ranked[:20]:
        print(f"  regressions={item[0]} objective={item[1]} {item[2]}")

    finalists = []
    complete_baseline = score(complete, None)
    for _, _, _, candidate, selected_values in ranked[:20]:
        if not h226.no_worse(selected_values, baseline):
            continue
        values = score(complete, candidate)
        finalists.append(
            (
                h226.regressions(values, complete_baseline),
                h226.objective(values),
                candidate.short(),
                values,
            )
        )
    finalists.sort()
    print(f"complete checked={len(finalists)}")
    for item in finalists:
        print(f"  regressions={item[0]} objective={item[1]} {item[2]}")


if __name__ == "__main__":
    main()
