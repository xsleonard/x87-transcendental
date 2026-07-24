#!/usr/bin/env python3
"""Search shared lookup-constant routing at the FIRC/FMUL boundary.

The eight Sj/Cj lookup constants have 67-bit significands.  A P5 FMUL can
accept one 67-bit X operand and one 64-bit Y operand, so placing a lookup
constant on Y discards exactly its three low bits.  Earlier passes tested
this route only for the narrow Cj*p terminal product.  This pass applies the
same physical question to every first lookup-constant consumer in Tang's
shared reconstruction graph:

    cross*r, lead*q, and cross*p.

Each consumer independently receives the native ROM67 value or an RN/chop/
away/odd 64-bit materialization.  The existing output operation, Tang RN67
correction, and validated narrow path-specific C*p route remain frozen.  The
search observes both FSINCOS lanes and accepts a route only when it is
componentwise no worse on dense/sweep, train/held, narrow/wide partitions.
"""

from __future__ import annotations

import dataclasses

import h58_constraint_search as h58
import h60_round16_parity as h60
import h110_fsin_standalone as h110
import h131_fsin_table_c1_search as h131
import h135_fsin_table_terminal_discriminator as h135
import h136_tang_reconstruction_search as h136
import h139_p5_fmul_route_search as h139
import h143_p5_fmul_c_parity as h143
import h169_fsin_table_round33_tomography as h169
import h170_fsin_table_correction_search as h170
import h173_fsin_table_fadd_topology as h173
import h177_table_sibling_triangulation as h177
import h182_table_joint_terminal_edges as h182


Metric = h173.Metric
NATIVE = "native67"
ROUTES = (NATIVE, "rn64", "chop64", "away64", "odd64")
RN67 = h110.Quant(67, "rn")


@dataclasses.dataclass(frozen=True)
class Candidate:
    linear: str = NATIVE
    q_product: str = NATIVE
    p_product: str = NATIVE

    def short(self) -> str:
        return (
            f"linear={self.linear} q={self.q_product} "
            f"p={self.p_product}"
        )


CURRENT = Candidate()


@dataclasses.dataclass(frozen=True)
class Point:
    joint: h182.Point
    state: h136.State
    route: h139.Route | None


def dataset(name: str) -> list[h182.Point]:
    input_path = h131.INPUTS / (
        "dense_qn.txt" if name == "dense" else "sweep_inputs.txt"
    )
    observed = h131.load_dataset(name, input_path)
    paired = {
        rc: h177.parse_pair(
            h177.PAIRED / f"{name}_fsincos_{rc}_status.txt"
        )
        for rc in h58.RCS
    }
    return [
        h182.Point(
            point,
            tuple(
                paired[rc][point.index][1] for rc in h58.RCS
            ),
            tuple(
                paired[rc][point.index][2] for rc in h58.RCS
            ),
        )
        for point in observed
    ]


def prepare(point: h182.Point) -> Point:
    observed = point.observed
    state = h136.standalone_state(
        observed.point, h135.path_candidate(observed)
    )
    route = (
        h143.SCHEDULE.route(observed.source == "reduced")
        if observed.family == "narrow"
        else None
    )
    return Point(point, state, route)


def route_constant(value: h58.FP, route: str) -> h58.FP:
    if route == NATIVE:
        return value
    mode, bits = route[:-2], int(route[-2:])
    return h110.quantize(value, h110.Quant(bits, mode))


def lane_value(
    point: Point,
    lead: h58.FP,
    cross: h58.FP,
    subtract: bool,
    candidate: Candidate,
) -> h58.FP:
    linear_constant = route_constant(cross, candidate.linear)
    q_constant = route_constant(lead, candidate.q_product)
    p_constant = route_constant(cross, candidate.p_product)

    linear = h58.mul_exact(
        linear_constant, point.state.residual
    )
    q_product = h58.mul_exact(
        q_constant, point.state.cosine_tail
    )
    p_product = (
        h139.p5_fmul(
            p_constant,
            point.state.sine_correction,
            point.route,
        )
        if point.route is not None
        else h58.mul_exact(
            p_constant, point.state.sine_correction
        )
    )
    if subtract:
        linear = h58.neg(linear)
        p_product = h58.neg(p_product)
    nonlinear = h58.add_exact(q_product, p_product)
    correction = h110.quantize(
        h58.add_exact(linear, nonlinear), RN67
    )
    return h58.add_exact(lead, correction)


