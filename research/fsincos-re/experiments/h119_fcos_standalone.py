#!/usr/bin/env python3
"""Constrain standalone FCOS's direct cosine-polynomial producer.

This is also relevant to standalone FSIN: after an odd-quadrant range
reduction, FSIN must evaluate cosine of the residual.  The historical h64
search used only Pentium-II RN results.  This pass adds Skylake RD/RU and C1,
and searches independent square, coefficient, Horner-edge, tail-product, and
pre-architectural-sum materializations.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Iterable

import h58_constraint_search as h58
import h64_poly_constraints as h64
import h110_fsin_standalone as h110


CAPTURE = h110.CAPTURE
Quant = h110.Quant
EXACT = h110.EXACT


@dataclasses.dataclass(frozen=True)
class Schedule:
    square: Quant
    coefficient: Quant
    products: tuple[Quant, ...]
    sums: tuple[Quant, ...]
    tail: Quant
    final_sum: Quant = EXACT
    coefficient_overrides: tuple[Quant, ...] = ()

    def short(self) -> str:
        products = ",".join(value.short() for value in self.products)
        sums = ",".join(value.short() for value in self.sums)
        coefficients = (
            "/ci=["
            + ",".join(value.short() for value in self.coefficient_overrides)
            + "]"
            if self.coefficient_overrides
            else ""
        )
        return (
            f"sq={self.square.short()}/c={self.coefficient.short()}"
            f"{coefficients}/prod=[{products}]/sum=[{sums}]"
            f"/tail={self.tail.short()}/final={self.final_sum.short()}"
        )


H64_START = Schedule(
    square=Quant(67, "chop"),
    coefficient=Quant(67, "rn"),
    products=(Quant(66, "chop"),) * 5,
    sums=(Quant(66, "chop"),) * 5,
    tail=Quant(69, "chop"),
)

SHARED_START = Schedule(
    square=Quant(67, "chop"),
    coefficient=Quant(67, "rn"),
    products=(
        EXACT,
        EXACT,
        EXACT,
        EXACT,
        Quant(67, "chop"),
    ),
    sums=(Quant(64, "rn"),) * 5,
    tail=Quant(67, "chop"),
)

FCOS_SURVIVOR = Schedule(
    square=Quant(68, "odd"),
    coefficient=Quant(66, "chop"),
    coefficient_overrides=(
        Quant(66, "chop"),
        Quant(66, "chop"),
        Quant(66, "chop"),
        Quant(66, "chop"),
        Quant(65, "chop"),
        Quant(66, "chop"),
    ),
    products=(
        Quant(66, "chop"),
        Quant(66, "chop"),
        Quant(66, "chop"),
        Quant(66, "chop"),
        Quant(65, "rn"),
    ),
    sums=(
        Quant(66, "chop"),
        Quant(66, "chop"),
        Quant(66, "chop"),
        Quant(64, "chop"),
        Quant(66, "chop"),
    ),
    tail=Quant(72, "away"),
)


@dataclasses.dataclass(frozen=True)
class Observed:
    raw: h64.PolyRaw
    outputs: tuple[tuple[int, int], ...]
    c1: tuple[bool, ...]


Score = h110.Score


def load_observed() -> list[Observed]:
    raw = h64.load_raw()
    paths = [CAPTURE / f"dense_fcos_{rc}_status.txt" for rc in h58.RCS]
    lines = [path.read_text().splitlines() for path in paths]
    if any(len(mode) != 240000 for mode in lines):
        raise SystemExit("extended standalone capture line count differs")
    result = []
    for point in raw:
        outputs = []
        c1 = []
        for mode in lines:
            fields = mode[point.index].split()
            if (
                len(fields) != 5
                or fields[0] != "OK"
                or fields[3] != "SW"
            ):
                raise ValueError(mode[point.index])
            outputs.append((int(fields[1], 16), int(fields[2], 16)))
            c1.append(bool(int(fields[4], 16) & 0x0200))
        if outputs[0] != point.standalone[1]:
            raise SystemExit(
                f"Skylake/PII standalone RN mismatch at {point.index}"
            )
        result.append(Observed(point, tuple(outputs), tuple(c1)))
    return result


def coefficient(row: int, schedule: Schedule, index: int) -> h58.FP:
    quant = (
        schedule.coefficient_overrides[index]
        if schedule.coefficient_overrides
        else schedule.coefficient
    )
    return h110.quantize(h58.ROM[row], quant)


def hidden_value(point: Observed, schedule: Schedule) -> h58.FP:
    magnitude: h58.FP = (
        0,
        point.raw.sig,
        point.raw.exponent - 63,
    )
    square = h110.quantize(
        h58.mul_exact(magnitude, magnitude), schedule.square
    )
    value = coefficient(h58.C6[0], schedule, 0)
    for index, row in enumerate(h58.C6[1:]):
        product = h110.quantize(
            h58.mul_exact(value, square), schedule.products[index]
        )
        value = h110.quantize(
            h58.add_exact(
                product, coefficient(row, schedule, index + 1)
            ),
            schedule.sums[index],
        )
    tail = h110.quantize(
        h58.mul_exact(value, square), schedule.tail
    )
    return h110.quantize(
        h58.add_exact(h58.ONE, tail), schedule.final_sum
    )


def score(
    points: Iterable[Observed],
    schedule: Schedule,
    weights: dict[int, float] | None = None,
) -> Score:
    result = Score()
    for point in points:
        weight = (
            weights.get(point.raw.index, 1.0) if weights else 1.0
        )
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
                predicted_c1 = (
                    h110.compare_magnitude(expected, hidden) > 0
                )
                result.c1_misses += (
                    predicted_c1 != point.c1[index]
                ) * weight
        result.output_misses += any_miss * weight
    return result


def is_train(point: Observed) -> bool:
    raw = point.raw
    return not (
        (
            raw.sig
            ^ (raw.sig >> 19)
            ^ (raw.sig >> 43)
            ^ raw.sign
        )
        & 1
    )


def sample_for_search(
    points: list[Observed], schedule: Schedule, controls: int
) -> tuple[list[Observed], dict[int, float]]:
    active = []
    exact_groups: dict[tuple[int, int], list[Observed]] = {}
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
    print(
        f"search sample: {len(active)} constrained + "
        f"{len(selected) - len(active)} controls "
        f"(weighted to {sum(weights.values()):.0f})"
    )
    return selected, weights


@dataclasses.dataclass(frozen=True)
class Coordinate:
    name: str
    candidates: Callable[[Schedule], Iterable[Schedule]]


def coordinates() -> list[Coordinate]:
    result = [
        Coordinate(
            "square",
            lambda schedule: (
                dataclasses.replace(schedule, square=value)
                for value in h110.quant_options()
            ),
        ),
        Coordinate(
            "coefficient",
            lambda schedule: (
                dataclasses.replace(schedule, coefficient=value)
                for value in h110.quant_options(64, 68)
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
                    for value in h110.quant_options(exact=True)
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
                    for value in h110.quant_options()
                ),
            )
        )
    for index in range(6):
        result.append(
            Coordinate(
                f"coefficient-{index + 1}",
                lambda schedule, index=index: (
                    dataclasses.replace(
                        schedule,
                        coefficient_overrides=h110.replace_tuple(
                            (
                                schedule.coefficient_overrides
                                or (schedule.coefficient,) * 6
                            ),
                            index,
                            value,
                        ),
                    )
                    for value in h110.quant_options(64, 68)
                ),
            )
        )
    result.extend(
        (
            Coordinate(
                "tail",
                lambda schedule: (
                    dataclasses.replace(schedule, tail=value)
                    for value in h110.quant_options(exact=True)
                ),
            ),
            Coordinate(
                "final-sum",
                lambda schedule: (
                    dataclasses.replace(schedule, final_sum=value)
                    for value in h110.quant_options(exact=True)
                ),
            ),
        )
    )
    return result


def optimize(
    train: list[Observed],
    heldout: list[Observed],
    start: Schedule,
    controls: int = 2500,
    passes: int = 4,
) -> Schedule:
    current = start
    train_search, train_weights = sample_for_search(
        train, start, controls
    )
    heldout_search, heldout_weights = sample_for_search(
        heldout, start, controls
    )
    for pass_index in range(passes):
        print(f"\ncoordinate pass {pass_index + 1}")
        changed = False
        for coordinate in coordinates():
            candidates = tuple(dict.fromkeys(coordinate.candidates(current)))
            ranked = sorted(
                (
                    score(train_search, candidate, train_weights).rank(),
                    candidate.short(),
                    candidate,
                )
                for candidate in candidates
            )
            train_base = score(train_search, current, train_weights)
            heldout_base = score(
                heldout_search, current, heldout_weights
            )
            accepted = None
            for _, _, candidate in ranked[:8]:
                train_score = score(
                    train_search, candidate, train_weights
                )
                heldout_score = score(
                    heldout_search, candidate, heldout_weights
                )
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
                f"  {coordinate.name:13s} -> "
                f"train {train_score.describe()}; "
                f"heldout {heldout_score.describe()}"
            )
            print(f"    {current.short()}")
        if not changed:
            break
    return current


def main() -> None:
    points = load_observed()
    train = [point for point in points if is_train(point)]
    heldout = [point for point in points if not is_train(point)]
    print(
        f"loaded {len(points)} standalone cosine-polynomial inputs: "
        f"{len(train)} train, {len(heldout)} held out"
    )
    for name, start in (
        ("h64", H64_START),
        ("shared", SHARED_START),
    ):
        print(f"{name} start: {start.short()}")
        print(f"  train    {score(train, start).describe()}")
        print(f"  heldout  {score(heldout, start).describe()}")
        print(f"  complete {score(points, start).describe()}")

    winner = optimize(train, heldout, H64_START)
    print("\nvalidated standalone FCOS survivor")
    print(f"  {winner.short()}")
    print(f"  train    {score(train, winner).describe()}")
    print(f"  heldout  {score(heldout, winner).describe()}")
    print(f"  complete {score(points, winner).describe()}")


if __name__ == "__main__":
    main()
