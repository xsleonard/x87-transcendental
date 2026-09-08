#!/usr/bin/env python3
"""Search for the missing companion to h161's rejected Round-33 rule.

h161 shows that its second fifth-sum selector improves hidden-value/C1
placement but regresses architectural values when applied by itself.  This
pass treats h161 as a new train/heldout dataset and asks two bounded
questions:

* does the same selector belong to a different single materialization?
* does chop65 at the fifth sum require one additional materialization?

Candidates are limited to the already-enumerated square, coefficient,
Horner, tail, and final grids.  They are searched on both h161 halves, then
survivors are gated against all older internal-cosine datasets.
"""

from __future__ import annotations

import dataclasses
import functools

import h110_fsin_standalone as h110
import h119_fcos_standalone as h119
import h121_fsin_internal_cosine as h121
import h146_fsin_cosine_boolean_search as h146
import h147_fsin_cosine_boolean_discriminator as h147
import h148_fsin_cosine_boolean_crossvalidate as h148
import h150_fsin_cosine_boolean_round30 as h150
import h151_fsin_cosine_tail_discriminator as h151
import h157_fsin_cosine_two_predicate as h157
import h158_fsin_cosine_two_predicate_discriminator as h158
import h159_fsin_cosine_two_predicate_union as h159
import h161_fsin_cosine_round32_composition as h161


Metric = h146.Metric
CURRENT = h121.FSIN_INTERNAL_COSINE
PRIMARY = dataclasses.replace(
    CURRENT,
    sums=h110.replace_tuple(
        CURRENT.sums, 4, h110.Quant(65, "chop")
    ),
)


@dataclasses.dataclass(frozen=True)
class Variant:
    label: str
    schedule: h119.Schedule
    coordinate: str
    tail_policy: str = "dynamic"


@functools.cache
def selected(point: h121.Point) -> bool:
    _, _, features = h157.round31_schedule(point)
    return (
        not h158.selected(features, h161.ROUND32)
        and h158.selected(features, h161.SECOND)
    )


@functools.cache
def baseline_schedule(point: h121.Point) -> h119.Schedule:
    return h159.schedule(point, (h161.ROUND32,))


def variant_schedule(
    point: h121.Point, variant: Variant
) -> h119.Schedule:
    baseline = baseline_schedule(point)
    if not selected(point):
        return baseline
    schedule = variant.schedule
    if variant.coordinate != "square":
        schedule = dataclasses.replace(
            schedule, square=h150.base_schedule(point).square
        )
    if variant.tail_policy == "preserve":
        return dataclasses.replace(schedule, tail=baseline.tail)
    if variant.tail_policy == "fixed":
        return schedule
    features = h146.trace(point, schedule)
    return (
        dataclasses.replace(
            schedule, tail=h157.ROUND31_TAIL
        )
        if features["tail.lsb"] == 1
        else schedule
    )


def point_metric(
    point: h121.Point, variant: Variant | None
) -> Metric:
    schedule = (
        baseline_schedule(point)
        if variant is None
        else variant_schedule(point, variant)
    )
    return h146.metric(
        point, h146.hidden_value(point, schedule)
    )


def score(
    points: list[h121.Point], variant: Variant | None
) -> Metric:
    result: Metric = (0, 0, 0)
    for point in points:
        result = h146.add(
            result, point_metric(point, variant)
        )
    return result


def no_worse(value: Metric, baseline: Metric) -> bool:
    return all(
        left <= right
        for left, right in zip(value, baseline)
    )


def variants() -> list[Variant]:
    result = []
    for coordinate in h119.coordinates():
        for candidate in dict.fromkeys(
            coordinate.candidates(CURRENT)
        ):
            if candidate == CURRENT:
                continue
            result.append(
                Variant(
                    f"single {coordinate.name}: {candidate.short()}",
                    candidate,
                    coordinate.name,
                    (
                        "fixed"
                        if coordinate.name == "tail"
                        else "dynamic"
                    ),
                )
            )
    result.append(
        Variant(
            "sum65 plus recomputed Round-31 tail",
            PRIMARY,
            "sum-5",
        )
    )
    result.append(
        Variant(
            "sum65 plus preserved Round-31 tail",
            PRIMARY,
            "sum-5",
            "preserve",
        )
    )
    for coordinate in h119.coordinates():
        if coordinate.name == "sum-5":
            continue
        for candidate in dict.fromkeys(
            coordinate.candidates(PRIMARY)
        ):
            if candidate == PRIMARY:
                continue
            result.append(
                Variant(
                    f"sum65 plus {coordinate.name}: "
                    f"{candidate.short()}",
                    candidate,
                    coordinate.name,
                    (
                        "fixed"
                        if coordinate.name == "tail"
                        else "dynamic"
                    ),
                )
            )
    return result


