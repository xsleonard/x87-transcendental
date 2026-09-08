#!/usr/bin/env python3
"""Constrain FPTAN's shared table-reconstruction FMUL/FSUB classes.

All four reconstruction products share one materialization and all four
subtractions share another.  This is the strongest site distinction exposed
by the operation-class map; per-edge parameters are intentionally absent.
"""

from __future__ import annotations

import dataclasses

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230
import h245_fptan_shared_state as h245


ACTIONS = ("exact",) + tuple(
    f"{mode}{bits}"
    for bits in range(64, 69)
    for mode in ("rn", "chop", "away", "odd")
)


@dataclasses.dataclass(frozen=True)
class Candidate:
    product: str = "exact"
    subtract: str = "exact"

    def short(self) -> str:
        return f"FMUL={self.product} FSUB={self.subtract}"


def quantize(value: h58.FP, action: str) -> h58.FP:
    if action == "exact":
        return value
    mode = action[:-2]
    bits = int(action[-2:])
    return h110.quantize(value, h110.Quant(bits, mode))


def mul(left: h58.FP, right: h58.FP, candidate: Candidate) -> h58.FP:
    return quantize(h58.mul_exact(left, right), candidate.product)


def sub(left: h58.FP, right: h58.FP, candidate: Candidate) -> h58.FP:
    return quantize(
        h58.add_exact(left, h58.neg(right)), candidate.subtract
    )


def values(
    point,
    candidate: Candidate,
    state_candidate: h230.Candidate = h228.CANDIDATE,
):
    prepared = point.prepared.joint.observed.point
    sine_a, cosine_tail = h230.state(point, state_candidate)
    negative_sine = h58.neg(sine_a)
    negative_table_sine = h58.neg(prepared.sin_t)

    denominator_partial = sub(
        mul(negative_table_sine, negative_sine, candidate),
        mul(prepared.cos_t, cosine_tail, candidate),
        candidate,
    )
    denominator = sub(
        prepared.cos_t, denominator_partial, candidate
    )

    numerator_partial = sub(
        mul(prepared.cos_t, negative_sine, candidate),
        mul(prepared.sin_t, cosine_tail, candidate),
        candidate,
    )
    numerator = sub(prepared.sin_t, numerator_partial, candidate)

    if prepared.raw.sign:
        numerator = h58.neg(numerator)
    return h230.h60.rotate(
        (numerator, denominator), point.prepared.joint.observed.signed_n
    )


def metric(
    point,
    hardware,
    candidate: Candidate,
    state_candidate: h230.Candidate = h228.CANDIDATE,
) -> tuple[int, int, int]:
    numerator, denominator = values(point, candidate, state_candidate)
    mode_misses = 0
    c1_misses = 0
    for rc in h58.RCS:
        predicted, increment = h245.round_div(numerator, denominator, rc)
        expected, sw = hardware[rc][point.prepared.joint.observed.index]
        if expected is None:
            raise AssertionError("table FPTAN returned C2")
        mode_misses += predicted != expected
        if predicted == expected:
            c1_misses += increment != bool(sw & 0x0200)
    return mode_misses, bool(mode_misses), c1_misses


def add(left, right):
    return tuple(a + b for a, b in zip(left, right))


def score(
    points,
    hardware,
    candidate: Candidate,
    state_candidate: h230.Candidate = h228.CANDIDATE,
):
    result = (0, 0, 0)
    for point in points:
        result = add(
            result, metric(point, hardware, candidate, state_candidate)
        )
    return result


def sample(points, hardware, count: int):
    constrained = []
    controls = []
    baseline = Candidate()
    for point in points:
        target = constrained if metric(point, hardware, baseline)[0] else controls
        target.append(point)

    def key(point):
        observed = point.prepared.joint.observed
        return (
            observed.point.raw.sig
            ^ (observed.index << 13)
            ^ (observed.signed_n << 5)
        )

    constrained.sort(key=key)
    controls.sort(key=key)
    half = count // 2
    return constrained[:half] + controls[: count - min(half, len(constrained))]


def main() -> None:
    datasets = []
    for name in ("dense", "sweep"):
        hardware = h245.captures(name)
        points = h228.points(name)
        selected = sample(points, hardware, 2400)
        datasets.append((name, points, selected, hardware))
        print(
            f"{name}: complete={len(points)} selected={len(selected)} "
            f"exact={score(selected, hardware, Candidate())}"
        )

    ranked = []
    for product in ACTIONS:
        for subtract in ACTIONS:
            candidate = Candidate(product, subtract)
            results = tuple(
                score(selected, hardware, candidate)
                for _, _, selected, hardware in datasets
            )
            objective = tuple(sum(value[i] for value in results) for i in (0, 2, 1))
            ranked.append((objective, candidate.short(), candidate, results))
    ranked.sort()
    print("selected leaders:")
    for item in ranked[:12]:
        print(f"  {item[0]} {item[1]} {item[3]}")

    print("complete leaders:")
    complete = []
    for _, _, candidate, _ in ranked[:12]:
        results = tuple(
            score(points, hardware, candidate)
            for _, points, _, hardware in datasets
        )
        objective = tuple(sum(value[i] for value in results) for i in (0, 2, 1))
        complete.append((objective, candidate.short(), results))
    for item in sorted(complete):
        print(f"  {item}")


if __name__ == "__main__":
    main()
