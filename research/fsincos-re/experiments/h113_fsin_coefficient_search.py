#!/usr/bin/env python3
"""Test per-row coefficient materialization in standalone FSIN.

h110's strongest output schedule contains two unusual away-from-zero
representatives near the leading sine coefficients.  This pass checks
whether independently materializing one of the six native 68-bit ROM
constants explains those representatives.  Candidates are ranked on fixed
train/held-out disagreement samples and the leaders are then scored on both
complete halves.
"""

from __future__ import annotations

import dataclasses

import h110_fsin_standalone as h110


def main() -> None:
    points = h110.load_observed()
    train = [point for point in points if h110.is_train(point)]
    heldout = [point for point in points if not h110.is_train(point)]
    train_sample, train_weights = h110.sample_for_search(
        train, h110.MULTISTART, 2500
    )
    heldout_sample, heldout_weights = h110.sample_for_search(
        heldout, h110.MULTISTART, 2500
    )
    baseline_train = h110.score(train, h110.MULTISTART)
    baseline_heldout = h110.score(heldout, h110.MULTISTART)
    print(
        f"baseline train {baseline_train.describe()}; "
        f"heldout {baseline_heldout.describe()}"
    )

    current = h110.MULTISTART
    for index in range(6):
        candidates = []
        for value in h110.quant_options(64, 68):
            overrides = (
                current.coefficient_overrides
                or (current.coefficient,) * 6
            )
            candidate = dataclasses.replace(
                current,
                coefficient_overrides=h110.replace_tuple(
                    overrides, index, value
                ),
            )
            train_score = h110.score(
                train_sample, candidate, train_weights
            )
            heldout_score = h110.score(
                heldout_sample, candidate, heldout_weights
            )
            candidates.append(
                (
                    tuple(
                        left + right
                        for left, right in zip(
                            train_score.rank(), heldout_score.rank()
                        )
                    ),
                    candidate.short(),
                    candidate,
                )
            )
        candidates.sort()
        print(f"\ncoefficient {index + 1}")
        accepted = None
        for _, _, candidate in candidates[:6]:
            train_score = h110.score(train, candidate)
            heldout_score = h110.score(heldout, candidate)
            print(
                f"  {candidate.coefficient_overrides[index].short():5s} "
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
                accepted = candidate, train_score, heldout_score
                break
        if accepted:
            current, baseline_train, baseline_heldout = accepted
            print("  accepted")

    print("\nfinal")
    print(f"  {current.short()}")
    print(f"  train {h110.score(train, current).describe()}")
    print(f"  heldout {h110.score(heldout, current).describe()}")
    print(f"  complete {h110.score(points, current).describe()}")


if __name__ == "__main__":
    main()
