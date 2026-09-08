#!/usr/bin/env python3
"""Localize h260's two FPTAN residuals to one reconstruction node.

The baseline uses an RN64 read of the complete sine carrier followed by
chop67 at all four ordinary products and all four subtracts.  It misses only
two inputs.  Their final quotient orientation initially makes both look like
one-unit numerator corrections, but one odd-quadrant case uses the local
cosine lane as the quotient numerator.  This historical diagnostic varies
one named local graph node at a time; later propagated, quadrant-aware work
supersedes its final-numerator interpretation.
"""

from __future__ import annotations

import dataclasses

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230
import h245_fptan_shared_state as h245
import h246_fptan_operation_search as h246
import h260_fptan_multiplier_input_format as h260


ACTIONS = ("exact",) + tuple(
    f"{mode}{bits}"
    for bits in range(64, 69)
    for mode in ("rn", "chop", "away", "odd")
)
FIELDS = (
    "denominator_sine_product",
    "denominator_tail_product",
    "numerator_sine_product",
    "numerator_tail_product",
    "denominator_partial",
    "denominator_final",
    "numerator_partial",
    "numerator_final",
)
INPUTS = h260.Candidate("rn64", "exact", "exact")


@dataclasses.dataclass(frozen=True)
class Candidate:
    denominator_sine_product: str = "chop67"
    denominator_tail_product: str = "chop67"
    numerator_sine_product: str = "chop67"
    numerator_tail_product: str = "chop67"
    denominator_partial: str = "chop67"
    denominator_final: str = "chop67"
    numerator_partial: str = "chop67"
    numerator_final: str = "chop67"

    def short(self) -> str:
        changed = [
            f"{field}={getattr(self, field)}"
            for field in FIELDS
            if getattr(self, field) != "chop67"
        ]
        return ",".join(changed) if changed else "all=chop67"


def quantize(value: h58.FP, action: str) -> h58.FP:
    if action == "exact":
        return value
    return h110.quantize(
        value, h110.Quant(int(action[-2:]), action[:-2])
    )


def product(left: h58.FP, right: h58.FP, action: str) -> h58.FP:
    return quantize(h58.mul_exact(left, right), action)


def sub(left: h58.FP, right: h58.FP, action: str) -> h58.FP:
    return quantize(h58.add_exact(left, h58.neg(right)), action)


def values(point, candidate: Candidate):
    prepared = point.prepared.joint.observed.point
    sine_a, cosine_tail = h230.state(point, h260.LEGACY_STATE)
    sine_a = h260.quantize(sine_a, "rn64")
    negative_sine = h58.neg(sine_a)
    negative_table_sine = h58.neg(prepared.sin_t)

    denominator_partial = sub(
        product(
            negative_table_sine,
            negative_sine,
            candidate.denominator_sine_product,
        ),
        product(
            prepared.cos_t,
            cosine_tail,
            candidate.denominator_tail_product,
        ),
        candidate.denominator_partial,
    )
    denominator = sub(
        prepared.cos_t,
        denominator_partial,
        candidate.denominator_final,
    )
    numerator_partial = sub(
        product(
            prepared.cos_t,
            negative_sine,
            candidate.numerator_sine_product,
        ),
        product(
            prepared.sin_t,
            cosine_tail,
            candidate.numerator_tail_product,
        ),
        candidate.numerator_partial,
    )
    numerator = sub(
        prepared.sin_t, numerator_partial, candidate.numerator_final
    )
    if prepared.raw.sign:
        numerator = h58.neg(numerator)
    return h230.h60.rotate(
        (numerator, denominator), point.prepared.joint.observed.signed_n
    )


def metric(point, hardware, candidate: Candidate):
    numerator, denominator = values(point, candidate)
    modes = 0
    c1 = 0
    for rc in h58.RCS:
        predicted, increment = h245.round_div(numerator, denominator, rc)
        expected, sw = hardware[rc][point.prepared.joint.observed.index]
        if expected is None:
            raise AssertionError("table FPTAN returned C2")
        modes += predicted != expected
        if predicted == expected:
            c1 += increment != bool(sw & 0x0200)
    return modes, bool(modes), c1


def score(points, hardware, candidate: Candidate):
    result = (0, 0, 0)
    for point in points:
        result = h246.add(result, metric(point, hardware, candidate))
    return result


def sample(points, hardware, count: int):
    constrained = []
    controls = []
    baseline = Candidate()
    for point in points:
        target = constrained if any(metric(point, hardware, baseline)) else controls
        target.append(point)

    def key(point):
        observed = point.prepared.joint.observed
        return (
            observed.point.raw.sig
            ^ (observed.index << 13)
            ^ (observed.signed_n << 5)
        )

    controls.sort(key=key)
    return constrained + controls[: max(0, count - len(constrained))]


def objective(results):
    return tuple(sum(value[i] for value in results) for i in (0, 2, 1))


def main() -> None:
    datasets = []
    for name in ("dense", "sweep"):
        hardware = h245.captures(name)
        points = h228.points(name)
        selected = sample(points, hardware, 2400)
        datasets.append((name, points, selected, hardware))
        print(
            f"{name}: complete={len(points)} selected={len(selected)} "
            f"baseline={score(points, hardware, Candidate())}",
            flush=True,
        )

    candidates = {Candidate()}
    for field in FIELDS:
        for action in ACTIONS:
            candidates.add(dataclasses.replace(Candidate(), **{field: action}))
    ranked = []
    for candidate in candidates:
        results = tuple(
            score(selected, hardware, candidate)
            for _, _, selected, hardware in datasets
        )
        ranked.append((objective(results), candidate.short(), candidate, results))
    ranked.sort()
    print(f"single-node candidates={len(ranked)}")
    print("selected leaders:")
    for item in ranked[:20]:
        print(f"  {item[0]} {item[1]} {item[3]}")

    complete = []
    for _, _, candidate, _ in ranked[:20]:
        results = tuple(
            score(points, hardware, candidate)
            for _, points, _, hardware in datasets
        )
        complete.append((objective(results), candidate.short(), results))
    print("complete leaders:")
    for item in sorted(complete):
        print(f"  {item}")


if __name__ == "__main__":
    main()
