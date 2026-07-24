#!/usr/bin/env python3
"""Search coordinated P/Q producer schedules after Round 34.

h181 and h182 reject every individual wide-Q coordinate and every terminal
producer edge.  h179 nevertheless projects the joint sine/cosine residuals
almost evenly onto P and Q.  This pass therefore permits one P-Horner edge
and one Q-Horner edge to change together.  It is a bounded beam search, not
an unconstrained Boolean fit:

* coefficients and sums use 64..72-bit RN/chop/away/odd materialization;
* products additionally allow an exact carrier;
* the current path-aware schedule and Round-34 lookup route stay frozen;
* beam ranking uses deterministic samples;
* acceptance requires separate sine/cosine componentwise non-regression on
  complete dense/sweep train/held partitions.
"""

from __future__ import annotations

import collections
import dataclasses
import functools
import hashlib

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


@dataclasses.dataclass(frozen=True)
class Change:
    chain: str
    field: str
    index: int
    quant: h110.Quant

    def coordinate(self) -> str:
        prefix = {
            "coefficients": "c",
            "products": "p",
            "sums": "s",
        }[self.field]
        return f"{self.chain}{prefix}{self.index + 1}"

    def short(self) -> str:
        return f"{self.coordinate()}={self.quant.short()}"


@dataclasses.dataclass(frozen=True)
class Candidate:
    p: Change | None = None
    q: Change | None = None

    def short(self) -> str:
        return " ".join(
            change.short()
            for change in (self.p, self.q)
            if change is not None
        ) or "current"


CURRENT = Candidate()


@dataclasses.dataclass(frozen=True)
class Point:
    joint: h182.Point
    base: h134.Schedule
    square: h58.FP


def replace(values, index: int, value):
    result = list(values)
    result[index] = value
    return tuple(result)


def apply_change(
    schedule: h134.Schedule, change: Change | None
) -> h134.Schedule:
    if change is None:
        return schedule
    name = f"{change.chain}_{change.field}"
    return dataclasses.replace(
        schedule,
        **{
            name: replace(
                getattr(schedule, name), change.index, change.quant
            )
        },
    )


def prepare(point: h182.Point) -> Point:
    observed = point.observed
    return Point(
        point,
        h135.path_candidate(observed),
        h58.fmul(
            observed.point.a, observed.point.a, 64, "rn"
        ),
    )


@functools.lru_cache(maxsize=None)
def producer(
    point: Point, chain: str, change: Change | None
) -> h58.FP:
    schedule = apply_change(point.base, change)
    rows = h58.S6 if chain == "p" else h58.C6
    return h134.horner(
        rows,
        point.square,
        getattr(schedule, f"{chain}_coefficients"),
        getattr(schedule, f"{chain}_products"),
        getattr(schedule, f"{chain}_sums"),
    )


def values(
    point: Point, candidate: Candidate
) -> tuple[h58.FP, h58.FP]:
    observed = point.joint.observed
    p = producer(point, "p", candidate.p)
    q = producer(point, "q", candidate.q)
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
    routed = h184.Point(point.joint, state, None)
    return h184.values(routed, ROUND34)


def point_score(
    point: Point, candidate: Candidate
) -> tuple[Metric, Metric]:
    sine, cosine = values(point, candidate)
    return (
        h170.point_metric(point.joint.observed, sine),
        h182.point_metric(
            point.joint.cosine_outputs,
            point.joint.cosine_c1,
            cosine,
        ),
    )


def score(
    points: list[Point], candidate: Candidate
) -> tuple[Metric, Metric]:
    result = ((0, 0, 0), (0, 0, 0))
    for point in points:
        value = point_score(point, candidate)
        result = tuple(
            h170.add(old, new)
            for old, new in zip(result, value)
        )
    return result


def score_signature(
    datasets: list[tuple[str, list[Point]]],
    candidate: Candidate,
) -> tuple[list[tuple[Metric, Metric]], bytes]:
    digest = hashlib.sha256()
    results = []
    for name, points in datasets:
        digest.update(name.encode("ascii"))
        result = ((0, 0, 0), (0, 0, 0))
        for point in points:
            value = point_score(point, candidate)
            digest.update(bytes((*value[0], *value[1])))
            result = tuple(
                h170.add(old, new)
                for old, new in zip(result, value)
            )
        results.append(result)
    return results, digest.digest()


def no_worse(value, baseline) -> bool:
    return all(
        h173.no_worse(new, old)
        for new, old in zip(value, baseline)
    )


def changes(chain: str) -> tuple[Change, ...]:
    result = []
    for field, count, exact in (
        ("coefficients", 6, False),
        ("products", 5, True),
        ("sums", 5, False),
    ):
        options = [
            h110.Quant(bits, mode)
            for bits in range(64, 73)
            for mode in ("rn", "chop", "away", "odd")
        ]
        if exact:
            options.insert(0, h110.EXACT)
        for index in range(count):
            result.extend(
                Change(chain, field, index, quant)
                for quant in options
            )
    return tuple(result)


