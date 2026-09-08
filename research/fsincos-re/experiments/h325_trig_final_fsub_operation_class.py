#!/usr/bin/env python3
"""Transfer the sibling-constrained ordinary-FSUB class to trig.

h277 tested whether the final table reconstruction could inherit the solved
ordinary-FMUL and ordinary-FADD classes.  The reconstructed sequence actually
combines the two table products with ordinary FSUB before the distinct final
add/writeback operation.  FPTAN and F2XM1 independently select chop67 for
ordinary FSUB, so this pass tests that class without changing the graph,
constants, operands, shared sine state, or final architectural add.
"""

from __future__ import annotations

import dataclasses
import functools

import h58_constraint_search as h58
import h60_round16_parity as h60
import h218_fadd_residual_programs as h218
import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230


@dataclasses.dataclass(frozen=True)
class Candidate:
    q_product: str
    correction_fsub: str

    def short(self) -> str:
        return (
            f"q-FMUL={self.q_product} "
            f"correction-FSUB={self.correction_fsub}"
        )


CANDIDATES = tuple(
    Candidate(q_product, correction)
    for q_product in ("odd67", "chop67")
    for correction in ("away67", "chop67", "rn64")
)
LEGACY = Candidate("odd67", "away67")


@functools.lru_cache(maxsize=None)
def local_value(point, cosine_lane: bool, candidate: Candidate):
    prepared = point.prepared.joint.observed.point
    sine, cosine_tail = h230.state(point, h228.CANDIDATE)
    if cosine_lane:
        lead, cross = prepared.cos_t, prepared.sin_t
    else:
        lead, cross = prepared.sin_t, prepared.cos_t

    q_product = h226.quantize(
        h58.mul_exact(lead, cosine_tail), candidate.q_product
    )
    p_product = h226.quantize(
        h58.mul_exact(cross, sine), "chop67"
    )
    if cosine_lane:
        p_product = h58.neg(p_product)
    correction = h226.quantize(
        h58.add_exact(q_product, p_product),
        candidate.correction_fsub,
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


def score(datasets, candidate: Candidate):
    totals = []
    for _, points in datasets:
        total = h226.ZERO_JOINT
        for point in points:
            total = h226.add_metric(
                total,
                h226.metric_for(point, hidden_values(point, candidate)),
            )
        totals.append(total)
    return tuple(totals)


def main() -> None:
    datasets = h218.datasets()
    baseline = score(datasets, LEGACY)
    print(
        "h325 final FSUB operation-class transfer: "
        f"partitions={len(datasets)} "
        f"points={sum(len(points) for _, points in datasets)}"
    )
    for candidate in CANDIDATES:
        values = score(datasets, candidate)
        print(
            f"{candidate.short():50s} "
            f"objective={h226.objective(values)} "
            f"regressions={h226.regressions(values, baseline)}"
        )
        for (name, _), old, new in zip(datasets, baseline, values):
            if new != old:
                print(f"  {name}: {old} -> {new}")


if __name__ == "__main__":
    main()
