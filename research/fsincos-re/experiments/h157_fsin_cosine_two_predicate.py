#!/usr/bin/env python3
"""Search two-bit physical selectors for the old Round 31 residuals.

The remaining old internal-cosine intervals need corrections in both
directions, so no single physical bit cleanly selects them.  This pass
chooses one already-enumerated materialization only when two local datapath
predicates are simultaneously true.  Eligible predicates remain limited to
normalization, retained/guard/sticky bits, low operand bits, trailing-zero
thresholds, input low bits, and output negation.

Every rule must be componentwise no worse on the old train/heldout halves,
h147, h148, pooled h151, and all six h151 targeted subsets.  It must improve
at least one old half.  Results remain hypotheses until a new hardware-blind
capture validates them.
"""

from __future__ import annotations

import dataclasses
import itertools
from collections import defaultdict

import h110_fsin_standalone as h110
import h119_fcos_standalone as h119
import h121_fsin_internal_cosine as h121
import h146_fsin_cosine_boolean_search as h146
import h147_fsin_cosine_boolean_discriminator as h147
import h148_fsin_cosine_boolean_crossvalidate as h148
import h150_fsin_cosine_boolean_round30 as h150
import h151_fsin_cosine_tail_discriminator as h151


Metric = h146.Metric
CURRENT = h121.FSIN_INTERNAL_COSINE
ROUND31_TAIL = h110.Quant(71, "chop")


@dataclasses.dataclass
class Dataset:
    name: str
    points: list[h121.Point]
    square_schedules: list[h119.Schedule]
    schedules: list[h119.Schedule]
    traces: list[dict[str, int]]
    metrics: list[Metric]
    baseline: Metric


def round31_schedule(
    point: h121.Point,
) -> tuple[h119.Schedule, h119.Schedule, dict[str, int]]:
    square_schedule = h150.base_schedule(point)
    features = h146.trace(point, square_schedule)
    schedule = (
        dataclasses.replace(
            square_schedule, tail=ROUND31_TAIL
        )
        if features["tail.lsb"] == 1
        else square_schedule
    )
    return square_schedule, schedule, features


def make_dataset(
    name: str, points: list[h121.Point]
) -> Dataset:
    prepared = [
        round31_schedule(point) for point in points
    ]
    square_schedules = [item[0] for item in prepared]
    schedules = [item[1] for item in prepared]
    traces = [item[2] for item in prepared]
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
        name,
        points,
        square_schedules,
        schedules,
        traces,
        metrics,
        baseline,
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
        make_dataset("h151", fresh151),
    ]
    for selector in h151.CANDIDATES:
        selected = [
            point
            for point, line in zip(fresh151, metadata)
            if selector.name in line.split()[-1].split(",")
        ]
        result.append(make_dataset(selector.name, selected))
    return result


def relevant_features(
    coordinate: str, features: dict[str, int]
) -> tuple[str, ...]:
    prefixes = ["global."]
    if coordinate == "square":
        prefixes.append("square.")
    elif coordinate.startswith("product-"):
        prefixes.extend(("square.", coordinate + "."))
    elif coordinate.startswith("sum-"):
        index = coordinate.split("-")[1]
        prefixes.extend(
            (f"product-{index}.", coordinate + ".")
        )
    elif coordinate == "tail":
        prefixes.extend(
            ("square.", "product-5.", "sum-5.", "tail.")
        )
    elif coordinate == "final-sum":
        prefixes.extend(
            ("tail.", "final-sum.")
        )
    return tuple(
        key
        for key in features
        if key != "global.exponent"
        and any(key.startswith(prefix) for prefix in prefixes)
    )


def candidate_schedule(
    coordinate: str,
    template: h119.Schedule,
    dataset: Dataset,
    index: int,
) -> h119.Schedule:
    schedule = dataclasses.replace(
        template,
        square=dataset.square_schedules[index].square,
    )
    if coordinate != "tail":
        schedule = dataclasses.replace(
            schedule, tail=dataset.schedules[index].tail
        )
    return schedule