def values(
    point: Point, candidate: Candidate
) -> tuple[h58.FP, h58.FP]:
    prepared = point.joint.observed.point
    sine = lane_value(
        point,
        prepared.sin_t,
        prepared.cos_t,
        False,
        candidate,
    )
    cosine = lane_value(
        point,
        prepared.cos_t,
        prepared.sin_t,
        True,
        candidate,
    )
    if prepared.raw.sign:
        sine = h58.neg(sine)
    return h60.rotate(
        (sine, cosine), point.joint.observed.signed_n
    )


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


def no_worse(
    value: tuple[Metric, Metric],
    baseline: tuple[Metric, Metric],
) -> bool:
    return all(
        h173.no_worse(new, old)
        for new, old in zip(value, baseline)
    )


def candidates() -> tuple[Candidate, ...]:
    return tuple(
        Candidate(linear, q_product, p_product)
        for linear in ROUTES
        for q_product in ROUTES
        for p_product in ROUTES
    )


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
            ^ (observed.point.raw.sig >> 17)
            ^ (observed.point.raw.sig >> 41)
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


def main() -> None:
    raw = {
        name: dataset(name) for name in ("dense", "sweep")
    }
    partitions: list[tuple[str, list[Point]]] = []
    for name, points in raw.items():
        for family in ("narrow", "wide"):
            selected = [
                point
                for point in points
                if point.observed.family == family
            ]
            for split, predicate in (
                ("train", h131.is_train),
                ("held", lambda point: not h131.is_train(point)),
            ):
                partitions.append(
                    (
                        f"{name}-{family}-{split}",
                        [
                            prepare(point)
                            for point in selected
                            if predicate(point.observed)
                        ],
                    )
                )

    for _, points in partitions:
        for point in points[:8]:
            expected = h173.hidden(
                h173.make_terms(point.joint.observed), h173.CURRENT
            )
            actual = values(point, CURRENT)[0]
            if actual != expected:
                raise AssertionError(
                    (point.joint.observed.index, actual, expected)
                )

    baselines = [
        score(points, CURRENT) for _, points in partitions
    ]
    samples = [
        (name, sample(points, 400)) for name, points in partitions
    ]
    sample_baselines = [
        score(points, CURRENT) for _, points in samples
    ]
    print(
        f"h184 loaded dense={len(raw['dense'])} "
        f"sweep={len(raw['sweep'])}; candidates={len(candidates())}"
    )
    for (name, points), value in zip(partitions, baselines):
        print(
            f"  baseline {name:19s} n={len(points):6d} "
            f"sine={value[0]} cosine={value[1]}"
        )

    ranked = []
    for candidate in candidates():
        values_by_sample = [
            score(points, candidate) for _, points in samples
        ]
        ranked.append(
            (
                sum(
                    metric[0]
                    for value in values_by_sample
                    for metric in value
                ),
                sum(
                    metric[2]
                    for value in values_by_sample
                    for metric in value
                ),
                sum(
                    metric[1]
                    for value in values_by_sample
                    for metric in value
                ),
                candidate.short(),
                candidate,
                values_by_sample,
            )
        )
    ranked.sort()

    survivors = []
    complete_checked = 0
    for *_, candidate, sample_values in ranked:
        if not all(
            no_worse(value, old)
            for value, old in zip(
                sample_values, sample_baselines
            )
        ):
            continue
        complete_checked += 1
        values_by_partition = [
            score(points, candidate) for _, points in partitions
        ]
        if all(
            no_worse(value, old)
            for value, old in zip(values_by_partition, baselines)
        ):
            survivors.append((candidate, values_by_partition))

    print(
        f"h184 complete gate: {len(survivors)} survivors "
        f"from {complete_checked} sample survivors"
    )
    for candidate, values_by_partition in survivors:
        changed = any(
            value != old
            for value, old in zip(values_by_partition, baselines)
        )
        print(
            f"  {'CHANGED' if changed else 'IDENTICAL'} "
            f"{candidate.short()}"
        )
        for (name, _), old, value in zip(
            partitions, baselines, values_by_partition
        ):
            if value != old:
                print(f"    {name:19s} {old}->{value}")

    print("h184 leading sample routes:")
    for item in ranked[:12]:
        print(
            f"  modes/c1/inputs={item[0]}/{item[1]}/{item[2]} "
            f"{item[4].short()}"
        )


if __name__ == "__main__":
    main()
