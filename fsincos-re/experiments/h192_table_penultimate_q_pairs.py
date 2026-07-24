#!/usr/bin/env python3
"""Search latent two-edge schedules at the penultimate wide-Q stage.

This is the Q-chain companion to h191.  Round 35's terminal P route remains
frozen.  The candidate penultimate Q stage is shared, while its terminal
coefficient follows the established instruction split: away64 for standalone
FSIN's internal Q producer and native RN67 for paired FSINCOS.
"""

from __future__ import annotations

import collections
import dataclasses
import hashlib

import h58_constraint_search as h58
import h79_table_state_bias as h79
import h110_fsin_standalone as h110
import h131_fsin_table_c1_search as h131
import h134_fsin_table_per_edge_search as h134
import h136_tang_reconstruction_search as h136
import h170_fsin_table_correction_search as h170
import h182_table_joint_terminal_edges as h182
import h184_table_lookup_firc_routes as h184
import h188_table_stage_local_pairs as h188
import h189_table_stage_local_discriminator as h189
import h191_table_penultimate_p_pairs as h191


Metric = h191.Metric
Override = h191.Override
CURRENT = h191.CURRENT
STAGE = h191.STAGE
RN67 = h110.Quant(67, "rn")
AWAY64 = h110.Quant(64, "away")


@dataclasses.dataclass(frozen=True)
class Point:
    joint: h182.Point
    square: h58.FP
    p_round35: h58.FP
    q_prefix: h58.FP
    q_standalone: h58.FP
    q_shared: h58.FP


def q_parts(
    square: h58.FP,
    prefix: h58.FP,
    override: Override,
) -> tuple[h58.FP, h58.FP]:
    schedule = h134.CURRENT
    coefficient = override.coefficient or schedule.q_coefficients[STAGE]
    product = override.product or schedule.q_products[STAGE - 1]
    total = override.sum or schedule.q_sums[STAGE - 1]
    value = h188.terminal(
        h58.C6[: STAGE + 1],
        square,
        prefix,
        coefficient,
        product,
        total,
    )
    for stage in range(STAGE + 1, len(h58.C6) - 1):
        value = h188.terminal(
            h58.C6[: stage + 1],
            square,
            value,
            schedule.q_coefficients[stage],
            schedule.q_products[stage - 1],
            schedule.q_sums[stage - 1],
        )
    standalone = h188.terminal(
        h58.C6,
        square,
        value,
        AWAY64,
        schedule.q_products[-1],
        schedule.q_sums[-1],
    )
    shared = h188.terminal(
        h58.C6,
        square,
        value,
        RN67,
        schedule.q_products[-1],
        schedule.q_sums[-1],
    )
    return standalone, shared


def prepare(point: h182.Point) -> Point:
    base = h188.prepare(point)
    schedule = h134.CURRENT
    prefix = h134.horner(
        h58.C6[:STAGE],
        base.square,
        schedule.q_coefficients[:STAGE],
        schedule.q_products[: STAGE - 1],
        schedule.q_sums[: STAGE - 1],
    )
    standalone, shared = q_parts(base.square, prefix, CURRENT)
    expected_shared = h134.horner(
        h58.C6,
        base.square,
        schedule.q_coefficients,
        schedule.q_products,
        schedule.q_sums,
    )
    if standalone != base.q_current or shared != expected_shared:
        raise AssertionError(
            f"stage Q{STAGE} current path differs from Round 35"
        )
    p_round35 = h188.producer(base, h189.CANDIDATES[1])
    return Point(
        point,
        base.square,
        p_round35,
        prefix,
        standalone,
        shared,
    )


def state(point: Point, q: h58.FP) -> h136.State:
    observed = point.joint.observed
    m = h58.fmul(point.p_round35, point.square, 64, "rn")
    correction = h58.fmul(m, observed.point.a, 64, "rn")
    sine_a = h58.fadd(observed.point.a, correction, 64, "rn")
    sine_a = h79.bias_toward_zero(sine_a, 5)
    return h136.State(
        observed.point.a,
        h58.add_exact(sine_a, h58.neg(observed.point.a)),
        h58.fmul(q, point.square, 64, "rn"),
    )


def values(
    point: Point, override: Override
) -> tuple[h58.FP, h58.FP]:
    if override.changed_fields():
        q_standalone, q_shared = q_parts(
            point.square, point.q_prefix, override
        )
    else:
        q_standalone, q_shared = point.q_standalone, point.q_shared
    standalone = h184.values(
        h184.Point(
            point.joint, state(point, q_standalone), None
        ),
        h188.ROUND34,
    )[0]
    paired = h184.values(
        h184.Point(point.joint, state(point, q_shared), None),
        h188.ROUND34,
    )[1]
    return standalone, paired


def point_score(
    point: Point, override: Override
) -> tuple[Metric, Metric]:
    sine, cosine = values(point, override)
    return (
        h170.point_metric(point.joint.observed, sine),
        h182.point_metric(
            point.joint.cosine_outputs,
            point.joint.cosine_c1,
            cosine,
        ),
    )