def no_worse(value: Metric, baseline: Metric) -> bool:
    return all(
        left <= right
        for left, right in zip(value, baseline)
    )


def main() -> None:
    values = datasets()
    for dataset in values:
        print(
            f"h157 baseline {dataset.name:20s} "
            f"n={len(dataset.points):5d} {dataset.baseline}"
        )
    first_trace = values[0].traces[0]
    tested = 0
    survivors = []
    for coordinate in h119.coordinates():
        if (
            coordinate.name == "square"
            or coordinate.name.startswith("coefficient")
        ):
            continue
        templates = tuple(
            template
            for template in dict.fromkeys(
                coordinate.candidates(CURRENT)
            )
            if template != CURRENT
        )
        feature_names = relevant_features(
            coordinate.name, first_trace
        )
        for template in templates:
            tested += 1
            deltas: dict[
                tuple[
                    tuple[str, int], tuple[str, int]
                ],
                list[Metric],
            ] = defaultdict(
                lambda: [(0, 0, 0) for _ in values]
            )
            for dataset_index, dataset in enumerate(values):
                for point_index, (
                    point,
                    features,
                    old_metric,
                ) in enumerate(
                    zip(
                        dataset.points,
                        dataset.traces,
                        dataset.metrics,
                    )
                ):
                    schedule = candidate_schedule(
                        coordinate.name,
                        template,
                        dataset,
                        point_index,
                    )
                    new_metric = h146.metric(
                        point,
                        h146.hidden_value(point, schedule),
                    )
                    delta: Metric = tuple(
                        new - old
                        for new, old in zip(
                            new_metric, old_metric
                        )
                    )  # type: ignore[assignment]
                    if delta == (0, 0, 0):
                        continue
                    predicates = tuple(
                        (feature, features[feature])
                        for feature in feature_names
                    )
                    for left, right in itertools.combinations(
                        predicates, 2
                    ):
                        key = tuple(sorted((left, right)))
                        deltas[key][
                            dataset_index
                        ] = h146.add(
                            deltas[key][dataset_index], delta
                        )
            for predicates, predicate_deltas in deltas.items():
                scores = tuple(
                    h146.add(dataset.baseline, delta)
                    for dataset, delta in zip(
                        values, predicate_deltas
                    )
                )
                if not all(
                    no_worse(score, dataset.baseline)
                    for score, dataset in zip(scores, values)
                ):
                    continue
                if not any(
                    scores[index] != values[index].baseline
                    for index in (0, 1)
                ):
                    continue
                old_score = tuple(
                    scores[0][index] + scores[1][index]
                    for index in range(3)
                )
                fresh_score = tuple(
                    sum(score[index] for score in scores[2:])
                    for index in range(3)
                )
                survivors.append(
                    (
                        old_score[0],
                        old_score[2],
                        old_score[1],
                        fresh_score[0],
                        fresh_score[2],
                        fresh_score[1],
                        coordinate.name,
                        predicates,
                        template.short(),
                        scores,
                    )
                )
    survivors.sort()
    print(
        f"h157 tested {tested} one-coordinate schedules; "
        f"{len(survivors)} two-predicate old-improving "
        "rules survive"
    )
    for entry in survivors[:40]:
        (
            old_mode,
            old_c1,
            old_output,
            fresh_mode,
            fresh_c1,
            fresh_output,
            coordinate,
            predicates,
            label,
            scores,
        ) = entry
        print(
            f"  {coordinate} if {predicates[0]} and "
            f"{predicates[1]}: "
            f"old={(old_mode, old_output, old_c1)} "
            f"fresh={(fresh_mode, fresh_output, fresh_c1)}"
        )
        for dataset, score in zip(values, scores):
            if score != dataset.baseline:
                print(
                    f"    {dataset.name:20s} "
                    f"{dataset.baseline}->{score}"
                )
        print(f"    {label}")


if __name__ == "__main__":
    main()
