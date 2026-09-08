#!/usr/bin/env python3
"""Test whether one standalone-FCOS coefficient has a fixed value bias.

The reconstructed P6 coefficients match the physically decoded P5 cosine
coefficients exactly, but that does not by itself prove that Skylake exposes
the same effective values at the polynomial datapath.  Search an additive
significand bias in each coefficient after h119's selected coefficient
materialization.  Delta steps are normalized so that one step changes the
final cosine by roughly 1/32 x87 ulp at x=3/16; this gives comparable coverage
to low- and high-order terms without an impractical raw-bit brute force.
"""

from __future__ import annotations

import argparse
import dataclasses
import math

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h119_fcos_standalone as h119


MIDPOINT = 3.0 / 16.0
STEPS_EACH_SIDE = 128


@dataclasses.dataclass(frozen=True)
class Candidate:
    row: int = -1
    magnitude_delta: int = 0

    def short(self) -> str:
        if self.row < 0:
            return "unchanged"
        return f"row={self.row} materialized-magnitude-delta={self.magnitude_delta:+d}"


def coefficient(row: int, index: int, candidate: Candidate) -> h58.FP:
    value = h119.coefficient(row, h119.FCOS_SURVIVOR, index)
    if row != candidate.row:
        return value
    sign, significand, scale = value
    significand += candidate.magnitude_delta
    if significand <= 0:
        raise ValueError("coefficient bias removed the significand")
    return sign, significand, scale


def hidden_value(point: h119.Observed, candidate: Candidate) -> h58.FP:
    schedule = h119.FCOS_SURVIVOR
    magnitude: h58.FP = (
        0,
        point.raw.sig,
        point.raw.exponent - 63,
    )
    square = h110.quantize(
        h58.mul_exact(magnitude, magnitude), schedule.square
    )
    value = coefficient(h58.C6[0], 0, candidate)
    for index, row in enumerate(h58.C6[1:]):
        product = h110.quantize(
            h58.mul_exact(value, square), schedule.products[index]
        )
        value = h110.quantize(
            h58.add_exact(product, coefficient(row, index + 1, candidate)),
            schedule.sums[index],
        )
    tail = h110.quantize(
        h58.mul_exact(value, square), schedule.tail
    )
    return h110.quantize(
        h58.add_exact(h58.ONE, tail), schedule.final_sum
    )


def score(points, candidate: Candidate, weights=None) -> h110.Score:
    result = h110.Score()
    for point in points:
        weight = weights.get(point.raw.index, 1.0) if weights else 1.0
        hidden = hidden_value(point, candidate)
        result.total += weight
        any_miss = False
        for index, rc in enumerate(h58.RCS):
            predicted = h58.x87_round(hidden, rc)
            expected = point.outputs[index]
            mismatch = predicted != expected
            result.mode_misses += mismatch * weight
            any_miss |= mismatch
            if not mismatch:
                predicted_c1 = h110.compare_magnitude(expected, hidden) > 0
                result.c1_misses += (
                    predicted_c1 != point.c1[index]
                ) * weight
        result.output_misses += any_miss * weight
    return result


def normalized_step(row: int, index: int) -> int:
    value = h119.coefficient(row, h119.FCOS_SURVIVOR, index)
    power = 12 - 2 * index
    units_per_output_ulp = (
        math.ldexp(1.0, -64 - value[2]) / MIDPOINT**power
    )
    return max(1, round(units_per_output_ulp / 32.0))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rows",
        nargs="*",
        type=int,
        default=list(h58.C6),
        help="P5 ROM rows to scan (default: all six cosine coefficients)",
    )
    parser.add_argument(
        "--fine",
        action="store_true",
        help="also scan every delta between normalized steps for rows 163/164",
    )
    args = parser.parse_args()
    requested_rows = set(args.rows)
    unknown_rows = requested_rows.difference(h58.C6)
    if unknown_rows:
        raise SystemExit(f"unknown cosine coefficient rows: {sorted(unknown_rows)}")

    points = h119.load_observed()
    sample, weights = h119.sample_for_search(
        points, h119.FCOS_SURVIVOR, controls=2048
    )
    baseline = Candidate()
    sample_baseline = score(sample, baseline, weights)
    full_baseline = score(points, baseline)
    print(f"sample baseline: {sample_baseline.describe()}")
    print(f"full baseline:   {full_baseline.describe()}")

    full_results = []
    for index, row in enumerate(h58.C6):
        if row not in requested_rows:
            continue
        step = normalized_step(row, index)
        candidates = [
            Candidate(row, multiple * step)
            for multiple in range(-STEPS_EACH_SIDE, STEPS_EACH_SIDE + 1)
        ]
        ranked = sorted(
            (
                score(sample, candidate, weights).rank(),
                candidate.short(),
                candidate,
            )
            for candidate in candidates
        )
        print(
            f"row {row}: power=x^{12 - 2 * index} step={step} "
            f"best-sample={ranked[0][0]} {ranked[0][2].short()}",
            flush=True,
        )
        for _, _, candidate in ranked[:12]:
            candidate_score = score(points, candidate)
            full_results.append(
                (
                    candidate_score.rank(),
                    candidate.short(),
                    candidate,
                    candidate_score,
                )
            )
        if args.fine and row in (163, 164) and step > 1:
            fine = [
                Candidate(row, delta)
                for delta in range(-step + 1, step)
            ]
            fine_ranked = sorted(
                (
                    score(sample, candidate, weights).rank(),
                    candidate.short(),
                    candidate,
                )
                for candidate in fine
            )
            print(
                f"row {row}: fine best-sample={fine_ranked[0][0]} "
                f"{fine_ranked[0][2].short()}",
                flush=True,
            )
            for _, _, candidate in fine_ranked[:12]:
                candidate_score = score(points, candidate)
                full_results.append(
                    (
                        candidate_score.rank(),
                        candidate.short(),
                        candidate,
                        candidate_score,
                    )
                )

    full_results.sort()
    print("best full-corpus candidates:")
    for rank, _, candidate, candidate_score in full_results[:20]:
        componentwise = all(
            candidate_value <= baseline_value
            for candidate_value, baseline_value in zip(
                candidate_score.rank(), full_baseline.rank()
            )
        )
        marker = (
            " COMPONENTWISE-IMPROVES"
            if componentwise and rank < full_baseline.rank()
            else " MODE-ONLY-TRADEOFF"
            if rank < full_baseline.rank()
            else ""
        )
        print(f"  {rank} {candidate.short()}{marker}")


if __name__ == "__main__":
    main()
