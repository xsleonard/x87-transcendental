#!/usr/bin/env python3
"""Constrain FPTAN's divide inputs after the h260 reconstruction closure.

h260 leaves only two input residuals after a 64-bit RN read of the complete
sine carrier, shared chop67 FMUL, and shared chop67 FSUB.  This pass tests
whether a uniform materialization of the reconstructed numerator and/or
denominator at the final divide input explains those residuals.

Both inputs are already at most 67 significant bits, so actions at 67 bits
or wider are identities.  The search therefore retains exact plus every
distinct 64..66-bit action and checks all pairs without per-input exceptions.
"""

from __future__ import annotations

import dataclasses

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h228_p6_four_term_c_parity as h228
import h245_fptan_shared_state as h245
import h246_fptan_operation_search as h246
import h260_fptan_multiplier_input_format as h260


ACTIONS = ("exact",) + tuple(
    f"{mode}{bits}"
    for bits in range(64, 67)
    for mode in ("rn", "chop", "away", "odd")
)
RECONSTRUCTION = h260.Candidate("rn64", "exact", "exact")


@dataclasses.dataclass(frozen=True)
class Candidate:
    numerator: str = "exact"
    denominator: str = "exact"

    def short(self) -> str:
        return f"numerator={self.numerator} denominator={self.denominator}"


def quantize(value: h58.FP, action: str) -> h58.FP:
    if action == "exact":
        return value
    return h110.quantize(
        value, h110.Quant(int(action[-2:]), action[:-2])
    )


def metric(point, hardware, candidate: Candidate):
    numerator, denominator = h260.values(point, RECONSTRUCTION)
    numerator = quantize(numerator, candidate.numerator)
    denominator = quantize(denominator, candidate.denominator)
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

    ranked = []
    for numerator in ACTIONS:
        for denominator in ACTIONS:
            candidate = Candidate(numerator, denominator)
            results = tuple(
                score(selected, hardware, candidate)
                for _, _, selected, hardware in datasets
            )
            ranked.append((objective(results), candidate.short(), candidate, results))
    ranked.sort()
    print("selected leaders:")
    for item in ranked[:16]:
        print(f"  {item[0]} {item[1]} {item[3]}")

    complete = []
    for _, _, candidate, _ in ranked[:16]:
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
