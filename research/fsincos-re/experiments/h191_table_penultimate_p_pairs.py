#!/usr/bin/env python3
"""Search latent two-edge schedules at the penultimate wide-P stage.

Round 35 establishes away64 materialization of the terminal P coefficient
followed by a chopped 65-bit terminal sum.  This pass freezes that route and
changes exactly two of coefficient, product, and sum materialization at the
preceding P Horner stage.  Standalone FSIN retains h135's path-aware Q
producer while paired FSINCOS retains the shared Q producer, matching h190's
instruction-specific C model.

Widths 64..72 and RN/chop/away/odd are searched; the product may also remain
exact.  Candidates must be componentwise non-regressing on joint sine/cosine
value, input, and C1 metrics.  Sample survivors are regrouped on all current
residuals plus independent controls before complete partition validation.
"""

from __future__ import annotations

import collections
import dataclasses
import hashlib
import itertools

import h58_constraint_search as h58
import h79_table_state_bias as h79
import h110_fsin_standalone as h110
import h131_fsin_table_c1_search as h131
import h134_fsin_table_per_edge_search as h134
import h136_tang_reconstruction_search as h136
import h170_fsin_table_correction_search as h170
import h173_fsin_table_fadd_topology as h173
import h182_table_joint_terminal_edges as h182
import h184_table_lookup_firc_routes as h184
import h188_table_stage_local_pairs as h188


Metric = h173.Metric
FIELDS = ("coefficient", "product", "sum")
STAGE = 4
ROUND35_COEFFICIENT = h110.Quant(64, "away")
ROUND35_SUM = h110.Quant(65, "chop")


@dataclasses.dataclass(frozen=True)
class Override:
    coefficient: h110.Quant | None = None
    product: h110.Quant | None = None
    sum: h110.Quant | None = None

    def short(self) -> str:
        values = []
        for field in FIELDS:
            quant = getattr(self, field)
            if quant is not None:
                values.append(f"p{field[0]}{STAGE}={quant.short()}")
        return " ".join(values) if values else "current"

    def changed_fields(self) -> tuple[str, ...]:
        return tuple(
            field for field in FIELDS if getattr(self, field) is not None
        )


CURRENT = Override()


@dataclasses.dataclass(frozen=True)
class Point:
    joint: h182.Point
    square: h58.FP
    p_prefix: h58.FP
    p_current: h58.FP
    q_standalone: h58.FP
    q_shared: h58.FP


def producer_parts(
    square: h58.FP,
    prefix: h58.FP,
    schedule: h134.Schedule,
    override: Override,
) -> h58.FP:
    coefficient = override.coefficient or schedule.p_coefficients[STAGE]
    product = override.product or schedule.p_products[STAGE - 1]
    total = override.sum or schedule.p_sums[STAGE - 1]
    value = h188.terminal(
        h58.S6[: STAGE + 1],
        square,
        prefix,
        coefficient,
        product,
        total,
    )
    for stage in range(STAGE + 1, len(h58.S6) - 1):
        value = h188.terminal(
            h58.S6[: stage + 1],
            square,
            value,
            schedule.p_coefficients[stage],
            schedule.p_products[stage - 1],
            schedule.p_sums[stage - 1],
        )
    return h188.terminal(
        h58.S6,
        square,
        value,
        ROUND35_COEFFICIENT,
        schedule.p_products[-1],
        ROUND35_SUM,
    )


def prepare(point: h182.Point) -> Point:
    base = h188.prepare(point)
    schedule = base.base
    prefix = h134.horner(
        h58.S6[:STAGE],
        base.square,
        schedule.p_coefficients[:STAGE],
        schedule.p_products[: STAGE - 1],
        schedule.p_sums[: STAGE - 1],
    )
    p_current = producer_parts(base.square, prefix, schedule, CURRENT)
    expected_p = h188.producer(
        base,
        h188.Override(
            "p",
            coefficient=ROUND35_COEFFICIENT,
            sum=ROUND35_SUM,
        ),
    )
    if p_current != expected_p:
        raise AssertionError(
            f"stage P{STAGE} current path differs from Round 35"
        )
    shared = h134.CURRENT
    q_shared = h134.horner(
        h58.C6,
        base.square,
        shared.q_coefficients,
        shared.q_products,
        shared.q_sums,
    )
    return Point(
        point,
        base.square,
        prefix,
        p_current,
        base.q_current,
        q_shared,
    )


