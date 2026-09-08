#!/usr/bin/env python3
"""Search adjacent Horner sum-carrier/product-consumer schedules.

h191-h198 exclude every same-stage coefficient/product/sum pair.  A distinct
physical pairing remains: the retained sum at stage k is the multiplicand
consumed by product k+1.  This pass changes exactly those two adjacent edges
for one requested P/Q boundary under the exact Round-35 model.

Each boundary tests 36 sum materializations times 37 product choices
(64..72 RN/chop/away/odd, with exact additionally allowed for the product).
The deterministic sample, all-residual, profile grouping, and complete
joint-lane gates match the stage-local searches.
"""

from __future__ import annotations

import argparse
import collections
import hashlib

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h131_fsin_table_c1_search as h131
import h170_fsin_table_correction_search as h170
import h173_fsin_table_fadd_topology as h173
import h184_table_lookup_firc_routes as h184
import h188_table_stage_local_pairs as h188
import h194_table_round35_counterfactuals as h194


Metric = h173.Metric
JointMetric = tuple[Metric, Metric]


def candidate(
    chain: str,
    stage: int,
    sum_quant: h110.Quant,
    product_quant: h110.Quant,
) -> h194.Candidate:
    return h194.Candidate(
        f"{chain}.sum-{stage}",
        sum_quant,
        ((f"{chain}.product-{stage + 1}", product_quant),),
    )


def candidates(chain: str, stage: int) -> tuple[h194.Candidate, ...]:
    sums = tuple(
        h110.Quant(bits, mode)
        for bits in range(64, 73)
        for mode in ("rn", "chop", "away", "odd")
    )
    products = (
        h110.EXACT,
        *(
            h110.Quant(bits, mode)
            for bits in range(64, 73)
            for mode in ("rn", "chop", "away", "odd")
        ),
    )
    return tuple(
        candidate(chain, stage, sum_quant, product_quant)
        for sum_quant in sums
        for product_quant in products
    )


def add(left: JointMetric, right: JointMetric) -> JointMetric:
    return tuple(
        h170.add(old, new) for old, new in zip(left, right)
    )  # type: ignore[return-value]


def score_signature(
    datasets: list[tuple[str, list[h188.Point]]],
    value_candidate: h194.Candidate,
) -> tuple[list[JointMetric], bytes]:
    digest = hashlib.sha256()
    results = []
    for name, points in datasets:
        digest.update(name.encode("ascii"))
        result: JointMetric = ((0, 0, 0), (0, 0, 0))
        for point in points:
            value = h194.point_metric(point, value_candidate)
            digest.update(bytes((*value[0], *value[1])))
            result = add(result, value)
        results.append(result)
    return results, digest.digest()


def objective(values: list[JointMetric]) -> tuple[int, int, int]:
    return tuple(
        sum(metric[index] for value in values for metric in value)
        for index in (0, 2, 1)
    )


