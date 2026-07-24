#!/usr/bin/env python3
"""Search interacting fused/separate Horner-edge subsets for FSIN.

Coordinate searches can miss a fused chain when changing one edge alone
loses but changing several together wins.  This pass exhausts all 2^10
combinations in which each of five Horner products and sums is either the
current materialization or exact.  Weighted train/held-out samples rank the
topologies; complete independent halves validate finalists.
"""

from __future__ import annotations

import argparse
import dataclasses

import h110_fsin_standalone as h110
import h122_fsin_reduced_sine as h122


def candidates(base: h110.Schedule):
    for mask in range(1 << 10):
        products = tuple(
            h110.EXACT if mask & (1 << index) else base.products[index]
            for index in range(5)
        )
        sums = tuple(
            h110.EXACT
            if mask & (1 << (index + 5))
            else base.sums[index]
            for index in range(5)
        )
        yield mask, dataclasses.replace(
            base, products=products, sums=sums
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--path", choices=("direct", "reduced"), default="direct"
    )
    parser.add_argument("--keep", type=int, default=30)
    args = parser.parse_args()
    if args.path == "direct":
        points = h110.load_observed()
        base = h110.FSIN_SURVIVOR
        split = h110.is_train
    else:
        points = h122.load_points()
        base = h122.FSIN_REDUCED_SINE
        split = h122.is_train
    train = [point for point in points if split(point)]
    heldout = [point for point in points if not split(point)]
    train_sample, train_weights = h110.sample_for_search(
        train, base, 1500
    )
    heldout_sample, heldout_weights = h110.sample_for_search(
        heldout, base, 1500
    )
    ranked = []
    for mask, candidate in candidates(base):
        train_score = h110.score(
            train_sample, candidate, train_weights
        )
        heldout_score = h110.score(
            heldout_sample, candidate, heldout_weights
        )
        ranked.append(
            (
                train_score.rank(),
                heldout_score.rank(),
                bin(mask).count("1"),
                mask,
                candidate,
            )
        )
    ranked.sort()
    baseline_train = h110.score(train, base)
    baseline_heldout = h110.score(heldout, base)
    print(
        f"loaded {len(points)} {args.path} points; "
        f"baseline train {baseline_train.describe()}; "
        f"heldout {baseline_heldout.describe()}"
    )
    survivors = []
    for _, _, _, mask, candidate in ranked[: args.keep]:
        train_score = h110.score(train, candidate)
        heldout_score = h110.score(heldout, candidate)
        if (
            h110.no_worse(train_score, baseline_train)
            and h110.no_worse(heldout_score, baseline_heldout)
        ):
            survivors.append(
                (
                    train_score.rank(),
                    heldout_score.rank(),
                    bin(mask).count("1"),
                    mask,
                    candidate,
                    train_score,
                    heldout_score,
                )
            )
    survivors.sort()
    print(f"complete-data survivors: {len(survivors)}")
    for row in survivors[:10]:
        _, _, _, mask, candidate, train_score, heldout_score = row
        print(
            f"  mask={mask:03x} train {train_score.describe()}; "
            f"heldout {heldout_score.describe()}"
        )
        print(f"    {candidate.short()}")
    if survivors:
        winner = survivors[0][4]
        print(f"winner complete {h110.score(points, winner).describe()}")


if __name__ == "__main__":
    main()
