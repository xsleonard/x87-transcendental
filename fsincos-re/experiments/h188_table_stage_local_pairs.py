#!/usr/bin/env python3
"""Search latent two-edge schedules at the terminal P/Q Horner stage.

h187 rejects one changed P coordinate paired with one changed Q coordinate,
but it cannot detect a same-stage schedule whose individual components are
architecturally silent.  This pass freezes Round 34 and changes two of the
three operations in the final Horner stage of one chain:

    materialize(coefficient), materialize(prefix*square), materialize(sum)

The other chain remains current.  Widths 64..72 and RN/chop/away/odd are
searched; the product may additionally remain exact.  Selection requires a
changed joint-lane profile with componentwise non-regression on deterministic
samples.  Surviving schedules are regrouped on all currently wrong inputs
plus independent controls, then one representative per exact profile is
checked on complete dense/sweep train/held partitions.
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
import h135_fsin_table_terminal_discriminator as h135
import h136_tang_reconstruction_search as h136
import h170_fsin_table_correction_search as h170
import h173_fsin_table_fadd_topology as h173
import h182_table_joint_terminal_edges as h182
import h184_table_lookup_firc_routes as h184


Metric = h173.Metric
ROUND34 = h184.Candidate(p_product="rn64")
FIELDS = ("coefficient", "product", "sum")


@dataclasses.dataclass(frozen=True)
class Override:
    chain: str
    coefficient: h110.Quant | None = None
    product: h110.Quant | None = None
    sum: h110.Quant | None = None

    def short(self) -> str:
        values = []
        for name in FIELDS:
            quant = getattr(self, name)
            if quant is not None:
                values.append(f"{self.chain}{name[0]}5={quant.short()}")
        return " ".join(values) if values else "current"

    def changed_fields(self) -> tuple[str, ...]:
        return tuple(
            name for name in FIELDS if getattr(self, name) is not None
        )


CURRENT_P = Override("p")
CURRENT_Q = Override("q")


@dataclasses.dataclass(frozen=True)
class Point:
    joint: h182.Point
    base: h134.Schedule
    square: h58.FP
    p_prefix: h58.FP
    q_prefix: h58.FP
    p_current: h58.FP
    q_current: h58.FP


def prefix(
    rows: tuple[int, ...],
    square: h58.FP,
    coefficients,
    products,
    sums,
) -> h58.FP:
    return h134.horner(
        rows[:-1],
        square,
        coefficients[:-1],
        products[:-1],
        sums[:-1],
    )


def terminal(
    rows: tuple[int, ...],
    square: h58.FP,
    value: h58.FP,
    coefficient_quant: h110.Quant,
    product_quant: h110.Quant,
    sum_quant: h110.Quant,
) -> h58.FP:
    product = h110.quantize(
        h58.mul_exact(value, square), product_quant
    )
    coefficient = h134.coefficient(
        rows[-1], coefficient_quant
    )
    return h110.quantize(
        h58.add_exact(product, coefficient), sum_quant
    )


def prepare(point: h182.Point) -> Point:
    observed = point.observed
    base = h135.path_candidate(observed)
    square = h58.fmul(
        observed.point.a, observed.point.a, 64, "rn"
    )
    p_prefix = prefix(
        h58.S6,
        square,
        base.p_coefficients,
        base.p_products,
        base.p_sums,
    )
    q_prefix = prefix(
        h58.C6,
        square,
        base.q_coefficients,
        base.q_products,
        base.q_sums,
    )
    p_current = terminal(
        h58.S6,
        square,
        p_prefix,
        base.p_coefficients[-1],
        base.p_products[-1],
        base.p_sums[-1],
    )
    q_current = terminal(
        h58.C6,
        square,
        q_prefix,
        base.q_coefficients[-1],
        base.q_products[-1],
        base.q_sums[-1],
    )
    return Point(
        point,
        base,
        square,
        p_prefix,
        q_prefix,
        p_current,
        q_current,
    )


def producer(point: Point, override: Override) -> h58.FP:
    chain = override.chain
    base = point.base
    if chain == "p":
        rows = h58.S6
        value = point.p_prefix
        current = point.p_current
    else:
        rows = h58.C6
        value = point.q_prefix
        current = point.q_current
    if not override.changed_fields():
        return current
    coefficient_quant = override.coefficient or getattr(
        base, f"{chain}_coefficients"
    )[-1]
    product_quant = override.product or getattr(
        base, f"{chain}_products"
    )[-1]
    sum_quant = override.sum or getattr(
        base, f"{chain}_sums"
    )[-1]
    return terminal(
        rows,
        point.square,
        value,
        coefficient_quant,
        product_quant,
        sum_quant,
    )


def values(
    point: Point, override: Override
) -> tuple[h58.FP, h58.FP]:
    observed = point.joint.observed
    p = (
        producer(point, override)
        if override.chain == "p"
        else point.p_current
    )
    q = (
        producer(point, override)
        if override.chain == "q"
        else point.q_current
    )
    m = h58.fmul(p, point.square, 64, "rn")
    correction = h58.fmul(
        m, observed.point.a, 64, "rn"
    )
    sine_a = h58.fadd(
        observed.point.a, correction, 64, "rn"
    )
    sine_a = h79.bias_toward_zero(sine_a, 5)
    state = h136.State(
        observed.point.a,
        h58.add_exact(sine_a, h58.neg(observed.point.a)),
        h58.fmul(q, point.square, 64, "rn"),
    )
    return h184.values(
        h184.Point(point.joint, state, None), ROUND34
    )


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


def overrides(chain: str) -> tuple[Override, ...]:
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
                    Override(
                        chain,
                        **{left: left_quant, right: right_quant},
                    )
                )
    return tuple(result)


def sample(points: list[Point], count: int) -> list[Point]:
    current = CURRENT_P
    constrained = []
    controls = []
    for point in points:
        target = (
            constrained
            if point_score(point, current)
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
            if point_score(point, CURRENT_P)
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
    return Override(
        override.chain, **{field: getattr(override, field)}
    )


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
        (name, sample(points, 150))
        for name, points in partitions
    ]
    baseline_values, baseline_signature = score_signature(
        samples, CURRENT_P
    )
    complete_baselines = [
        score_signature([(name, points)], CURRENT_P)[0][0]
        for name, points in partitions
    ]
    print(
        f"h188 loaded dense={len(raw['dense'])} "
        f"sweep={len(raw['sweep'])}"
    )
    for (name, points), value in zip(
        partitions, complete_baselines
    ):
        print(
            f"  baseline {name:11s} n={len(points):6d} "
            f"sine={value[0]} cosine={value[1]}"
        )

    sample_survivors = []
    singleton_signatures = {}
    for chain in ("p", "q"):
        candidates = overrides(chain)
        for override in candidates:
            values_by_sample, signature = score_signature(
                samples, override
            )
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
        print(
            f"h188 {chain.upper()} sample complete: "
            f"tested={len(candidates)}"
        )
    sample_survivors.sort()
    print(
        f"h188 sample gate: {len(sample_survivors)} changed, "
        f"componentwise survivors"
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
        score_signature([(name, points)], CURRENT_P)[0][0]
        for name, points in secondary
    ]
    secondary_classes = collections.defaultdict(list)
    for item in sample_survivors:
        override = item[5]
        values_by_gate, signature = score_signature(
            secondary, override
        )
        if (
            no_worse(values_by_gate, secondary_baselines)
            and any(
                value != old
                for value, old in zip(
                    values_by_gate, secondary_baselines
                )
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
        f"h188 all-residual gate: "
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
            survivors.append(
                (override, values_by_partition, class_size)
            )
    print(f"h188 complete joint-lane gate: {len(survivors)} survivors")
    for override, values_by_partition, class_size in survivors:
        print(f"  {override.short()} class={class_size}")
        for (name, _), old, value in zip(
            partitions, complete_baselines, values_by_partition
        ):
            if value != old:
                print(f"    {name:11s} {old}->{value}")


if __name__ == "__main__":
    main()