def sample(points: list[h188.Point], count: int) -> list[h188.Point]:
    constrained = []
    controls = []
    for point in points:
        target = (
            constrained
            if h194.point_metric(point, h194.CURRENT)
            != ((0, 0, 0), (0, 0, 0))
            else controls
        )
        target.append(point)

    def key(point: h188.Point) -> int:
        observed = point.joint.observed
        return (
            observed.point.raw.sig
            ^ (observed.point.raw.sig >> 19)
            ^ (observed.point.raw.sig >> 43)
            ^ observed.index
            ^ observed.signed_n
        )

    constrained.sort(key=key)
    controls.sort(key=key)
    selected = constrained[: count // 2]
    selected.extend(controls[: count - len(selected)])
    if len(selected) < count:
        selected.extend(constrained[len(selected) : count])
    return selected


def constraint_gate(
    points: list[h188.Point], control_count: int
) -> list[h188.Point]:
    constrained = []
    controls = []
    for point in points:
        target = (
            constrained
            if h194.point_metric(point, h194.CURRENT)
            != ((0, 0, 0), (0, 0, 0))
            else controls
        )
        target.append(point)
    controls.sort(
        key=lambda point: (
            point.joint.observed.point.raw.sig
            ^ (point.joint.observed.point.raw.sig >> 31)
            ^ point.joint.observed.index
        )
    )
    return constrained + controls[:control_count]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chain", choices=("p", "q"), required=True)
    parser.add_argument("--stage", type=int, choices=(1, 2, 3, 4), required=True)
    args = parser.parse_args()
    raw = {
        name: [
            h188.prepare(point)
            for point in h184.dataset(name)
            if point.observed.family == "wide"
        ]
        for name in ("dense", "sweep")
    }
    partitions = []
    for name, points in raw.items():
        for split in ("train", "held"):
            partitions.append(
                (
                    f"{name}-{split}",
                    [
                        point
                        for point in points
                        if h131.is_train(point.joint.observed)
                        == (split == "train")
                    ],
                )
            )
    samples = [
        (name, sample(points, 150)) for name, points in partitions
    ]
    baseline_values, baseline_signature = score_signature(
        samples, h194.CURRENT
    )
    complete_baselines = [
        score_signature([(name, points)], h194.CURRENT)[0][0]
        for name, points in partitions
    ]
    values_to_test = candidates(args.chain, args.stage)
    print(
        f"h199 adjacent carrier: chain={args.chain.upper()} "
        f"boundary={args.stage}->{args.stage + 1} "
        f"candidates={len(values_to_test)}"
    )
    for (name, points), baseline in zip(partitions, complete_baselines):
        print(
            f"  baseline {name:11s} n={len(points):6d} "
            f"sine={baseline[0]} cosine={baseline[1]}"
        )

    sample_survivors = []
    for value_candidate in values_to_test:
        values, signature = score_signature(samples, value_candidate)
        if (
            signature == baseline_signature
            or not all(
                h194.no_worse(value, baseline)
                for value, baseline in zip(values, baseline_values)
            )
        ):
            continue
        sample_survivors.append(
            (*objective(values), value_candidate.short(), value_candidate)
        )
    sample_survivors.sort()
    print(
        f"h199 sample gate: tested={len(values_to_test)} "
        f"survivors={len(sample_survivors)}"
    )
    for item in sample_survivors[:12]:
        print(
            f"  modes/c1/inputs={item[0]}/{item[1]}/{item[2]} "
            f"{item[4].short()}"
        )
    if not sample_survivors:
        print("h199 all-residual gate: 0 survivors")
        print("h199 complete joint-lane gate: 0 survivors")
        return

    secondary = [
        (name, constraint_gate(points, 250))
        for name, points in partitions
    ]
    secondary_baselines = [
        score_signature([(name, points)], h194.CURRENT)[0][0]
        for name, points in secondary
    ]
    classes: dict[bytes, list[tuple]] = collections.defaultdict(list)
    for item in sample_survivors:
        value_candidate = item[4]
        values, signature = score_signature(secondary, value_candidate)
        if all(
            h194.no_worse(value, baseline)
            for value, baseline in zip(values, secondary_baselines)
        ) and any(
            value != baseline
            for value, baseline in zip(values, secondary_baselines)
        ):
            classes[signature].append(
                (*objective(values), value_candidate.short(), value_candidate)
            )
    representatives = sorted(min(items) for items in classes.values())
    print(
        f"h199 all-residual gate: "
        f"{sum(len(items) for items in classes.values())} survivors "
        f"in {len(representatives)} profile classes"
    )

    survivors = []
    for item in representatives:
        value_candidate = item[4]
        values = [
            score_signature([(name, points)], value_candidate)[0][0]
            for name, points in partitions
        ]
        if all(
            h194.no_worse(value, baseline)
            for value, baseline in zip(values, complete_baselines)
        ) and any(
            value != baseline
            for value, baseline in zip(values, complete_baselines)
        ):
            survivors.append((value_candidate, values))
    print(f"h199 complete joint-lane gate: {len(survivors)} survivors")
    for value_candidate, values in survivors:
        print(f"  {value_candidate.short()}")
        for (name, _), baseline, value in zip(
            partitions, complete_baselines, values
        ):
            if value != baseline:
                print(f"    {name:11s} {baseline}->{value}")


if __name__ == "__main__":
    main()