def old_datasets() -> list[tuple[str, list[h121.Point]]]:
    old = h121.load_points()
    return [
        (
            "old-train",
            [point for point in old if h121.is_train(point)],
        ),
        (
            "old-heldout",
            [
                point
                for point in old
                if not h121.is_train(point)
            ],
        ),
        (
            "h147",
            h147.load_capture(
                h147.DEFAULT_OUTPUT,
                h121.ROOT
                / "capture-kit-captures"
                / "skylake-fsin-h147",
            ),
        ),
        (
            "h148",
            h148.load_capture(
                h148.DEFAULT_OUTPUT,
                h121.ROOT
                / "capture-kit-captures"
                / "skylake-fsin-h148",
            ),
        ),
        (
            "h151",
            h151.load_capture(
                h151.DEFAULT_OUTPUT,
                h121.ROOT
                / "capture-kit-captures"
                / "skylake-fsin-h151",
            ),
        ),
        (
            "h158",
            h158.load_capture(
                h158.DEFAULT_OUTPUT,
                h121.ROOT
                / "capture-kit-captures"
                / "skylake-fsin-h158",
            ),
        ),
    ]


def main() -> None:
    fresh = h161.load_capture(
        h161.DEFAULT_OUTPUT,
        h121.ROOT
        / "capture-kit-captures"
        / "skylake-fsin-h161",
    )
    train = [
        point for point in fresh if h121.is_train(point)
    ]
    heldout = [
        point for point in fresh if not h121.is_train(point)
    ]
    if not all(selected(point) for point in fresh):
        raise SystemExit("h161 contains a point outside E && !D")
    train_base = score(train, None)
    heldout_base = score(heldout, None)
    print(
        f"h162 baseline h161-train n={len(train):3d} "
        f"{train_base}"
    )
    print(
        f"h162 baseline h161-held  n={len(heldout):3d} "
        f"{heldout_base}"
    )
    searched = variants()
    h161_survivors = []
    for variant in searched:
        train_score = score(train, variant)
        heldout_score = score(heldout, variant)
        if (
            no_worse(train_score, train_base)
            and no_worse(heldout_score, heldout_base)
            and (
                train_score != train_base
                or heldout_score != heldout_base
            )
        ):
            h161_survivors.append(
                (
                    train_score[0] + heldout_score[0],
                    train_score[2] + heldout_score[2],
                    train_score[1] + heldout_score[1],
                    variant.label,
                    variant,
                    train_score,
                    heldout_score,
                )
            )
    h161_survivors.sort()
    print(
        f"h162: {len(h161_survivors)}/{len(searched)} "
        "variants survive both h161 halves"
    )
    for entry in h161_survivors[:20]:
        _, _, _, label, _, train_score, heldout_score = entry
        print(
            f"  {label}\n"
            f"    train {train_base}->{train_score}; "
            f"held {heldout_base}->{heldout_score}"
        )

    datasets = old_datasets()
    baselines = [
        score(points, None) for _, points in datasets
    ]
    gated = []
    for entry in h161_survivors:
        variant = entry[4]
        scores = [
            score(points, variant)
            for _, points in datasets
        ]
        if all(
            no_worse(value, baseline)
            for value, baseline in zip(scores, baselines)
        ):
            gated.append((*entry[:4], scores))
    gated.sort()
    print(
        f"h162: {len(gated)}/{len(h161_survivors)} "
        "h161 survivors pass all old/fresh gates"
    )
    for entry in gated[:20]:
        _, _, _, label, scores = entry
        print(f"  {label}")
        for (name, _), baseline, value in zip(
            datasets, baselines, scores
        ):
            if value != baseline:
                print(f"    {name:11s} {baseline}->{value}")
    for family in (
        "single coefficient-5:",
        "single product-5:",
        "single sum-5:",
        "sum65 plus",
    ):
        entries = [
            entry
            for entry in gated
            if entry[3].startswith(family)
        ]
        print(
            f"h162 gated family {family!r}: "
            f"{len(entries)} variants"
        )
        for mode, c1, outputs, label, _ in entries[:40]:
            print(
                f"  h161={(mode, outputs, c1)} {label}"
            )


if __name__ == "__main__":
    main()
