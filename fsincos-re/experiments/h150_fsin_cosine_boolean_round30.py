#!/usr/bin/env python3
"""Gate one-bit internal-cosine rules against every Round 30 dataset.

Round 30 conditionally retains one extra bit in the exact-square
materialization when the product has no high normalization bit.  Starting
from that graph, this pass repeats h146's physically constrained
one-coordinate search and requires every rule to be componentwise no worse
on the old train/heldout halves and on both fresh h147/h148 captures.
"""

from __future__ import annotations

import dataclasses
from collections import defaultdict

import h110_fsin_standalone as h110
import h119_fcos_standalone as h119
import h121_fsin_internal_cosine as h121
import h146_fsin_cosine_boolean_search as h146
import h147_fsin_cosine_boolean_discriminator as h147
import h148_fsin_cosine_boolean_crossvalidate as h148


Metric = h146.Metric
CURRENT = h121.FSIN_INTERNAL_COSINE
LOW_SQUARE = h148.with_square(68, "away")


@dataclasses.dataclass
class Dataset:
    name: str
    points: list[h121.Point]
    schedules: list[h119.Schedule]
    traces: list[dict[str, int]]
    metrics: list[Metric]
    baseline: Metric


def base_schedule(point: h121.Point) -> h119.Schedule:
    significand = point.observed.raw.sig
    normalized_high = (
        (significand * significand).bit_length() == 128
    )
    return CURRENT if normalized_high else LOW_SQUARE


def make_dataset(
    name: str, points: list[h121.Point]
) -> Dataset:
    schedules = [base_schedule(point) for point in points]
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
    for point_metric in metrics:
        baseline = h146.add(baseline, point_metric)
    return Dataset(
        name, points, schedules, traces, metrics, baseline
    )


def preserve_square(
    candidate: h119.Schedule, baseline: h119.Schedule
) -> h119.Schedule:
    return dataclasses.replace(candidate, square=baseline.square)


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
    datasets = [
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
    for dataset in datasets:
        print(
            f"h150 baseline {dataset.name:11s} "
            f"n={len(dataset.points):5d} {dataset.baseline}"
        )

    survivors = []
    tested = 0
    first_trace = datasets[0].traces[0]
    for coordinate in h119.coordinates():
        if (
            coordinate.name == "square"
            or coordinate.name.startswith("coefficient")
        ):
            continue
        candidates = tuple(
            candidate
            for candidate in dict.fromkeys(
                coordinate.candidates(CURRENT)
            )
            if candidate != CURRENT
        )
        feature_names = h146.relevant_features(
            coordinate.name, first_trace
        )
        for candidate in candidates:
            tested += 1
            deltas: dict[
                tuple[str, int], list[Metric]
            ] = defaultdict(
                lambda: [(0, 0, 0) for _ in datasets]
            )
            for dataset_index, dataset in enumerate(datasets):
                for (
                    point,
                    schedule,
                    features,
                    old_metric,
                ) in zip(
                    dataset.points,
                    dataset.schedules,
                    dataset.traces,
                    dataset.metrics,
                ):
                    point_candidate = preserve_square(
                        candidate, schedule
                    )
                    new_metric = h146.metric(
                        point,
                        h146.hidden_value(
                            point, point_candidate
                        ),
                    )
                    delta: Metric = tuple(
                        new - old
                        for new, old in zip(
                            new_metric, old_metric
                        )
                    )  # type: ignore[assignment]
                    for feature in feature_names:
                        key = (feature, features[feature])
                        deltas[key][dataset_index] = h146.add(
                            deltas[key][dataset_index], delta
                        )
            for (feature, value), feature_deltas in deltas.items():
                scores = tuple(
                    h146.add(dataset.baseline, delta)
                    for dataset, delta in zip(
                        datasets, feature_deltas
                    )
                )
                if (
                    all(
                        h146.no_worse(score, dataset.baseline)
                        for score, dataset in zip(
                            scores, datasets
                        )
                    )
                    and any(
                        score != dataset.baseline
                        for score, dataset in zip(
                            scores, datasets
                        )
                    )
                ):
                    aggregate = tuple(
                        sum(score[index] for score in scores)
                        for index in range(3)
                    )
                    survivors.append(
                        (
                            aggregate,
                            coordinate.name,
                            feature,
                            value,
                            candidate.short(),
                            scores,
                        )
                    )
    survivors.sort(
        key=lambda entry: (
            entry[0][0],
            entry[0][2],
            entry[0][1],
            entry[1:5],
        )
    )
    print(
        f"h150 tested {tested} one-coordinate schedules; "
        f"{len(survivors)} all-dataset conditional rules survive"
    )
    for entry in survivors[:40]:
        aggregate, coordinate, feature, value, label, scores = entry
        print(
            f"  {coordinate} if {feature}={value}: "
            f"aggregate={aggregate}"
        )
        for dataset, score in zip(datasets, scores):
            print(f"    {dataset.name:11s} {score}")
        print(f"    {label}")


if __name__ == "__main__":
    main()