def score_signature(datasets, override: Override):
    digest = hashlib.sha256()
    results = []
    for name, points in datasets:
        digest.update(name.encode("ascii"))
        result = ((0, 0, 0), (0, 0, 0))
        for point in points:
            value = point_score(point, override)
            digest.update(bytes((*value[0], *value[1])))
            result = tuple(
                h170.add(old, new)
                for old, new in zip(result, value)
            )
        results.append(result)
    return results, digest.digest()


def sample(points: list[Point], count: int) -> list[Point]:
    constrained = []
    controls = []
    for point in points:
        target = (
            constrained
            if point_score(point, CURRENT)
            != ((0, 0, 0), (0, 0, 0))
            else controls
        )
        target.append(point)

    def key(point: Point) -> int:
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
    points: list[Point], control_count: int
) -> list[Point]:
    constrained = []
    controls = []
    for point in points:
        target = (
            constrained
            if point_score(point, CURRENT)
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
    raw = {
        name: [
            point
            for point in h184.dataset(name)
            if point.observed.family == "wide"
        ]
        for name in ("dense", "sweep")
    }
    partitions = []
    for name, points in raw.items():
        for split, predicate in (
            ("train", h131.is_train),
            ("held", lambda point: not h131.is_train(point)),
        ):
            partitions.append(
                (
                    f"{name}-{split}",
                    [
                        prepare(point)
                        for point in points
                        if predicate(point.observed)
                    ],
                )
            )
    samples = [
        (name, sample(points, 150)) for name, points in partitions
    ]
    baseline_values, baseline_signature = score_signature(samples, CURRENT)
    complete_baselines = [
        score_signature([(name, points)], CURRENT)[0][0]
        for name, points in partitions
    ]
    print(
        f"h192 loaded dense={len(raw['dense'])} "
        f"sweep={len(raw['sweep'])} stage=Q{STAGE}"
    )
    for (name, points), value in zip(partitions, complete_baselines):
        print(
            f"  baseline {name:11s} n={len(points):6d} "
            f"sine={value[0]} cosine={value[1]}"
        )

    candidates = h191.overrides()
    sample_survivors = []
    singleton_signatures = {}
    for override in candidates:
        values_by_sample, signature = score_signature(samples, override)
        if (
            signature == baseline_signature
            or not h191.no_worse(values_by_sample, baseline_values)
        ):
            continue
        latent = 0
        for field in override.changed_fields():
            individual = h191.singleton(override, field)
            individual_signature = singleton_signatures.get(individual)
            if individual_signature is None:
                individual_signature = score_signature(
                    samples, individual
                )[1]
                singleton_signatures[individual] = individual_signature
            latent += individual_signature == baseline_signature
        sample_survivors.append(
            (
                -latent,
                *h191.objective(values_by_sample),
                override.short().replace("p", "q"),
                override,
            )
        )
    sample_survivors.sort()
    print(
        f"h192 sample gate: tested={len(candidates)} "
        f"survivors={len(sample_survivors)}"
    )
    for item in sample_survivors[:12]:
        print(
            f"  latent={-item[0]} modes/c1/inputs="
            f"{item[1]}/{item[2]}/{item[3]} {item[4]}"
        )

    secondary = [
        (name, constraint_gate(points, 250))
        for name, points in partitions
    ]
    secondary_baselines = [
        score_signature([(name, points)], CURRENT)[0][0]
        for name, points in secondary
    ]
    secondary_classes = collections.defaultdict(list)
    for item in sample_survivors:
        override = item[5]
        values_by_gate, signature = score_signature(secondary, override)
        if (
            h191.no_worse(values_by_gate, secondary_baselines)
            and any(
                value != old
                for value, old in zip(values_by_gate, secondary_baselines)
            )
        ):
            secondary_classes[signature].append(
                (
                    *h191.objective(values_by_gate),
                    item[4],
                    override,
                )
            )
    representatives = [
        min(items) for items in secondary_classes.values()
    ]
    representatives.sort()
    print(
        f"h192 all-residual gate: "
        f"{sum(len(items) for items in secondary_classes.values())} "
        f"survivors in {len(representatives)} profile classes; "
        f"n={sum(len(points) for _, points in secondary)}"
    )

    survivors = []
    for item in representatives:
        override = item[4]
        values_by_partition = [
            score_signature([(name, points)], override)[0][0]
            for name, points in partitions
        ]
        if (
            h191.no_worse(values_by_partition, complete_baselines)
            and any(
                value != old
                for value, old in zip(
                    values_by_partition, complete_baselines
                )
            )
        ):
            class_size = next(
                len(items)
                for items in secondary_classes.values()
                if item in items
            )
            survivors.append((item[3], override, values_by_partition, class_size))
    print(f"h192 complete joint-lane gate: {len(survivors)} survivors")
    for label, override, values_by_partition, class_size in survivors:
        print(f"  {label} class={class_size}")
        for (name, _), old, value in zip(
            partitions, complete_baselines, values_by_partition
        ):
            if value != old:
                print(f"    {name:11s} {old}->{value}")


if __name__ == "__main__":
    main()
