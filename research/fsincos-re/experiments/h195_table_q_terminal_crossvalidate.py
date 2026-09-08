#!/usr/bin/env python3
"""Cross-validate h194's Round-35 terminal-Q survivors.

h194 finds three complete-sweep single-site improvements after the terminal-P
schedule is fixed: shared-Q coefficient chop65/odd65 and common terminal-Q
sum RN65.  This pass tests those profiles and their same-stage combinations
on complete dense/sweep train/held partitions plus the independent h183,
h185, and h189 two-lane hardware captures.

Candidates remain hypotheses unless every gate is componentwise no worse.
Equivalent old-data profiles are kept distinct so a new hardware-blind
separator can target the unresolved materialization mode if needed.
"""

from __future__ import annotations

import hashlib

import h110_fsin_standalone as h110
import h131_fsin_table_c1_search as h131
import h170_fsin_table_correction_search as h170
import h173_fsin_table_fadd_topology as h173
import h183_table_joint_product_discriminator as h183
import h184_table_lookup_firc_routes as h184
import h185_table_lookup_firc_discriminator as h185
import h188_table_stage_local_pairs as h188
import h189_table_stage_local_discriminator as h189
import h194_table_round35_counterfactuals as h194


Metric = h173.Metric
JointMetric = tuple[Metric, Metric]
ROOT = h189.ROOT
H183_CAPTURE = ROOT / "capture-kit-captures" / "skylake-fsin-h183"
H185_CAPTURE = ROOT / "capture-kit-captures" / "skylake-fsin-h185"
H189_CAPTURE = ROOT / "capture-kit-captures" / "skylake-fsin-h189"

QC65C = h194.Candidate(
    "q-shared.coefficient-6", h110.Quant(65, "chop")
)
QC65O = h194.Candidate(
    "q-shared.coefficient-6", h110.Quant(65, "odd")
)
QS65R = h194.Candidate("q.sum-5", h110.Quant(65, "rn"))
CANDIDATES = (
    h194.CURRENT,
    QC65C,
    QC65O,
    QS65R,
    h194.Candidate(
        QC65C.site,
        QC65C.quant,
        ((QS65R.site, QS65R.quant),),
    ),
    h194.Candidate(
        QC65O.site,
        QC65O.quant,
        ((QS65R.site, QS65R.quant),),
    ),
)


def name(candidate: h194.Candidate) -> str:
    return "current" if candidate == h194.CURRENT else candidate.short()


def add(left: JointMetric, right: JointMetric) -> JointMetric:
    return tuple(
        h170.add(old, new) for old, new in zip(left, right)
    )  # type: ignore[return-value]


def score(
    points: list[h188.Point], candidate: h194.Candidate
) -> JointMetric:
    result: JointMetric = ((0, 0, 0), (0, 0, 0))
    for point in points:
        result = add(result, h194.point_metric(point, candidate))
    return result


def no_worse(value: JointMetric, baseline: JointMetric) -> bool:
    return all(
        h173.no_worse(new, old)
        for new, old in zip(value, baseline)
    )


def profile_digest(
    datasets: list[tuple[str, list[h188.Point]]],
    candidate: h194.Candidate,
) -> str:
    digest = hashlib.sha256()
    for dataset_name, points in datasets:
        digest.update(dataset_name.encode("ascii"))
        for point in points:
            value = h194.point_metric(point, candidate)
            digest.update(bytes((*value[0], *value[1])))
    return digest.hexdigest()[:16]


def complete_partitions() -> list[tuple[str, list[h188.Point]]]:
    result = []
    for dataset_name in ("dense", "sweep"):
        points = [
            h188.prepare(point)
            for point in h184.dataset(dataset_name)
            if point.observed.family == "wide"
        ]
        for split in ("train", "held"):
            result.append(
                (
                    f"{dataset_name}-{split}",
                    [
                        point
                        for point in points
                        if h131.is_train(point.joint.observed)
                        == (split == "train")
                    ],
                )
            )
    return result


def fresh_partitions() -> list[tuple[str, list[h188.Point]]]:
    h183_points = [
        h188.prepare(point)
        for point in h183.load_capture(
            h183.DEFAULT_OUTPUT, H183_CAPTURE
        )
    ]
    h185_points = [
        h188.prepare(point.joint)
        for point in h185.load_capture(
            h185.DEFAULT_OUTPUT, H185_CAPTURE
        )
        if point.joint.observed.family == "wide"
    ]
    h189_points = h189.load_capture(
        h189.DEFAULT_OUTPUT, H189_CAPTURE
    )
    return [
        ("fresh-h183", h183_points),
        ("fresh-h185", h185_points),
        ("fresh-h189", h189_points),
    ]


def main() -> None:
    datasets = complete_partitions() + fresh_partitions()
    baselines = [
        score(points, h194.CURRENT) for _, points in datasets
    ]
    print(
        "h195 Round-35 terminal-Q cross-validation: "
        f"datasets={sum(len(points) for _, points in datasets)}"
    )
    for (dataset_name, points), baseline in zip(datasets, baselines):
        print(
            f"  baseline {dataset_name:11s} n={len(points):6d} "
            f"sine={baseline[0]} cosine={baseline[1]}"
        )

    survivors = []
    for candidate in CANDIDATES:
        values = [
            score(points, candidate) for _, points in datasets
        ]
        passed = all(
            no_worse(value, baseline)
            for value, baseline in zip(values, baselines)
        )
        changed = any(
            value != baseline
            for value, baseline in zip(values, baselines)
        )
        status = (
            "CURRENT"
            if candidate == h194.CURRENT
            else "PASS"
            if passed and changed
            else "IDENTICAL"
            if passed
            else "FAIL"
        )
        digest = profile_digest(datasets, candidate)
        print(f"{status:9s} {name(candidate)} profile={digest}")
        for (dataset_name, _), baseline, value in zip(
            datasets, baselines, values
        ):
            if value != baseline:
                print(
                    f"    {dataset_name:11s} "
                    f"sine {baseline[0]}->{value[0]} "
                    f"cosine {baseline[1]}->{value[1]}"
                )
        if passed and changed:
            survivors.append(candidate)
    print(f"h195 complete survivors: {len(survivors)}")


if __name__ == "__main__":
    main()
