#!/usr/bin/env python3
"""Search adjacent conditional operations after Round 33.

The remaining old internal-cosine states need corrections in both
directions, and h166 finds no clean Boolean partition by itself.  This pass
therefore tests an operation and selector together.  Candidate operations
are limited to product 5, sum 5, tail, and final-sum materializations over
the existing 64..72-bit grids.  Selectors are conjunctions of at most two
adjacent physical trace predicates.

Every rule must be componentwise no worse on both old halves and all seven
focused capture sets.  A survivor is still only a hypothesis until a new
hardware-blind discriminator validates it.
"""

from __future__ import annotations

import collections
import dataclasses
import itertools

import h110_fsin_standalone as h110
import h119_fcos_standalone as h119
import h121_fsin_internal_cosine as h121
import h146_fsin_cosine_boolean_search as h146
import h147_fsin_cosine_boolean_discriminator as h147
import h148_fsin_cosine_boolean_crossvalidate as h148
import h151_fsin_cosine_tail_discriminator as h151
import h157_fsin_cosine_two_predicate as h157
import h158_fsin_cosine_two_predicate_discriminator as h158
import h161_fsin_cosine_round32_composition as h161
import h162_fsin_cosine_round32_residual_search as h162
import h163_fsin_cosine_product_discriminator as h163
import h165_fsin_cosine_product_width_discriminator as h165


Metric = h146.Metric
P67_ODD = next(
    candidate
    for candidate in h163.CANDIDATES
    if candidate.name == "product5-67o"
)


@dataclasses.dataclass
class Dataset:
    name: str
    points: list[h121.Point]
    schedules: list[h119.Schedule]
    traces: list[dict[str, int]]
    metrics: list[Metric]
    baseline: Metric


@dataclasses.dataclass(frozen=True)
class Operation:
    coordinate: str
    quant: h110.Quant

    def short(self) -> str:
        return f"{self.coordinate}={self.quant.short()}"


def current_schedule(point: h121.Point) -> h119.Schedule:
    return h162.variant_schedule(point, P67_ODD.variant)


def make_dataset(
    name: str, points: list[h121.Point]
) -> Dataset:
    schedules = [current_schedule(point) for point in points]
    traces = [
        h146.trace(point, value_schedule)
        for point, value_schedule in zip(points, schedules)
    ]
    metrics = [
        h146.metric(
            point,
            h146.hidden_value(point, value_schedule),
        )
        for point, value_schedule in zip(points, schedules)
    ]
    baseline: Metric = (0, 0, 0)
    for value in metrics:
        baseline = h146.add(baseline, value)
    return Dataset(
        name, points, schedules, traces, metrics, baseline
    )


def datasets() -> list[Dataset]:
    root = h121.ROOT / "capture-kit-captures"
    old = h121.load_points()
    return [
        make_dataset(
            "old-train",
            [point for point in old if h121.is_train(point)],
        ),
        make_dataset(
            "old-heldout",
            [
                point
                for point in old
                if not h121.is_train(point)
            ],
        ),
        make_dataset(
            "h147",
            h147.load_capture(
                h147.DEFAULT_OUTPUT, root / "skylake-fsin-h147"
            ),
        ),
        make_dataset(
            "h148",
            h148.load_capture(
                h148.DEFAULT_OUTPUT, root / "skylake-fsin-h148"
            ),
        ),
        make_dataset(
            "h151",
            h151.load_capture(
                h151.DEFAULT_OUTPUT, root / "skylake-fsin-h151"
            ),
        ),
        make_dataset(
            "h158",
            h158.load_capture(
                h158.DEFAULT_OUTPUT, root / "skylake-fsin-h158"
            ),
        ),
        make_dataset(
            "h161",
            h161.load_capture(
                h161.DEFAULT_OUTPUT, root / "skylake-fsin-h161"
            ),
        ),
        make_dataset(
            "h163",
            h163.load_capture(
                h163.DEFAULT_OUTPUT, root / "skylake-fsin-h163"
            ),
        ),
        make_dataset(
            "h165",
            h165.load_capture(
                h165.DEFAULT_OUTPUT, root / "skylake-fsin-h165"
            ),
        ),
    ]


