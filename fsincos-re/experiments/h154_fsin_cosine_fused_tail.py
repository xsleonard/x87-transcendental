#!/usr/bin/env python3
"""Test fixed-grid and fused forms of FSIN's internal cosine tail.

The P5 multiplier exposes an unrounded normalized carrier, while the current
equivalent graph separately rounds ``q*a2`` before adding one.  This pass
tests two concrete alternatives:

* retain the negative product on an absolute binary grid anchored to 1.0,
  then add one exactly;
* add the exact product to 1.0 first, then materialize the near-one result.

Candidates cover 60..85 retained/fraction bits and the four established
equivalent rounding modes.  Every survivor must be componentwise no worse
on old train/heldout, h147, h148, and all six h151 targeted subsets.
"""

from __future__ import annotations

import dataclasses

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h121_fsin_internal_cosine as h121
import h126_fsin_raw_carrier_search as h126
import h146_fsin_cosine_boolean_search as h146
import h147_fsin_cosine_boolean_discriminator as h147
import h148_fsin_cosine_boolean_crossvalidate as h148
import h151_fsin_cosine_tail_discriminator as h151
import h153_fsin_cosine_p5_tail_round30 as h153


Metric = h146.Metric


@dataclasses.dataclass(frozen=True)
class Candidate:
    topology: str
    bits: int
    mode: str

    def short(self) -> str:
        return f"{self.topology} {self.bits}{self.mode}"


def candidates() -> tuple[Candidate, ...]:
    return tuple(
        Candidate(topology, bits, mode)
        for topology in ("tail-fixed", "fused-result")
        for bits in range(60, 86)
        for mode in ("rn", "chop", "odd", "away")
    )


def hidden(
    point: h121.Point,
    prepared: h153.State,
    candidate: Candidate | None,
) -> h58.FP:
    value, square = prepared
    if candidate is None:
        return h153.hidden(point, prepared, None)
    exact_tail = h58.mul_exact(value, square)
    if candidate.topology == "tail-fixed":
        tail = h126.grid_quantize(
            exact_tail, -candidate.bits, candidate.mode
        )
        result = h58.add_exact(h58.ONE, tail)
    elif candidate.topology == "fused-result":
        result = h110.quantize(
            h58.add_exact(h58.ONE, exact_tail),
            h110.Quant(candidate.bits, candidate.mode),
        )
    else:
        raise ValueError(candidate.topology)
    return h58.neg(result) if point.negate else result


def point_metric(
    point: h121.Point,
    prepared: h153.State,
    candidate: Candidate | None,
) -> Metric:
    return h146.metric(
        point, hidden(point, prepared, candidate)
    )


def score(
    dataset: h153.Dataset, candidate: Candidate | None
) -> Metric:
    result: Metric = (0, 0, 0)
    for point, prepared in zip(
        dataset.points, dataset.states
    ):
        result = h146.add(
            result,
            point_metric(point, prepared, candidate),
        )
    return result


def no_worse(value: Metric, baseline: Metric) -> bool:
    return all(
        left <= right
        for left, right in zip(value, baseline)
    )


def load_datasets() -> list[h153.Dataset]:
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
        h153.make_dataset(
            "old-train",
            [point for point in old if h121.is_train(point)],
        ),
        h153.make_dataset(
            "old-heldout",
            [point for point in old if not h121.is_train(point)],
        ),
        h153.make_dataset("h147", fresh147),
        h153.make_dataset("h148", fresh148),
    ]
    for selector in h151.CANDIDATES:
        selected = [
            point
            for point, line in zip(fresh151, metadata)
            if selector.name in line.split()[-1].split(",")
        ]
        result.append(
            h153.make_dataset(selector.name, selected)
        )
    return result


def main() -> None:
    datasets = load_datasets()
    for dataset in datasets:
        print(
            f"h154 baseline {dataset.name:20s} "
            f"n={len(dataset.points):5d} {dataset.baseline}"
        )
    search = [
        h153.sample(datasets[0], 1000),
        h153.sample(datasets[1], 1000),
        *datasets[2:],
    ]
    ranked = []
    for candidate in candidates():
        scores = tuple(
            score(dataset, candidate) for dataset in search
        )
        if not all(
            no_worse(value, dataset.baseline)
            for value, dataset in zip(scores, search)
        ):
            continue
        total = tuple(
            sum(value[index] for value in scores)
            for index in range(3)
        )
        ranked.append(
            (
                total[0],
                total[2],
                total[1],
                candidate.short(),
                candidate,
            )
        )
    ranked.sort()
    print(
        f"h154: {len(ranked)}/{len(candidates())} candidates "
        "survive all search gates"
    )
    validated = []
    for entry in ranked:
        candidate = entry[-1]
        scores = tuple(
            score(dataset, candidate) for dataset in datasets
        )
        if all(
            no_worse(value, dataset.baseline)
            for value, dataset in zip(scores, datasets)
        ):
            validated.append((*entry[:-1], candidate, scores))
    print(
        f"h154: {len(validated)} fixed/fused candidates "
        "survive all complete gates"
    )
    for entry in validated[:30]:
        _, _, _, label, _, scores = entry
        print(f"  {label}")
        for dataset, value in zip(datasets, scores):
            if value != dataset.baseline:
                print(
                    f"    {dataset.name:20s} "
                    f"{dataset.baseline}->{value}"
                )


if __name__ == "__main__":
    main()
