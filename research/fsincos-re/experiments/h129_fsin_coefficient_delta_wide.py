#!/usr/bin/env python3
"""Search wider effective deltas for the last FSIN sine coefficients.

h114 stopped at +/-512 raw ROM units.  Because the coefficient contribution
is attenuated by a^3 or more before reaching the result, that range is below
one output ulp for most rows.  This pass searches row-scaled ranges large
enough to move the hidden result through several rounding thresholds, then
fine-scans any transferable coarse survivor.  Deltas remain equivalent
datapath corrections, not proposed ROM edits.
"""

from __future__ import annotations

import argparse

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h114_fsin_coefficient_delta as h114
import h122_fsin_reduced_sine as h122


SEARCHES = (
    (5, 8192, 16),
    (4, 131072, 256),
    (3, 2097152, 4096),
)


def rank_candidates(
    train_sample,
    train_weights,
    heldout_sample,
    heldout_weights,
    current: h110.Schedule,
    index: int,
    radius: int,
    step: int,
    center: int = 0,
):
    rows = []
    fingerprints = set()
    for offset in range(-radius, radius + 1, step):
        delta = center + offset
        candidate = h114.with_delta(current, index, delta)
        materialized = h110.coefficient(
            h58.S6[index], candidate, index
        )
        if materialized in fingerprints:
            continue
        fingerprints.add(materialized)
        train_score = h110.score(
            train_sample, candidate, train_weights
        )
        heldout_score = h110.score(
            heldout_sample, candidate, heldout_weights
        )
        rows.append(
            (
                tuple(
                    left + right
                    for left, right in zip(
                        train_score.rank(), heldout_score.rank()
                    )
                ),
                abs(offset),
                delta,
                candidate,
            )
        )
    rows.sort()
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--path", choices=("direct", "reduced"), default="direct"
    )
    args = parser.parse_args()
    if args.path == "direct":
        points = h110.load_observed()
        current = h110.FSIN_SURVIVOR
        split = h110.is_train
    else:
        points = h122.load_points()
        current = h122.FSIN_REDUCED_SINE
        split = h122.is_train
    train = [point for point in points if split(point)]
    heldout = [point for point in points if not split(point)]

    for index, radius, step in SEARCHES:
        train_sample, train_weights = h110.sample_for_search(
            train, current, 1200
        )
        heldout_sample, heldout_weights = h110.sample_for_search(
            heldout, current, 1200
        )
        baseline_train = h110.score(train, current)
        baseline_heldout = h110.score(heldout, current)
        rows = rank_candidates(
            train_sample,
            train_weights,
            heldout_sample,
            heldout_weights,
            current,
            index,
            radius,
            step,
        )
        print(
            f"\ncoefficient {index + 1}: "
            f"{len(rows)} coarse materializations"
        )
        accepted = None
        for _, _, delta, candidate in rows[:20]:
            train_score = h110.score(train, candidate)
            heldout_score = h110.score(heldout, candidate)
            print(
                f"  coarse {delta:+d}: "
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
                accepted = delta, candidate
                break
        if accepted is None:
            continue

        center, _ = accepted
        fine_step = max(1, step // 16)
        translated = rank_candidates(
            train_sample,
            train_weights,
            heldout_sample,
            heldout_weights,
            current,
            index,
            step,
            fine_step,
            center,
        )
        for _, _, delta, candidate in translated[:20]:
            train_score = h110.score(train, candidate)
            heldout_score = h110.score(heldout, candidate)
            if (
                h110.no_worse(train_score, baseline_train)
                and h110.no_worse(heldout_score, baseline_heldout)
                and (
                    train_score.rank() < baseline_train.rank()
                    or heldout_score.rank() < baseline_heldout.rank()
                )
            ):
                current = candidate
                print(
                    f"  accepted {delta:+d}: "
                    f"train {train_score.describe()}; "
                    f"heldout {heldout_score.describe()}"
                )
                break

    print("\nfinal")
    print(f"  {current.short()}")
    print(f"  complete {h110.score(points, current).describe()}")


if __name__ == "__main__":
    main()
