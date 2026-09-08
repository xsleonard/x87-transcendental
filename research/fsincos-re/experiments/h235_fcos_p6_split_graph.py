#!/usr/bin/env python3
"""Constrain the standalone-cosine two-chain model.

This model groups the negative x^2/x^6/x^10 terms and the positive
x^4/x^8/x^12 terms into two interleaved chains before combining them and
adding 1 with architectural rounding. h119 uses a serial-Horner equivalence
model. This search varies materialization at the fixed multiply/add boundaries,
with the validated h119 effective coefficient values held fixed."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Iterable

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h119_fcos_standalone as h119


Quant = h110.Quant
EXACT = h110.EXACT


@dataclasses.dataclass(frozen=True)
class Schedule:
    square: Quant
    fourth: Quant
    products: tuple[Quant, ...]
    sums: tuple[Quant, ...]
    combine: Quant
    final: Quant

    def short(self) -> str:
        products = ",".join(value.short() for value in self.products)
        sums = ",".join(value.short() for value in self.sums)
        return (
            f"sq={self.square.short()}/x4={self.fourth.short()}"
            f"/prod=[{products}]/sum=[{sums}]"
            f"/combine={self.combine.short()}/final={self.final.short()}"
        )


P6_START = Schedule(
    square=EXACT,
    fourth=Quant(64, "rn"),
    products=(Quant(67, "chop"),) * 6,
    sums=(Quant(67, "chop"),) * 4,
    combine=Quant(67, "chop"),
    final=EXACT,
)

# h235 complete-corpus winner.  It was selected independently on both halves
# and is ported by the C model's --round38-p6-cosine-split option.
P6_SURVIVOR = Schedule(
    square=Quant(67, "chop"),
    fourth=Quant(64, "rn"),
    products=(
        Quant(67, "chop"),
        Quant(67, "chop"),
        Quant(67, "chop"),
        Quant(67, "chop"),
        Quant(68, "rn"),
        Quant(67, "chop"),
    ),
    sums=(
        Quant(67, "chop"),
        Quant(67, "chop"),
        Quant(64, "rn"),
        Quant(66, "odd"),
    ),
    combine=Quant(66, "chop"),
    final=EXACT,
)


def coefficient(index: int) -> h58.FP:
    return h119.coefficient(
        h58.C6[index], h119.FCOS_SURVIVOR, index
    )


def hidden_value(point: h119.Observed, schedule: Schedule) -> h58.FP:
    magnitude: h58.FP = (
        0,
        point.raw.sig,
        point.raw.exponent - 63,
    )
    square = h110.quantize(
        h58.mul_exact(magnitude, magnitude), schedule.square
    )
    fourth = h110.quantize(
        h58.mul_exact(square, square), schedule.fourth
    )

    # Negative chain: C10*x^4 + C6; then *x^4 + C2; then *x^2.
    negative = h110.quantize(
        h58.mul_exact(coefficient(1), fourth), schedule.products[0]
    )
    negative = h110.quantize(
        h58.add_exact(coefficient(3), negative), schedule.sums[0]
    )
    negative = h110.quantize(
        h58.mul_exact(negative, fourth), schedule.products[2]
    )
    negative = h110.quantize(
        h58.add_exact(coefficient(5), negative), schedule.sums[2]
    )
    negative = h110.quantize(
        h58.mul_exact(negative, square), schedule.products[4]
    )

    # Positive chain: C12*x^4 + C8; then *x^4 + C4; then *x^4.
    positive = h110.quantize(
        h58.mul_exact(coefficient(0), fourth), schedule.products[1]
    )
    positive = h110.quantize(
        h58.add_exact(coefficient(2), positive), schedule.sums[1]
    )
    positive = h110.quantize(
        h58.mul_exact(positive, fourth), schedule.products[3]
    )
    positive = h110.quantize(
        h58.add_exact(coefficient(4), positive), schedule.sums[3]
    )
    positive = h110.quantize(
        h58.mul_exact(positive, fourth), schedule.products[5]
    )

    tail = h110.quantize(
        h58.add_exact(negative, positive), schedule.combine
    )
    return h110.quantize(h58.add_exact(h58.ONE, tail), schedule.final)


def score(points, schedule: Schedule, weights=None) -> h110.Score:
    result = h110.Score()
    for point in points:
        weight = weights.get(point.raw.index, 1.0) if weights else 1.0
        hidden = hidden_value(point, schedule)
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


def sample_for_search(points, schedule: Schedule, controls: int):
    active = []
    exact_groups = {}
    for point in points:
        point_score = score((point,), schedule)
        if point_score.mode_misses or point_score.c1_misses:
            active.append(point)
        else:
            key = point.raw.sign, (point.raw.sig >> 60) & 7
            exact_groups.setdefault(key, []).append(point)
    quota = max(1, controls // len(exact_groups))
    selected = list(active)
    weights = {point.raw.index: 1.0 for point in active}
    for key in sorted(exact_groups):
        group = exact_groups[key]
        count = min(quota, len(group))
        chosen = [
            group[(index * len(group)) // count]
            for index in range(count)
        ]
        selected.extend(chosen)
        group_weight = len(group) / count
        for point in chosen:
            weights[point.raw.index] = group_weight
    return selected, weights


@dataclasses.dataclass(frozen=True)
class Coordinate:
    name: str
    candidates: Callable[[Schedule], Iterable[Schedule]]


def coordinates() -> list[Coordinate]:
    options = h110.quant_options(exact=True)
    result = [
        Coordinate(
            "square",
            lambda schedule: (
                dataclasses.replace(schedule, square=value)
                for value in options
            ),
        ),
        Coordinate(
            "fourth",
            lambda schedule: (
                dataclasses.replace(schedule, fourth=value)
                for value in options
            ),
        ),
    ]
    for index in range(6):
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
                    for value in options
                ),
            )
        )
    for index in range(4):
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
                    for value in options
                ),
            )
        )
    result.extend(
        (
            Coordinate(
                "combine",
                lambda schedule: (
                    dataclasses.replace(schedule, combine=value)
                    for value in options
                ),
            ),
            Coordinate(
                "final",
                lambda schedule: (
                    dataclasses.replace(schedule, final=value)
                    for value in options
                ),
            ),
        )
    )
    return result


def optimize(train, heldout, start: Schedule, passes: int = 4) -> Schedule:
    train_sample, train_weights = sample_for_search(train, start, 1536)
    heldout_sample, heldout_weights = sample_for_search(heldout, start, 1536)
    current = start
    for pass_index in range(passes):
        changed = False
        print(f"coordinate pass {pass_index + 1}", flush=True)
        for coordinate in coordinates():
            train_base = score(train_sample, current, train_weights)
            heldout_base = score(heldout_sample, current, heldout_weights)
            ranked = sorted(
                (
                    score(train_sample, candidate, train_weights).rank(),
                    candidate.short(),
                    candidate,
                )
                for candidate in dict.fromkeys(
                    coordinate.candidates(current)
                )
            )
            accepted = None
            for _, _, candidate in ranked[:10]:
                train_score = score(train_sample, candidate, train_weights)
                heldout_score = score(
                    heldout_sample, candidate, heldout_weights
                )
                if (
                    train_score.rank() <= train_base.rank()
                    and heldout_score.rank() <= heldout_base.rank()
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
                f"  {coordinate.name:10s}: "
                f"train={train_score.rank()} heldout={heldout_score.rank()} "
                f"{current.short()}",
                flush=True,
            )
        if not changed:
            break
    return current


def main() -> None:
    points = h119.load_observed()
    train = [point for point in points if h119.is_train(point)]
    heldout = [point for point in points if not h119.is_train(point)]
    print(
        f"serial h119: {h119.score(points, h119.FCOS_SURVIVOR).describe()}"
    )
    print(f"P6 split start: {score(points, P6_START).describe()}")
    winner = optimize(train, heldout, P6_START)
    print(f"winner: {winner.short()}")
    print(f"  train:   {score(train, winner).describe()}")
    print(f"  heldout: {score(heldout, winner).describe()}")
    print(f"  complete:{score(points, winner).describe()}")


if __name__ == "__main__":
    main()
