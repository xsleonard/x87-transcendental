#!/usr/bin/env python3
"""Fit bounded effective low-bit deltas for the last FSIN coefficients.

This does not claim ROM errors.  A delta may equivalently represent product
alignment or a downstream partial-product rule.  Candidates are selected on
one deterministic half and must improve the untouched half before they are
reported as survivors.
"""

from __future__ import annotations

import dataclasses

import h58_constraint_search as h58
import h110_fsin_standalone as h110


def with_delta(
    schedule: h110.Schedule, index: int, delta: int
) -> h110.Schedule:
    values = schedule.coefficient_deltas or (0,) * 6
    changed = list(values)
    changed[index] = delta
    return dataclasses.replace(
        schedule, coefficient_deltas=tuple(changed)
    )


def main() -> None:
    points = h110.load_observed()
    train = [point for point in points if h110.is_train(point)]
    heldout = [point for point in points if not h110.is_train(point)]
    current = h110.FSIN_SURVIVOR

    for index in (4, 5, 3):
        train_sample, train_weights = h110.sample_for_search(
            train, current, 1000
        )
        rows = []
        fingerprints = set()
        for delta in range(-512, 513):
            candidate = with_delta(current, index, delta)
            materialized = h110.coefficient(
                h58.S6[index], candidate, index
            )
            if materialized in fingerprints:
                continue
            fingerprints.add(materialized)
            train_score = h110.score(
                train_sample, candidate, train_weights
            )
            rows.append(
                (
                    train_score.rank(),
                    abs(delta),
                    delta,
                    candidate,
                )
            )
        rows.sort()
        baseline_train = h110.score(train, current)
        baseline_heldout = h110.score(heldout, current)
        print(
            f"\ncoefficient {index + 1}: "
            f"{len(rows)} materialized delta classes"
        )
        accepted = None
        for _, _, delta, candidate in rows[:12]:
            train_score = h110.score(train, candidate)
            heldout_score = h110.score(heldout, candidate)
            print(
                f"  delta={delta:+d}: "
                f"train {train_score.describe()}; "
                f"heldout {heldout_score.describe()}"
            )
            if (
                h110.no_worse(train_score, baseline_train)
                and h110.no_worse(heldout_score, baseline_heldout)
                and (
                    train_score.rank() < baseline_train.rank()
                    or heldout_score.rank() < baseline_heldout.rank()
                )
            ):
                accepted = candidate
                break
        if accepted is not None:
            current = accepted
            print("  accepted")

    print("\nfinal")
    print(f"  {current.short()}")
    print(f"  complete {h110.score(points, current).describe()}")


if __name__ == "__main__":
    main()
