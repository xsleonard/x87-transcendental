#!/usr/bin/env python3
"""Constrain h151's surviving internal-cosine tail selectors.

The fresh capture preserves two h150 mechanisms.  This pass evaluates the
complete 64..72-bit/exact tail grid under each selector and requires
componentwise non-regression on the old halves, h147, h148, and every h151
targeted subset.  It then evaluates all ordered pairs of surviving
single-rule mechanisms to expose overlap or precedence.
"""

from __future__ import annotations

import dataclasses

import h110_fsin_standalone as h110
import h119_fcos_standalone as h119
import h121_fsin_internal_cosine as h121
import h146_fsin_cosine_boolean_search as h146
import h147_fsin_cosine_boolean_discriminator as h147
import h148_fsin_cosine_boolean_crossvalidate as h148
import h150_fsin_cosine_boolean_round30 as h150
import h151_fsin_cosine_tail_discriminator as h151


Metric = h146.Metric


@dataclasses.dataclass
class Dataset:
    name: str
    points: list[h121.Point]
    schedules: list[h119.Schedule]
    traces: list[dict[str, int]]
    metrics: list[Metric]
    baseline: Metric


@dataclasses.dataclass(frozen=True)
class Rule:
    feature: str
    value: int
    tail: h110.Quant

    def short(self) -> str:
        return (
            f"{self.tail.short()} if "
            f"{self.feature}={self.value}"
        )


def make_dataset(
    name: str, points: list[h121.Point]
) -> Dataset:
    schedules = [
        h150.base_schedule(point) for point in points
    ]
    traces = [
        h146.trace(point, schedule)
        for point, schedule in zip(points, schedules)
    ]
    metrics = [
        h146.metric(
            point, h146.hidden_value(point, schedule)
        )
        for point, schedule in zip(points, schedules)
    ]
    baseline: Metric = (0, 0, 0)
    for value in metrics:
        baseline = h146.add(baseline, value)
    return Dataset(
        name, points, schedules, traces, metrics, baseline
    )


def datasets() -> list[Dataset]:
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
    metadata = h151.DEFAULT_METADATA.read_text().splitlines()
    result = [
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
    ]
    for candidate in h151.CANDIDATES:
        selected = [
            point
            for point, line in zip(fresh151, metadata)
            if candidate.name in line.split()[-1].split(",")
        ]
        result.append(make_dataset(candidate.name, selected))
    return result


def score(
    dataset: Dataset, rules: tuple[Rule, ...]
) -> Metric:
    result: Metric = (0, 0, 0)
    for point, schedule, features in zip(
        dataset.points, dataset.schedules, dataset.traces
    ):
        selected = schedule
        for rule in rules:
            if features[rule.feature] == rule.value:
                selected = dataclasses.replace(
                    schedule, tail=rule.tail
                )
                break
        result = h146.add(
            result,
            h146.metric(
                point,
                h146.hidden_value(point, selected),
            ),
        )
    return result


def passes(
    values: list[Dataset], scores: tuple[Metric, ...]
) -> bool:
    return all(
        h146.no_worse(value, dataset.baseline)
        for value, dataset in zip(scores, values)
    ) and any(
        value != dataset.baseline
        for value, dataset in zip(scores, values)
    )


def aggregate(scores: tuple[Metric, ...]) -> Metric:
    return tuple(
        sum(score[index] for score in scores)
        for index in range(3)
    )  # type: ignore[return-value]


def ranking(
    rules: tuple[Rule, ...],
    values: list[Dataset],
) -> tuple[
    int, int, int, tuple[str, ...], tuple[Metric, ...]
]:
    scores = tuple(score(dataset, rules) for dataset in values)
    total = aggregate(scores)
    return (
        total[0],
        total[2],
        total[1],
        tuple(rule.short() for rule in rules),
        scores,
    )


def report(
    label: str,
    entries: list[
        tuple[
            int,
            int,
            int,
            tuple[str, ...],
            tuple[Metric, ...],
        ]
    ],
    values: list[Dataset],
    limit: int,
) -> None:
    entries.sort()
    print(f"h152 {label}: {len(entries)} rules survive")
    for entry in entries[:limit]:
        mode, c1, outputs, labels, scores = entry
        print(
            f"  aggregate={(mode, outputs, c1)} "
            f"{' then '.join(labels)}"
        )
        for dataset, value in zip(values, scores):
            if value != dataset.baseline:
                print(
                    f"    {dataset.name:20s} "
                    f"{dataset.baseline}->{value}"
                )


def main() -> None:
    values = datasets()
    for dataset in values:
        print(
            f"h152 baseline {dataset.name:20s} "
            f"n={len(dataset.points):5d} {dataset.baseline}"
        )
    selectors = (
        ("tail.right-low3", 6),
        ("tail.lsb", 1),
    )
    single_entries = []
    single_rules = []
    for feature, value in selectors:
        for tail in h110.quant_options(exact=True):
            rule = Rule(feature, value, tail)
            entry = ranking((rule,), values)
            if passes(values, entry[-1]):
                single_entries.append(entry)
                single_rules.append(rule)
    report("single", single_entries, values, 30)

    pair_entries = []
    for first in single_rules:
        for second in single_rules:
            if first.feature == second.feature:
                continue
            entry = ranking((first, second), values)
            if passes(values, entry[-1]):
                pair_entries.append(entry)
    report("ordered-pair", pair_entries, values, 30)


if __name__ == "__main__":
    main()
