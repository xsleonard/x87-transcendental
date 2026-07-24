#!/usr/bin/env python3
"""Replace FPTAN's scalar FSUB surrogate with the literal 68-bit add bus."""

from __future__ import annotations

import dataclasses

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h206_p5_fadd_complete as h206
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230
import h245_fptan_shared_state as h245
import h246_fptan_operation_search as h246


POST_ACTIONS = ("retain",) + tuple(
    f"{mode}{bits}"
    for bits in (64, 65, 66, 67, 68)
    for mode in ("rn", "chop", "away", "odd")
)


@dataclasses.dataclass(frozen=True)
class Candidate:
    mode: str
    normalize: bool
    post: str

    def short(self) -> str:
        return (
            f"FSUB={self.mode}/{'norm' if self.normalize else 'raw'}"
            f"/{self.post}"
        )


def product(left: h58.FP, right: h58.FP) -> h58.FP:
    return h110.quantize(
        h58.mul_exact(left, right), h110.Quant(67, "away")
    )


def sub(left: h58.FP, right: h58.FP, candidate: Candidate) -> h58.FP:
    bus, _ = h206.fadd(
        h206.h200.normalized_bus(left),
        h206.h200.normalized_bus(h58.neg(right)),
        candidate.mode,
        normalize=candidate.normalize,
    )
    value = bus.value()
    if candidate.post == "retain":
        return value
    return h246.quantize(value, candidate.post)


def values(point, candidate: Candidate):
    prepared = point.prepared.joint.observed.point
    sine_a, cosine_tail = h230.state(point, h228.CANDIDATE)
    negative_sine = h58.neg(sine_a)
    negative_table_sine = h58.neg(prepared.sin_t)

    denominator_partial = sub(
        product(negative_table_sine, negative_sine),
        product(prepared.cos_t, cosine_tail),
        candidate,
    )
    denominator = sub(prepared.cos_t, denominator_partial, candidate)
    numerator_partial = sub(
        product(prepared.cos_t, negative_sine),
        product(prepared.sin_t, cosine_tail),
        candidate,
    )
    numerator = sub(prepared.sin_t, numerator_partial, candidate)
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
        value = metric(point, hardware, candidate)
        result = tuple(a + b for a, b in zip(result, value))
    return result


def main() -> None:
    datasets = []
    for name in ("dense", "sweep"):
        hardware = h245.captures(name)
        points = h228.points(name)
        selected = h246.sample(points, hardware, 2400)
        datasets.append((name, points, selected, hardware))

    ranked = []
    invalid = 0
    for mode in h206.MODES:
        for normalize in (False, True):
            for post in POST_ACTIONS:
                candidate = Candidate(mode, normalize, post)
                try:
                    results = tuple(
                        score(selected, hardware, candidate)
                        for _, _, selected, hardware in datasets
                    )
                except ValueError:
                    invalid += 1
                    continue
                objective = tuple(
                    sum(value[i] for value in results) for i in (0, 2, 1)
                )
                ranked.append((objective, candidate.short(), candidate, results))
    ranked.sort()
    print(f"tested={len(ranked)} invalid={invalid}")
    for item in ranked[:12]:
        print(f"  selected {item[0]} {item[1]} {item[3]}")

    complete = []
    for _, _, candidate, _ in ranked[:12]:
        results = tuple(
            score(points, hardware, candidate)
            for _, points, _, hardware in datasets
        )
        objective = tuple(sum(value[i] for value in results) for i in (0, 2, 1))
        complete.append((objective, candidate.short(), results))
    for item in sorted(complete):
        print(f"  complete {item}")


if __name__ == "__main__":
    main()
