#!/usr/bin/env python3
"""Cross-validate simple unions of h158's three surviving selectors.

All three rules choose the same fifth-Horner-sum materialization, chop65,
but select it from different physical bits.  Because h158 declared each
mechanism before capture, its targeted subsets can independently score
their single rules and simple OR combinations.  This pass requires
componentwise non-regression on old train/heldout, h147, h148, h151, and
each h158 targeted subset.
"""

from __future__ import annotations

import dataclasses
import itertools

import h110_fsin_standalone as h110
import h121_fsin_internal_cosine as h121
import h146_fsin_cosine_boolean_search as h146
import h147_fsin_cosine_boolean_discriminator as h147
import h148_fsin_cosine_boolean_crossvalidate as h148
import h151_fsin_cosine_tail_discriminator as h151
import h157_fsin_cosine_two_predicate as h157
import h158_fsin_cosine_two_predicate_discriminator as h158


Metric = h146.Metric
SURVIVOR_NAMES = (
    "sum65c-if-p5norm0-sticky",
    "sum65c-if-p5lsb0-ylo3",
    "sum65c-if-input2-p5lo0",
)
SURVIVORS = tuple(
    candidate
    for candidate in h158.CANDIDATES
    if candidate.name in SURVIVOR_NAMES
)


def schedule(
    point: h121.Point,
    rules: tuple[h158.Conditional, ...],
):
    square_schedule, baseline, features = (
        h157.round31_schedule(point)
    )
    if not any(
        h158.selected(features, rule) for rule in rules
    ):
        return baseline
    altered = dataclasses.replace(
        square_schedule,
        sums=h110.replace_tuple(
            square_schedule.sums,
            4,
            h110.Quant(65, "chop"),
        ),
    )
    altered_features = h146.trace(point, altered)
    return (
        dataclasses.replace(
            altered, tail=h157.ROUND31_TAIL
        )
        if altered_features["tail.lsb"] == 1
        else altered
    )


def metric(
    point: h121.Point,
    rules: tuple[h158.Conditional, ...],
) -> Metric:
    return h146.metric(
        point,
        h146.hidden_value(point, schedule(point, rules)),
    )


def score(
    points: list[h121.Point],
    rules: tuple[h158.Conditional, ...],
) -> Metric:
    result: Metric = (0, 0, 0)
    for point in points:
        result = h146.add(result, metric(point, rules))
    return result


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
    fresh158 = h158.load_capture(
        h158.DEFAULT_OUTPUT,
        h121.ROOT
        / "capture-kit-captures"
        / "skylake-fsin-h158",
    )
    metadata = h158.DEFAULT_METADATA.read_text().splitlines()
    datasets = [
        (
            "old-train",
            [point for point in old if h121.is_train(point)],
        ),
        (
            "old-heldout",
            [point for point in old if not h121.is_train(point)],
        ),
        ("h147", fresh147),
        ("h148", fresh148),
        ("h151", fresh151),
        ("h158", fresh158),
    ]
    for candidate in h158.CANDIDATES:
        datasets.append(
            (
                candidate.name,
                [
                    point
                    for point, line in zip(
                        fresh158, metadata
                    )
                    if candidate.name
                    in line.split()[-1].split(",")
                ],
            )
        )
    baselines = tuple(
        score(points, ()) for _, points in datasets
    )
    for (name, points), baseline in zip(
        datasets, baselines
    ):
        print(
            f"h159 baseline {name:29s} "
            f"n={len(points):5d} {baseline}"
        )
    ranked = []
    for count in range(1, len(SURVIVORS) + 1):
        for rules in itertools.combinations(SURVIVORS, count):
            scores = tuple(
                score(points, rules)
                for _, points in datasets
            )
            if not all(
                no_worse(value, baseline)
                for value, baseline in zip(scores, baselines)
            ):
                continue
            old = tuple(
                scores[0][index] + scores[1][index]
                for index in range(3)
            )
            fresh = tuple(
                sum(value[index] for value in scores[2:])
                for index in range(3)
            )
            ranked.append(
                (
                    old[0],
                    old[2],
                    old[1],
                    fresh[0],
                    fresh[2],
                    fresh[1],
                    tuple(rule.name for rule in rules),
                    scores,
                )
            )
    ranked.sort()
    print(
        f"h159: {len(ranked)}/7 simple unions survive"
    )
    for entry in ranked:
        *_, names, scores = entry
        print(f"  {' OR '.join(names)}")
        for (name, _), baseline, value in zip(
            datasets, baselines, scores
        ):
            if value != baseline:
                print(f"    {name:29s} {baseline}->{value}")


if __name__ == "__main__":
    main()
