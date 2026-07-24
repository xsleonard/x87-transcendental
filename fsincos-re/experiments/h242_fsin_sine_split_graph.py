#!/usr/bin/env python3
"""Constrain standalone FSIN's two-chain six-term sine graph.

The operation graph evaluates the x^2/x^6/x^10 and x^4/x^8/x^12
coefficient groups as interleaved x^4 chains, combines them, multiplies by
x, and finally adds the leading x.  Fit only the named arithmetic boundaries
while requiring independent improvement on direct and reduced FSIN halves.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Iterable

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h122_fsin_reduced_sine as h122
import h235_fcos_p6_split_graph as h235


@dataclasses.dataclass(frozen=True)
class Schedule:
    square: h110.Quant
    fourth: h110.Quant
    products: tuple[h110.Quant, ...]
    sums: tuple[h110.Quant, ...]
    combine: h110.Quant
    correction: h110.Quant
    final: h110.Quant

    def short(self) -> str:
        products = ",".join(value.short() for value in self.products)
        sums = ",".join(value.short() for value in self.sums)
        return (
            f"sq={self.square.short()}/x4={self.fourth.short()}"
            f"/prod=[{products}]/sum=[{sums}]"
            f"/combine={self.combine.short()}"
            f"/correction={self.correction.short()}"
            f"/final={self.final.short()}"
        )


P6_START = Schedule(
    square=h110.EXACT,
    fourth=h110.Quant(64, "rn"),
    products=(h110.Quant(67, "chop"),) * 6,
    sums=(h110.Quant(67, "chop"),) * 4,
    combine=h110.Quant(67, "chop"),
    correction=h110.Quant(67, "chop"),
    final=h110.EXACT,
)

COSINE_SEED = Schedule(
    square=h235.P6_SURVIVOR.square,
    fourth=h235.P6_SURVIVOR.fourth,
    products=h235.P6_SURVIVOR.products,
    sums=h235.P6_SURVIVOR.sums,
    combine=h235.P6_SURVIVOR.combine,
    correction=h110.Quant(67, "chop"),
    final=h110.EXACT,
)

# Complete-corpus survivor selected independently on direct/reduced halves.
FSIN_SINE_SPLIT_SURVIVOR = Schedule(
    square=h110.Quant(67, "chop"),
    fourth=h110.Quant(65, "rn"),
    products=(
        h110.Quant(67, "chop"),
        h110.Quant(67, "chop"),
        h110.Quant(67, "chop"),
        h110.Quant(67, "chop"),
        h110.Quant(67, "chop"),
        h110.Quant(64, "chop"),
    ),
    sums=(
        h110.Quant(67, "chop"),
        h110.Quant(67, "chop"),
        h110.Quant(64, "rn"),
        h110.Quant(66, "odd"),
    ),
    combine=h110.Quant(64, "rn"),
    correction=h110.Quant(67, "chop"),
    final=h110.EXACT,
)


def coefficient(
    index: int, coefficient_schedule: h110.Schedule
) -> h58.FP:
    return h110.coefficient(
        h58.S6[index], coefficient_schedule, index
    )


def hidden_value(
    point: h110.Observed,
    schedule: Schedule,
    coefficient_schedule: h110.Schedule,
) -> h58.FP:
    raw = point.raw
    magnitude: h58.FP = (0, raw.sig, raw.exponent - 63)
    square = h110.quantize(
        h58.mul_exact(magnitude, magnitude), schedule.square
    )
    fourth = h110.quantize(
        h58.mul_exact(square, square), schedule.fourth
    )

    # x^2/x^6/x^10 chain: ((S5*x^4 + S3)*x^4 + S1)*x^2.
    odd = h110.quantize(
        h58.mul_exact(
            coefficient(1, coefficient_schedule), fourth
        ),
        schedule.products[0],
    )
    odd = h110.quantize(
        h58.add_exact(
            coefficient(3, coefficient_schedule), odd
        ),
        schedule.sums[0],
    )
    odd = h110.quantize(
        h58.mul_exact(odd, fourth), schedule.products[2]
    )
    odd = h110.quantize(
        h58.add_exact(
            coefficient(5, coefficient_schedule), odd
        ),
        schedule.sums[2],
    )
    odd = h110.quantize(
        h58.mul_exact(odd, square), schedule.products[4]
    )

    # x^4/x^8/x^12 chain: ((S6*x^4 + S4)*x^4 + S2)*x^4.
    even = h110.quantize(
        h58.mul_exact(
            coefficient(0, coefficient_schedule), fourth
        ),
        schedule.products[1],
    )
    even = h110.quantize(
        h58.add_exact(
            coefficient(2, coefficient_schedule), even
        ),
        schedule.sums[1],
    )
    even = h110.quantize(
        h58.mul_exact(even, fourth), schedule.products[3]
    )
    even = h110.quantize(
        h58.add_exact(
            coefficient(4, coefficient_schedule), even
        ),
        schedule.sums[3],
    )
    even = h110.quantize(
        h58.mul_exact(even, fourth), schedule.products[5]
    )

    polynomial = h110.quantize(
        h58.add_exact(odd, even), schedule.combine
    )
    correction = h110.quantize(
        h58.mul_exact(polynomial, magnitude), schedule.correction
    )
    result = h110.quantize(
        h58.add_exact(magnitude, correction), schedule.final
    )
    return h58.neg(result) if raw.sign else result


def score(
    points: list[h110.Observed],
    schedule: Schedule,
    coefficient_schedule: h110.Schedule,
    weights: dict[int, float] | None = None,
) -> h110.Score:
    result = h110.Score()
    for point in points:
        weight = (
            weights.get(point.raw.index, 1.0) if weights else 1.0
        )
        hidden = hidden_value(point, schedule, coefficient_schedule)
        result.total += weight
        any_miss = False
        for index, rc in enumerate(h58.RCS):
            expected = point.outputs[index]
            output = h58.x87_round(hidden, rc)
            mismatch = output != expected
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


def point_active(
    point: h110.Observed,
    schedule: Schedule,
    coefficient_schedule: h110.Schedule,
    serial_schedule: h110.Schedule,
) -> bool:
    split = score([point], schedule, coefficient_schedule)
    serial = h110.score([point], serial_schedule)
    return bool(
        split.mode_misses
        or split.c1_misses
        or serial.mode_misses
        or serial.c1_misses
    )


def sample_for_search(
    points: list[h110.Observed],
    schedule: Schedule,
    coefficient_schedule: h110.Schedule,
    serial_schedule: h110.Schedule,
    controls: int,
) -> tuple[list[h110.Observed], dict[int, float]]:
    active = []
    exact_groups: dict[tuple[int, int, int], list[h110.Observed]] = {}
    for point in points:
        if point_active(
            point, schedule, coefficient_schedule, serial_schedule
        ):
            active.append(point)
            continue
        raw = point.raw
        key = raw.sign, raw.exponent, (raw.sig >> 60) & 7
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
                "correction",
                lambda schedule: (
                    dataclasses.replace(schedule, correction=value)
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


def optimize(
    datasets: list[
        tuple[
            str,
            list[h110.Observed],
            h110.Schedule,
            h110.Schedule,
        ]
    ],
    start: Schedule,
    passes: int = 4,
) -> Schedule:
    sampled = []
    for name, points, coefficients, serial in datasets:
        sample, weights = sample_for_search(
            points, start, coefficients, serial, 1536
        )
        sampled.append((name, sample, coefficients, weights))
        print(
            f"{name} search sample: {len(sample)}/{len(points)}",
            flush=True,
        )

    current = start
    for pass_index in range(passes):
        changed = False
        print(f"coordinate pass {pass_index + 1}", flush=True)
        for coordinate in coordinates():
            base = [
                score(points, current, coefficients, weights)
                for _, points, coefficients, weights in sampled
            ]
            ranked = []
            for candidate in dict.fromkeys(
                coordinate.candidates(current)
            ):
                scores = [
                    score(points, candidate, coefficients, weights)
                    for _, points, coefficients, weights in sampled
                ]
                aggregate = tuple(
                    sum(value.rank()[index] for value in scores)
                    for index in range(3)
                )
                ranked.append((aggregate, candidate.short(), candidate, scores))
            ranked.sort()
            accepted = None
            for _, _, candidate, scores in ranked[:16]:
                if all(
                    value.rank() <= old.rank()
                    for value, old in zip(scores, base)
                ) and any(
                    value.rank() < old.rank()
                    for value, old in zip(scores, base)
                ):
                    accepted = candidate, scores
                    break
            if accepted is None:
                continue
            current, scores = accepted
            changed = True
            labels = " ".join(
                f"{name}={value.rank()}"
                for (name, _, _, _), value in zip(sampled, scores)
            )
            print(
                f"  {coordinate.name:10s}: {labels}\n"
                f"    {current.short()}",
                flush=True,
            )
        if not changed:
            break
    return current


def main() -> None:
    direct = h110.load_observed()
    reduced = h122.load_points()
    direct_train = [point for point in direct if h110.is_train(point)]
    direct_held = [point for point in direct if not h110.is_train(point)]
    reduced_train = [point for point in reduced if h122.is_train(point)]
    reduced_held = [point for point in reduced if not h122.is_train(point)]
    datasets = [
        (
            "direct-train",
            direct_train,
            h110.FSIN_SURVIVOR,
            h110.FSIN_SURVIVOR,
        ),
        (
            "direct-held",
            direct_held,
            h110.FSIN_SURVIVOR,
            h110.FSIN_SURVIVOR,
        ),
        (
            "reduced-train",
            reduced_train,
            h122.FSIN_REDUCED_SINE,
            h122.FSIN_REDUCED_SINE,
        ),
        (
            "reduced-held",
            reduced_held,
            h122.FSIN_REDUCED_SINE,
            h122.FSIN_REDUCED_SINE,
        ),
    ]
    print(
        f"loaded direct={len(direct)} reduced={len(reduced)} "
        "standalone-FSIN points"
    )
    print(
        "serial direct:  "
        f"{h110.score(direct, h110.FSIN_SURVIVOR).describe()}"
    )
    print(
        "serial reduced: "
        f"{h110.score(reduced, h122.FSIN_REDUCED_SINE).describe()}"
    )
    for name, candidate in (
        ("split start", P6_START),
        ("cosine seed", COSINE_SEED),
    ):
        print(
            f"{name:14s} direct "
            f"{score(direct, candidate, h110.FSIN_SURVIVOR).describe()}; "
            "reduced "
            f"{score(reduced, candidate, h122.FSIN_REDUCED_SINE).describe()}"
        )

    winner = optimize(datasets, COSINE_SEED)
    if winner != FSIN_SINE_SPLIT_SURVIVOR:
        raise SystemExit("h242 search no longer selects the frozen survivor")
    print("\nstandalone-FSIN sine split survivor")
    print(f"  {winner.short()}")
    print(
        "  direct:  "
        f"{score(direct, winner, h110.FSIN_SURVIVOR).describe()}"
    )
    print(
        "  reduced: "
        f"{score(reduced, winner, h122.FSIN_REDUCED_SINE).describe()}"
    )


if __name__ == "__main__":
    main()