def p_value(point: Point, override: Override) -> h58.FP:
    if not override.changed_fields():
        return point.p_current
    schedule = h134.CURRENT
    return producer_parts(
        point.square, point.p_prefix, schedule, override
    )


def state(point: Point, p: h58.FP, q: h58.FP) -> h136.State:
    observed = point.joint.observed
    m = h58.fmul(p, point.square, 64, "rn")
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
    p = p_value(point, override)
    standalone = h184.values(
        h184.Point(
            point.joint,
            state(point, p, point.q_standalone),
            None,
        ),
        h188.ROUND34,
    )[0]
    paired = h184.values(
        h184.Point(
            point.joint,
            state(point, p, point.q_shared),
            None,
        ),
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


def score_signature(
    datasets: list[tuple[str, list[Point]]],
    override: Override,
) -> tuple[list[tuple[Metric, Metric]], bytes]:
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


def no_worse(values, baselines) -> bool:
    return all(
        all(
            h173.no_worse(new, old)
            for new, old in zip(value, baseline)
        )
        for value, baseline in zip(values, baselines)
    )


def objective(values) -> tuple[int, int, int]:
    return tuple(
        sum(metric[index] for value in values for metric in value)
        for index in (0, 2, 1)
    )


def quants(exact: bool) -> tuple[h110.Quant, ...]:
    values = tuple(
        h110.Quant(bits, mode)
        for bits in range(64, 73)
        for mode in ("rn", "chop", "away", "odd")
    )
    return ((h110.EXACT,) + values) if exact else values


def overrides() -> tuple[Override, ...]:
    options = {
        "coefficient": quants(False),
        "product": quants(True),
        "sum": quants(False),
    }
    result = []
    for left, right in itertools.combinations(FIELDS, 2):
        for left_quant in options[left]:
            for right_quant in options[right]:
                result.append(
                    Override(**{left: left_quant, right: right_quant})
                )
    return tuple(result)


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


def singleton(override: Override, field: str) -> Override:
    return Override(**{field: getattr(override, field)})


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
        f"h191 loaded dense={len(raw['dense'])} "
        f"sweep={len(raw['sweep'])} stage=P{STAGE}"
    )
    for (name, points), value in zip(partitions, complete_baselines):
        print(
            f"  baseline {name:11s} n={len(points):6d} "
            f"sine={value[0]} cosine={value[1]}"
        )

    candidates = overrides()
    sample_survivors = []
    singleton_signatures = {}
    for override in candidates:
        values_by_sample, signature = score_signature(samples, override)
        if (
            signature == baseline_signature
            or not no_worse(values_by_sample, baseline_values)
        ):
            continue
        latent = 0
        for field in override.changed_fields():
            individual = singleton(override, field)
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
                *objective(values_by_sample),
                override.short(),
                override,
            )
        )
    sample_survivors.sort()
    print(
        f"h191 sample gate: tested={len(candidates)} "
        f"survivors={len(sample_survivors)}"
    )
    for item in sample_survivors[:12]:
        print(
            f"  latent={-item[0]} modes/c1/inputs="
            f"{item[1]}/{item[2]}/{item[3]} {item[5].short()}"
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
            no_worse(values_by_gate, secondary_baselines)
            and any(
                value != old
                for value, old in zip(values_by_gate, secondary_baselines)
            )
        ):
            secondary_classes[signature].append(
                (*objective(values_by_gate), override.short(), override)
            )
    representatives = [
        min(items) for items in secondary_classes.values()
    ]
    representatives.sort()
    print(
        f"h191 all-residual gate: "
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
            no_worse(values_by_partition, complete_baselines)
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
            survivors.append((override, values_by_partition, class_size))
    print(f"h191 complete joint-lane gate: {len(survivors)} survivors")
    for override, values_by_partition, class_size in survivors:
        print(f"  {override.short()} class={class_size}")
        for (name, _), old, value in zip(
            partitions, complete_baselines, values_by_partition
        ):
            if value != old:
                print(f"    {name:11s} {old}->{value}")


if __name__ == "__main__":
    main()
