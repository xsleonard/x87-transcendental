#!/usr/bin/env python3
"""Extend the standalone-FSIN normalized width search through 80 bits.

h110 searched 64..72-bit materializations.  This pass keeps its complete
operation graph but tests 64..80 bits (plus exact products) at every square,
Horner product/sum, and tail boundary.  A weighted disagreement/control
sample ranks candidates; complete train and held-out halves decide whether
any change is accepted.
"""

from __future__ import annotations

import argparse
import dataclasses
from collections.abc import Callable, Iterable

import h110_fsin_standalone as h110
import h122_fsin_reduced_sine as h122


@dataclasses.dataclass(frozen=True)
class Coordinate:
    name: str
    candidates: Callable[
        [h110.Schedule], Iterable[h110.Schedule]
    ]


def options(exact: bool = False) -> tuple[h110.Quant, ...]:
    values = tuple(
        h110.Quant(bits, mode)
        for bits in range(64, 81)
        for mode in ("rn", "chop", "odd", "away")
    )
    return ((h110.EXACT,) + values) if exact else values


def coordinates() -> list[Coordinate]:
    result = [
        Coordinate(
            "square",
            lambda schedule: (
                dataclasses.replace(schedule, square=value)
                for value in options()
            ),
        ),
    ]
    for index in range(5):
        result.append(
            Coordinate(
                f"product-{index + 1}",
                lambda schedule, index=index: (
                    dataclasses.replace(
                        schedule,
                        products=h110.replace_tuple(
                            schedule.products, index, value
                        ),
                    )
                    for value in options(exact=True)
                ),
            )
        )
        result.append(
            Coordinate(
                f"sum-{index + 1}",
                lambda schedule, index=index: (
                    dataclasses.replace(
                        schedule,
                        sums=h110.replace_tuple(
                            schedule.sums, index, value
                        ),
                    )
                    for value in options()
                ),
            )
        )
    result.extend(
        (
            Coordinate(
                "m",
                lambda schedule: (
                    dataclasses.replace(schedule, m=value)
                    for value in options(exact=True)
                ),
            ),
            Coordinate(
                "correction",
                lambda schedule: (
                    dataclasses.replace(schedule, correction=value)
                    for value in options(exact=True)
                ),
            ),
        )
    )
    return result


def optimize(
    train: list[h110.Observed],
    heldout: list[h110.Observed],
    start: h110.Schedule,
    passes: int,
) -> h110.Schedule:
    current = start
    train_sample, train_weights = h110.sample_for_search(
        train, start, 2000
    )
    heldout_sample, heldout_weights = h110.sample_for_search(
        heldout, start, 2000
    )
    for pass_index in range(passes):
        print(f"\nextended-width pass {pass_index + 1}")
        changed = False
        for coordinate in coordinates():
            candidates = tuple(
                dict.fromkeys(coordinate.candidates(current))
            )
            ranked = sorted(
                (
                    h110.score(
                        train_sample, candidate, train_weights
                    ).rank(),
                    candidate.short(),
                    candidate,
                )
                for candidate in candidates
            )
            train_base = h110.score(train, current)
            heldout_base = h110.score(heldout, current)
            accepted = None
            for _, _, candidate in ranked[:10]:
                train_score = h110.score(train, candidate)
                heldout_score = h110.score(heldout, candidate)
                if (
                    h110.no_worse(train_score, train_base)
                    and h110.no_worse(heldout_score, heldout_base)
                    and (
                        train_score.rank() < train_base.rank()
                        or heldout_score.rank() < heldout_base.rank()
                    )
                ):
                    accepted = candidate, train_score, heldout_score
                    break
            if accepted is None:
                continue
            current, train_score, heldout_score = accepted
            changed = True
            print(
                f"  {coordinate.name:12s} "
                f"train {train_score.describe()}; "
                f"heldout {heldout_score.describe()}"
            )
            print(f"    {current.short()}")
        if not changed:
            break
    return current


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--path", choices=("direct", "reduced"), default="direct"
    )
    parser.add_argument("--passes", type=int, default=3)
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
    print(
        f"loaded {len(points)} {args.path} sine points: "
        f"{len(train)} train, {len(heldout)} held out"
    )
    print(f"baseline {h110.score(points, base).describe()}")
    winner = optimize(train, heldout, base, args.passes)
    print("\nvalidated extended-width survivor")
    print(f"  {winner.short()}")
    print(f"  train    {h110.score(train, winner).describe()}")
    print(f"  heldout  {h110.score(heldout, winner).describe()}")
    print(f"  complete {h110.score(points, winner).describe()}")


if __name__ == "__main__":
    main()
