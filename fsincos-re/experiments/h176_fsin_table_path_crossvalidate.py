#!/usr/bin/env python3
"""Cross-validate h175's surviving table FADD path rules.

h175 independently validates narrow-cosine RN64, narrow-cosine odd67, and
cosine-lane chop69 nonlinear carriers.  This pass scores those mechanisms,
the wide-cosine restriction of chop69, and the two non-overlapping
narrow/wide compositions on every old and fresh gate, including each h175
target subset.
"""

from __future__ import annotations

import dataclasses

import h110_fsin_standalone as h110
import h131_fsin_table_c1_search as h131
import h135_fsin_table_terminal_discriminator as h135
import h140_p5_fmul_discriminator as h140
import h170_fsin_table_correction_search as h170
import h171_fsin_table_correction_discriminator as h171
import h173_fsin_table_fadd_topology as h173
import h175_fsin_table_path_discriminator as h175


Metric = h173.Metric
RN67 = h110.Quant(67, "rn")
RN64 = h110.Quant(64, "rn")
ODD67 = h110.Quant(67, "odd")
CHOP69 = h110.Quant(69, "chop")


@dataclasses.dataclass(frozen=True)
class Variant:
    name: str
    narrow_cosine: h110.Quant | None = None
    wide_cosine: h110.Quant | None = None


CURRENT = Variant("current")
VARIANTS = (
    Variant("narrow-cos-rn64", narrow_cosine=RN64),
    Variant("narrow-cos-odd67", narrow_cosine=ODD67),
    Variant(
        "all-cos-chop69",
        narrow_cosine=CHOP69,
        wide_cosine=CHOP69,
    ),
    Variant("wide-cos-chop69", wide_cosine=CHOP69),
    Variant(
        "narrow-rn64-wide-chop69",
        narrow_cosine=RN64,
        wide_cosine=CHOP69,
    ),
    Variant(
        "narrow-odd67-wide-chop69",
        narrow_cosine=ODD67,
        wide_cosine=CHOP69,
    ),
)


@dataclasses.dataclass
class Dataset:
    name: str
    points: list[h131.Observed]
    baseline: Metric


def schedule(
    point: h131.Observed, variant: Variant
) -> h173.Candidate:
    if not (point.signed_n & 1):
        return h173.CURRENT
    quant = (
        variant.wide_cosine
        if point.family == "wide"
        else variant.narrow_cosine
    )
    if quant is None:
        return h173.CURRENT
    return h173.Candidate("correction", quant, RN67)


def score(
    points: list[h131.Observed], variant: Variant
) -> Metric:
    result: Metric = (0, 0, 0)
    for point in points:
        terms = h173.make_terms(point)
        value = h173.hidden(terms, schedule(point, variant))
        result = h170.add(
            result, h170.point_metric(point, value)
        )
    return result


def make_dataset(
    name: str, points: list[h131.Observed]
) -> Dataset:
    return Dataset(name, points, score(points, CURRENT))


def datasets() -> list[Dataset]:
    dense = h131.load_dataset(
        "dense", h131.INPUTS / "dense_qn.txt"
    )
    sweep = h131.load_dataset(
        "sweep", h131.INPUTS / "sweep_inputs.txt"
    )
    result = []
    for name, points in (("dense", dense), ("sweep", sweep)):
        result.extend(
            (
                make_dataset(
                    f"{name}-train",
                    [point for point in points if h131.is_train(point)],
                ),
                make_dataset(
                    f"{name}-held",
                    [
                        point
                        for point in points
                        if not h131.is_train(point)
                    ],
                ),
            )
        )
    fresh135 = h135.load_capture(
        h135.DEFAULT_OUTPUT,
        h135.DEFAULT_METADATA,
        h135.ROOT
        / "capture-kit-captures"
        / "skylake-fsin-h135",
    )
    result.append(
        make_dataset(
            "h135",
            [
                point
                for points in fresh135.values()
                for point in points
            ],
        )
    )
    result.append(
        make_dataset(
            "h140",
            h140.load_capture(
                h140.DEFAULT_OUTPUT,
                h140.ROOT
                / "capture-kit-captures"
                / "skylake-fsin-h140",
            ),
        )
    )
    result.append(
        make_dataset(
            "h171",
            h171.load_capture(
                h171.DEFAULT_OUTPUT,
                h171.ROOT
                / "capture-kit-captures"
                / "skylake-fsin-h171",
            ),
        )
    )
    fresh175 = h175.load_capture(
        h175.DEFAULT_OUTPUT,
        h175.ROOT
        / "capture-kit-captures"
        / "skylake-fsin-h175",
    )
    metadata = h175.DEFAULT_METADATA.read_text().splitlines()
    result.append(make_dataset("h175-all", fresh175))
    for candidate in h175.CANDIDATES:
        result.append(
            make_dataset(
                f"h175-{candidate.name}",
                [
                    point
                    for point, line in zip(
                        fresh175, metadata
                    )
                    if any(
                        item.split(":", 1)[0]
                        == candidate.name
                        for item in line.split()[-1].split(",")
                    )
                ],
            )
        )
    return result


def main() -> None:
    values = datasets()
    for variant in VARIANTS:
        scores = [
            score(dataset.points, variant)
            for dataset in values
        ]
        passed = all(
            h173.no_worse(value, dataset.baseline)
            for value, dataset in zip(scores, values)
        )
        changed = any(
            value != dataset.baseline
            for value, dataset in zip(scores, values)
        )
        print(
            f"{'PASS' if passed and changed else 'FAIL'} "
            f"{variant.name}"
        )
        for dataset, value in zip(values, scores):
            if value != dataset.baseline:
                print(
                    f"  {dataset.name:43s} "
                    f"{dataset.baseline}->{value}"
                )


if __name__ == "__main__":
    main()
