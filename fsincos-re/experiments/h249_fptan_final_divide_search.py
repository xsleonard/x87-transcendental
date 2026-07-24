#!/usr/bin/env python3
"""Constrain FPTAN's final divide input-port materializations."""

from __future__ import annotations

import dataclasses

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h228_p6_four_term_c_parity as h228
import h245_fptan_shared_state as h245
import h246_fptan_operation_search as h246


ACTIONS = ("exact",) + tuple(
    f"{mode}{bits}"
    for bits in range(64, 73)
    for mode in ("rn", "chop", "away", "odd")
)
RECONSTRUCTION = h246.Candidate("away67", "chop67")


@dataclasses.dataclass(frozen=True)
class Candidate:
    dividend: str = "exact"
    divisor: str = "exact"

    def short(self) -> str:
        return f"dividend={self.dividend} divisor={self.divisor}"


def quantize(value: h58.FP, action: str) -> h58.FP:
    if action == "exact":
        return value
    return h110.quantize(
        value, h110.Quant(int(action[-2:]), action[:-2])
    )


def metric(point, hardware, candidate: Candidate):
    numerator, denominator = h246.values(point, RECONSTRUCTION)
    numerator = quantize(numerator, candidate.dividend)
    denominator = quantize(denominator, candidate.divisor)
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
    for dividend in ACTIONS:
        for divisor in ACTIONS:
            candidate = Candidate(dividend, divisor)
            results = tuple(
                score(selected, hardware, candidate)
                for _, _, selected, hardware in datasets
            )
            objective = tuple(
                sum(value[i] for value in results) for i in (0, 2, 1)
            )
            ranked.append((objective, candidate.short(), candidate, results))
    ranked.sort()
    print(f"candidates={len(ranked)}")
    for item in ranked[:12]:
        print(f"  selected {item[0]} {item[1]} {item[3]}")

    complete = []
    for _, _, candidate, _ in ranked[:12]:
        results = tuple(
            score(points, hardware, candidate)
            for _, points, _, hardware in datasets
        )
        objective = tuple(
            sum(value[i] for value in results) for i in (0, 2, 1)
        )
        complete.append((objective, candidate.short(), results))
    for item in sorted(complete):
        print(f"  complete {item}")


if __name__ == "__main__":
    main()