def operations() -> tuple[Operation, ...]:
    result = []
    for coordinate in ("product-5", "sum-5"):
        for quant in h110.quant_options():
            result.append(Operation(coordinate, quant))
    for coordinate in ("tail", "final-sum"):
        for quant in h110.quant_options(exact=True):
            result.append(Operation(coordinate, quant))
    return tuple(result)


def apply_operation(
    point: h121.Point,
    baseline: h119.Schedule,
    operation: Operation,
) -> h119.Schedule:
    if operation.coordinate == "product-5":
        candidate = dataclasses.replace(
            baseline,
            products=h110.replace_tuple(
                baseline.products, 4, operation.quant
            ),
        )
    elif operation.coordinate == "sum-5":
        candidate = dataclasses.replace(
            baseline,
            sums=h110.replace_tuple(
                baseline.sums, 4, operation.quant
            ),
        )
    elif operation.coordinate == "tail":
        return dataclasses.replace(
            baseline, tail=operation.quant
        )
    else:
        candidate = dataclasses.replace(
            baseline, final_sum=operation.quant
        )
    # Re-evaluate Round 31 after any upstream materialization changes.
    candidate = dataclasses.replace(
        candidate, tail=h110.Quant(72, "away")
    )
    features = h146.trace(point, candidate)
    return (
        dataclasses.replace(
            candidate, tail=h110.Quant(71, "chop")
        )
        if features["tail.lsb"] == 1
        else candidate
    )


def predicates(
    coordinate: str, features: dict[str, int]
) -> tuple[tuple[str, int], ...]:
    names = h157.relevant_features(coordinate, features)
    return tuple((name, features[name]) for name in names)


def no_worse(value: Metric, baseline: Metric) -> bool:
    return all(
        left <= right
        for left, right in zip(value, baseline)
    )


def main() -> None:
    values = datasets()
    for dataset in values:
        print(
            f"h167 baseline {dataset.name:11s} "
            f"n={len(dataset.points):5d} {dataset.baseline}"
        )
    survivors = []
    tested = 0
    for operation in operations():
        tested += 1
        deltas: dict[
            tuple[tuple[str, int], ...],
            list[Metric],
        ] = collections.defaultdict(
            lambda: [(0, 0, 0) for _ in values]
        )
        for dataset_index, dataset in enumerate(values):
            for point, baseline, features, old_metric in zip(
                dataset.points,
                dataset.schedules,
                dataset.traces,
                dataset.metrics,
            ):
                candidate = apply_operation(
                    point, baseline, operation
                )
                new_metric = h146.metric(
                    point,
                    h146.hidden_value(point, candidate),
                )
                delta: Metric = tuple(
                    new - old
                    for new, old in zip(
                        new_metric, old_metric
                    )
                )  # type: ignore[assignment]
                if delta == (0, 0, 0):
                    continue
                terms = predicates(
                    operation.coordinate, features
                )
                for count in (1, 2):
                    for rule in itertools.combinations(
                        terms, count
                    ):
                        deltas[rule][dataset_index] = h146.add(
                            deltas[rule][dataset_index], delta
                        )
        for rule, rule_deltas in deltas.items():
            scores = tuple(
                h146.add(dataset.baseline, delta)
                for dataset, delta in zip(
                    values, rule_deltas
                )
            )
            if not all(
                no_worse(value, dataset.baseline)
                for value, dataset in zip(scores, values)
            ):
                continue
            if not (
                scores[0] != values[0].baseline
                or scores[1] != values[1].baseline
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
            survivors.append(
                (
                    old[0],
                    old[2],
                    old[1],
                    fresh[0],
                    fresh[2],
                    fresh[1],
                    operation.short(),
                    rule,
                    scores,
                )
            )
    survivors.sort()
    print(
        f"h167: {len(survivors)} conditional rules survive "
        f"from {tested} adjacent operations"
    )
    for entry in survivors[:40]:
        *_, operation, rule, scores = entry
        label = " & ".join(
            f"{name}={value}" for name, value in rule
        )
        print(f"  {operation} if {label}")
        for dataset, score in zip(values, scores):
            if score != dataset.baseline:
                print(
                    f"    {dataset.name:11s} "
                    f"{dataset.baseline}->{score}"
                )


if __name__ == "__main__":
    main()