def objective(values) -> tuple[int, int, int]:
    return tuple(
        sum(metric[index] for value in values for metric in value)
        for index in (0, 2, 1)
    )


def beam(
    chain: str,
    samples: list[tuple[str, list[Point]]],
    baselines,
) -> list[Change]:
    ranked = []
    for change in changes(chain):
        candidate = Candidate(
            p=change if chain == "p" else None,
            q=change if chain == "q" else None,
        )
        results = [
            score(points, candidate) for _, points in samples
        ]
        if results == baselines:
            continue
        ranked.append(
            (*objective(results), change.short(), change, results)
        )
    ranked.sort()
    selected: dict[Change, None] = {}
    for item in ranked[:32]:
        selected[item[4]] = None
    by_coordinate = collections.defaultdict(list)
    for item in ranked:
        by_coordinate[item[4].coordinate()].append(item)
    for items in by_coordinate.values():
        for item in items[:2]:
            selected[item[4]] = None
    print(
        f"h187 {chain.upper()} beam: {len(selected)} from "
        f"{len(ranked)} changed single-edge routes"
    )
    for item in ranked[:8]:
        print(
            f"  {item[4].short():18s} "
            f"sample modes/c1/inputs={item[0]}/{item[1]}/{item[2]}"
        )
    return list(selected)


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
            ^ (observed.point.raw.sig >> 23)
            ^ (observed.point.raw.sig >> 47)
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
            ^ (point.joint.observed.point.raw.sig >> 29)
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
        (name, sample(points, 150))
        for name, points in partitions
    ]
    baselines = [
        score(points, CURRENT) for _, points in partitions
    ]
    sample_baselines = [
        score(points, CURRENT) for _, points in samples
    ]
    print(
        f"h187 loaded dense={len(raw['dense'])} "
        f"sweep={len(raw['sweep'])}"
    )
    for (name, points), value in zip(partitions, baselines):
        print(
            f"  baseline {name:11s} n={len(points):6d} "
            f"sine={value[0]} cosine={value[1]}"
        )

    p_beam = beam("p", samples, sample_baselines)
    q_beam = beam("q", samples, sample_baselines)
    ranked = []
    for p_change in p_beam:
        for q_change in q_beam:
            candidate = Candidate(p_change, q_change)
            results = [
                score(points, candidate) for _, points in samples
            ]
            if not all(
                no_worse(value, old)
                for value, old in zip(results, sample_baselines)
            ):
                continue
            if results == sample_baselines:
                continue
            ranked.append(
                (*objective(results), candidate.short(), candidate, results)
            )
    ranked.sort()
    print(
        f"h187 paired sample gate: {len(ranked)} survivors from "
        f"{len(p_beam) * len(q_beam)} schedules"
    )

    secondary = [
        (name, constraint_gate(points, 250))
        for name, points in partitions
    ]
    secondary_baselines = [
        score(points, CURRENT) for _, points in secondary
    ]
    secondary_classes = collections.defaultdict(list)
    for item in ranked:
        candidate = item[4]
        results, signature = score_signature(secondary, candidate)
        if (
            all(
                no_worse(value, old)
                for value, old in zip(
                    results, secondary_baselines
                )
            )
            and any(
                value != old
                for value, old in zip(
                    results, secondary_baselines
                )
            )
        ):
            secondary_classes[signature].append(
                (*objective(results), candidate.short(), candidate)
            )
    secondary_survivors = [
        min(items) for items in secondary_classes.values()
    ]
    secondary_survivors.sort()
    print(
        f"h187 all-residual gate: "
        f"{sum(len(items) for items in secondary_classes.values())} "
        f"survivors in {len(secondary_survivors)} profile classes "
        f"from {len(ranked)} sample survivors; "
        f"n={sum(len(points) for _, points in secondary)}"
    )

    survivors = []
    for item in secondary_survivors:
        candidate = item[4]
        results = [
            score(points, candidate) for _, points in partitions
        ]
        if (
            all(
                no_worse(value, old)
                for value, old in zip(results, baselines)
            )
            and any(
                value != old
                for value, old in zip(results, baselines)
            )
        ):
            class_size = len(
                secondary_classes[
                    next(
                        signature
                        for signature, items in secondary_classes.items()
                        if item in items
                    )
                ]
            )
            survivors.append((candidate, results, class_size))
    print(
        f"h187 complete joint-lane gate: {len(survivors)} survivors"
    )
    for candidate, results, class_size in survivors:
        print(f"  {candidate.short()} class={class_size}")
        for (name, _), old, value in zip(
            partitions, baselines, results
        ):
            if value != old:
                print(f"    {name:11s} {old}->{value}")


if __name__ == "__main__":
    main()
