#!/usr/bin/env python3
"""Retry the physical P5 tail multiplier after Round 30.

h145 tested X67*Y64 routes before the square-normalization split was known.
This pass preserves Round 30, ranks all 1,728 input-route/output-rounding
combinations on constrained old points plus every fresh capture, and
requires componentwise non-regression on independent complete gates.
"""

from __future__ import annotations

import dataclasses

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h119_fcos_standalone as h119
import h121_fsin_internal_cosine as h121
import h145_fsin_cosine_terminal_fmul as h145
import h146_fsin_cosine_boolean_search as h146
import h147_fsin_cosine_boolean_discriminator as h147
import h148_fsin_cosine_boolean_crossvalidate as h148
import h150_fsin_cosine_boolean_round30 as h150
import h151_fsin_cosine_tail_discriminator as h151


Metric = h146.Metric
State = tuple[h58.FP, h58.FP]


@dataclasses.dataclass
class Dataset:
    name: str
    points: list[h121.Point]
    states: list[State]
    metrics: list[Metric]
    baseline: Metric


def state(point: h121.Point) -> State:
    observed = point.observed
    schedule = h150.base_schedule(point)
    magnitude: h58.FP = (
        0,
        observed.raw.sig,
        observed.raw.exponent - 63,
    )
    square = h110.quantize(
        h58.mul_exact(magnitude, magnitude), schedule.square
    )
    value = h119.coefficient(h58.C6[0], schedule, 0)
    for index, row in enumerate(h58.C6[1:]):
        product = h110.quantize(
            h58.mul_exact(value, square),
            schedule.products[index],
        )
        value = h110.quantize(
            h58.add_exact(
                product,
                h119.coefficient(row, schedule, index + 1),
            ),
            schedule.sums[index],
        )
    return value, square


def hidden(
    point: h121.Point,
    prepared: State,
    route: h145.Route | None,
) -> h58.FP:
    value, square = prepared
    schedule = h150.base_schedule(point)
    tail = (
        h110.quantize(
            h58.mul_exact(value, square), schedule.tail
        )
        if route is None
        else h145.product(value, square, route)
    )
    result = h110.quantize(
        h58.add_exact(h58.ONE, tail),
        schedule.final_sum,
    )
    return h58.neg(result) if point.negate else result


def point_metric(
    point: h121.Point,
    prepared: State,
    route: h145.Route | None,
) -> Metric:
    return h146.metric(point, hidden(point, prepared, route))


def make_dataset(
    name: str, points: list[h121.Point]
) -> Dataset:
    states = [state(point) for point in points]
    metrics = [
        point_metric(point, prepared, None)
        for point, prepared in zip(points, states)
    ]
    baseline: Metric = (0, 0, 0)
    for value in metrics:
        baseline = h146.add(baseline, value)
    return Dataset(name, points, states, metrics, baseline)


def score(
    dataset: Dataset, route: h145.Route | None
) -> Metric:
    result: Metric = (0, 0, 0)
    for point, prepared in zip(
        dataset.points, dataset.states
    ):
        result = h146.add(
            result, point_metric(point, prepared, route)
        )
    return result


def sample(dataset: Dataset, controls: int) -> Dataset:
    active = [
        index
        for index, value in enumerate(dataset.metrics)
        if value != (0, 0, 0)
    ]
    exact = [
        index
        for index, value in enumerate(dataset.metrics)
        if value == (0, 0, 0)
    ]
    count = min(controls, len(exact))
    chosen = active + [
        exact[(index * len(exact)) // count]
        for index in range(count)
    ]
    return make_dataset(
        dataset.name + "-sample",
        [dataset.points[index] for index in chosen],
    )


def no_worse(value: Metric, baseline: Metric) -> bool:
    return all(
        left <= right
        for left, right in zip(value, baseline)
    )


def main() -> None:
    old = h121.load_points()
    fresh147 = h147.load_capture(
        h147.DEFAULT_OUTPUT,
        h121.ROOT
        / "capture-kit-captures"
        / "skylake-fsin-h147",
    )
    fresh148 = h148.load_capture(
        h148.DEFAULT_OUTPUT,
        h121.ROOT
        / "capture-kit-captures"
        / "skylake-fsin-h148",
    )
    fresh151 = h151.load_capture(
        h151.DEFAULT_OUTPUT,
        h121.ROOT
        / "capture-kit-captures"
        / "skylake-fsin-h151",
    )
    complete = [
        make_dataset(
            "old-train",
            [point for point in old if h121.is_train(point)],
        ),
        make_dataset(
            "old-heldout",
            [point for point in old if not h121.is_train(point)],
        ),
        make_dataset("h147", fresh147),
        make_dataset("h148", fresh148),
        make_dataset("h151", fresh151),
    ]
    search = [
        sample(complete[0], 800),
        sample(complete[1], 800),
        *complete[2:],
    ]
    for dataset in complete:
        print(
            f"h153 baseline {dataset.name:11s} "
            f"n={len(dataset.points):5d} {dataset.baseline}"
        )
    ranked = []
    for route in h145.routes():
        scores = tuple(score(dataset, route) for dataset in search)
        if not all(
            no_worse(value, dataset.baseline)
            for value, dataset in zip(scores, search)
        ):
            continue
        aggregate = tuple(
            sum(value[index] for value in scores)
            for index in range(3)
        )
        ranked.append(
            (
                aggregate[0],
                aggregate[2],
                aggregate[1],
                route.short(),
                route,
            )
        )
    ranked.sort()
    print(
        f"h153: {len(ranked)}/{len(h145.routes())} routes "
        "survive all search gates"
    )
    validated = []
    for entry in ranked:
        route = entry[-1]
        scores = tuple(
            score(dataset, route) for dataset in complete
        )
        if all(
            no_worse(value, dataset.baseline)
            for value, dataset in zip(scores, complete)
        ):
            validated.append((*entry[:-1], route, scores))
    print(
        f"h153: {len(validated)} physical routes survive "
        "all complete gates"
    )
    for entry in validated[:30]:
        _, _, _, label, _, scores = entry
        print(f"  {label}")
        for dataset, value in zip(complete, scores):
            print(
                f"    {dataset.name:11s} "
                f"{dataset.baseline}->{value}"
            )


if __name__ == "__main__":
    main()
