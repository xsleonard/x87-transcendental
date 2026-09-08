#!/usr/bin/env python3
"""Replay every Tang reconstruction topology through literal P5 FADD.

h173--h176 search the seven four-term Tang addition trees with scalar
materializations.  h200--h205 apply a bit-vector FADD only inside the P/Q
polynomial producers.  This pass closes that gap: all three additions in
every h173 topology use h206's complete FAMUBUS/X2 model.

The first two additions independently select retained normalized carrier,
retained normalization-disabled carrier, or a physical 64-bit FRND result.
The final carrier is tested with normalization on and off before architectural
rounding.  Linear, Q, and P products are explicitly routed through X67/Y64
FMUL inputs and may return either the sticky 67-bit carrier or RN64.

Selection is joint-lane and componentwise across deterministic sweep halves,
h171/h175 final-addition captures, and later producer captures.  Exact sample
profiles alone advance to the complete dense/sweep gates.
"""

from __future__ import annotations

import collections
import dataclasses
import functools
import hashlib

import h58_constraint_search as h58
import h60_round16_parity as h60
import h79_table_state_bias as h79
import h110_fsin_standalone as h110
import h131_fsin_table_c1_search as h131
import h134_fsin_table_per_edge_search as h134
import h136_tang_reconstruction_search as h136
import h170_fsin_table_correction_search as h170
import h171_fsin_table_correction_discriminator as h171
import h173_fsin_table_fadd_topology as h173
import h175_fsin_table_path_discriminator as h175
import h182_table_joint_terminal_edges as h182
import h183_table_joint_product_discriminator as h183
import h184_table_lookup_firc_routes as h184
import h185_table_lookup_firc_discriminator as h185
import h188_table_stage_local_pairs as h188
import h189_table_stage_local_discriminator as h189
import h190_table_stage_local_c_parity as h190
import h200_p5_fadd_bitvector as h200
import h201_p5_fadd_path_gate as h201
import h206_p5_fadd_complete as h206


Metric = h173.Metric
JointMetric = tuple[Metric, Metric]
ACTIONS = ("retain", "retain-raw", "rn64", "chop64", "away64", "odd64")
PRODUCT_OUTPUTS = ("odd67", "rn64")
TOPOLOGIES = h173.TOPOLOGIES
MODES = h206.MODES


@dataclasses.dataclass(frozen=True)
class ProductRoute:
    linear: str = "odd67"
    q_product: str = "odd67"
    p_product: str = "odd67"

    def short(self) -> str:
        return f"products={self.linear}/{self.q_product}/{self.p_product}"


@dataclasses.dataclass(frozen=True)
class Candidate:
    topology: str
    mode: str
    first: str
    second: str
    final_normalize: bool
    products: ProductRoute

    def short(self) -> str:
        final = "norm" if self.final_normalize else "raw"
        return (
            f"{self.topology} {self.mode} {self.first}/{self.second}/"
            f"final-{final} {self.products.short()}"
        )


@dataclasses.dataclass(frozen=True)
class Terms:
    lead: h206.Bus
    linear: h206.Bus
    q_product: h206.Bus
    p_product: h206.Bus


@dataclasses.dataclass(frozen=True)
class Point:
    prepared: h188.Point
    cosine_hardware: bool


def negate(bus: h206.Bus) -> h206.Bus:
    return dataclasses.replace(bus, sign=bus.sign ^ 1) if bus.word else bus


def state(point: h188.Point, shared: bool) -> h136.State:
    observed = point.joint.observed
    p = h188.producer(point, h189.CANDIDATES[1])
    q = (
        h134.horner(
            h58.C6,
            point.square,
            h134.CURRENT.q_coefficients,
            h134.CURRENT.q_products,
            h134.CURRENT.q_sums,
        )
        if shared
        else point.q_current
    )
    p_square = h110.quantize(
        h58.mul_exact(p, point.square), h206.RN64
    )
    correction = h110.quantize(
        h58.mul_exact(p_square, observed.point.a), h206.RN64
    )
    sine_a = h110.quantize(
        h58.add_exact(observed.point.a, correction), h206.RN64
    )
    sine_a = h79.bias_toward_zero(sine_a, 5)
    sine_correction = h58.add_exact(
        sine_a, h58.neg(observed.point.a)
    )
    cosine_tail = h110.quantize(
        h58.mul_exact(q, point.square), h206.RN64
    )
    return h136.State(observed.point.a, sine_correction, cosine_tail)


def value_bus(value: h58.FP, quant: h110.Quant | None = None) -> h206.Bus:
    if quant is not None:
        value = h110.quantize(value, quant)
    return h200.normalized_bus(value)


def product_bus(
    x: h58.FP,
    y: h58.FP,
    output: str,
    y_quant: h110.Quant = h206.RN64,
) -> h206.Bus:
    return h206.fmul_x67_y64(
        value_bus(x),
        value_bus(y),
        y_mode="rn64",
        output=output,
    )


@functools.lru_cache(maxsize=None)
def lane_terms(
    point: h188.Point,
    shared: bool,
    cosine_lane: bool,
    products: ProductRoute,
) -> Terms:
    prepared = point.joint.observed.point
    current = state(point, shared)
    if cosine_lane:
        lead, cross, subtract = prepared.cos_t, prepared.sin_t, True
    else:
        lead, cross, subtract = prepared.sin_t, prepared.cos_t, False
    linear = product_bus(cross, current.residual, products.linear)
    q_product = product_bus(
        lead, current.cosine_tail, products.q_product
    )
    # Round 34 routes the wide cross constant through RN64 before cross*p;
    # the retained state occupies X67 and the constant occupies Y64.
    p_product = h206.fmul_x67_y64(
        value_bus(current.sine_correction),
        value_bus(cross, h206.RN64),
        output=products.p_product,
    )
    if subtract:
        linear = negate(linear)
        p_product = negate(p_product)
    return Terms(value_bus(lead), linear, q_product, p_product)


def add_action(
    left: h206.Bus,
    right: h206.Bus,
    mode: str,
    action: str,
) -> tuple[h206.Bus, h206.AddTrace]:
    result, trace = h206.fadd(
        left,
        right,
        mode,
        normalize=action != "retain-raw",
    )
    return h206.materialize(result, action), trace


def reconstruct(
    terms: Terms, candidate: Candidate
) -> tuple[h206.Bus, tuple[h206.AddTrace, ...]]:
    lead = terms.lead
    linear = terms.linear
    q_product = terms.q_product
    p_product = terms.p_product
    mode = candidate.mode
    traces = []

    def first(left, right):
        value, trace = add_action(left, right, mode, candidate.first)
        traces.append(trace)
        return value

    def second(left, right):
        value, trace = add_action(left, right, mode, candidate.second)
        traces.append(trace)
        return value

    if candidate.topology == "correction":
        partial = first(q_product, p_product)
        partial = second(linear, partial)
        left, right = lead, partial
    elif candidate.topology == "lead-linear":
        partial = first(lead, linear)
        nonlinear = second(q_product, p_product)
        left, right = partial, nonlinear
    elif candidate.topology == "lead-nonlinear":
        nonlinear = first(q_product, p_product)
        partial = second(lead, nonlinear)
        left, right = partial, linear
    elif candidate.topology == "lead-q":
        partial = first(lead, q_product)
        cross = second(linear, p_product)
        left, right = partial, cross
    elif candidate.topology == "lead-p":
        partial = first(lead, p_product)
        other = second(linear, q_product)
        left, right = partial, other
    elif candidate.topology == "serial-q-p":
        partial = first(lead, linear)
        partial = second(partial, q_product)
        left, right = partial, p_product
    elif candidate.topology == "serial-p-q":
        partial = first(lead, linear)
        partial = second(partial, p_product)
        left, right = partial, q_product
    else:
        raise ValueError(candidate.topology)
    value, trace = h206.fadd(
        left,
        right,
        mode,
        normalize=candidate.final_normalize,
    )
    traces.append(trace)
    return value, tuple(traces)


def local_values(point: h188.Point, candidate: Candidate, shared: bool):
    sine = reconstruct(
        lane_terms(point, shared, False, candidate.products), candidate
    )[0].value()
    cosine = reconstruct(
        lane_terms(point, shared, True, candidate.products), candidate
    )[0].value()
    if point.joint.observed.point.raw.sign:
        sine = h58.neg(sine)
    return h60.rotate(
        (sine, cosine), point.joint.observed.signed_n
    )


def hidden_values(point: h188.Point, candidate: Candidate):
    sine = local_values(point, candidate, False)[0]
    cosine = local_values(point, candidate, True)[1]
    return sine, cosine


def current_values(point: h188.Point):
    return h190.hidden_values(point, True)


def point_metric(point: Point, candidate: Candidate | None) -> JointMetric:
    sine, cosine = (
        current_values(point.prepared)
        if candidate is None
        else hidden_values(point.prepared, candidate)
    )
    sine_metric = h170.point_metric(
        point.prepared.joint.observed, sine
    )
    cosine_metric = (
        h182.point_metric(
            point.prepared.joint.cosine_outputs,
            point.prepared.joint.cosine_c1,
            cosine,
        )
        if point.cosine_hardware
        else (0, 0, 0)
    )
    return sine_metric, cosine_metric


def add_metric(left: JointMetric, right: JointMetric) -> JointMetric:
    return tuple(
        h170.add(old, new) for old, new in zip(left, right)
    )  # type: ignore[return-value]


def score_signature(datasets, candidate: Candidate | None):
    digest = hashlib.sha256()
    values = []
    for name, points in datasets:
        digest.update(name.encode("ascii"))
        result: JointMetric = ((0, 0, 0), (0, 0, 0))
        for point in points:
            metric = point_metric(point, candidate)
            digest.update(bytes((*metric[0], *metric[1])))
            result = add_metric(result, metric)
        values.append(result)
    return values, digest.digest()


def gated_score(datasets, baselines, candidate: Candidate):
    """Score one candidate, stopping at its first regressing partition."""
    digest = hashlib.sha256()
    values = []
    cache = {}
    for (name, points), baseline in zip(datasets, baselines):
        digest.update(name.encode("ascii"))
        result: JointMetric = ((0, 0, 0), (0, 0, 0))
        for point in points:
            metric = cache.get(point)
            if metric is None:
                metric = point_metric(point, candidate)
                cache[point] = metric
            digest.update(bytes((*metric[0], *metric[1])))
            result = add_metric(result, metric)
        if not no_worse(result, baseline):
            return None
        values.append(result)
    return values, digest.digest()


def no_worse(value: JointMetric, baseline: JointMetric) -> bool:
    return all(
        h173.no_worse(new, old) for new, old in zip(value, baseline)
    )


def objective(values) -> tuple[int, int, int]:
    return tuple(
        sum(metric[index] for value in values for metric in value)
        for index in (0, 2, 1)
    )


def candidates():
    routes = tuple(
        ProductRoute(linear, q_product, p_product)
        for linear in PRODUCT_OUTPUTS
        for q_product in PRODUCT_OUTPUTS
        for p_product in PRODUCT_OUTPUTS
    )
    for products in routes:
        for topology in TOPOLOGIES:
            for mode in MODES:
                for first in ACTIONS:
                    for second in ACTIONS:
                        for final_normalize in (False, True):
                            yield Candidate(
                                topology,
                                mode,
                                first,
                                second,
                                final_normalize,
                                products,
                            )


def joint_partitions(name: str):
    points = [
        Point(h188.prepare(point), True)
        for point in h184.dataset(name)
        if point.observed.family == "wide"
    ]
    return [
        (
            f"{name}-{split}",
            [
                point
                for point in points
                if h131.is_train(point.prepared.joint.observed)
                == (split == "train")
            ],
        )
        for split in ("train", "held")
    ]


def standalone_points(observed):
    result = []
    for item in observed:
        if item.family != "wide":
            continue
        fake = h182.Point(
            item,
            ((0, 0), (0, 0), (0, 0)),
            (False, False, False),
        )
        result.append(Point(h188.prepare(fake), False))
    return result


def focused_datasets():
    result = [
        (
            "h183",
            [
                Point(h188.prepare(point), True)
                for point in h183.load_capture(
                    h183.DEFAULT_OUTPUT,
                    h183.ROOT / "capture-kit-captures" / "skylake-fsin-h183",
                )
                if point.observed.family == "wide"
            ],
        ),
        (
            "h185",
            [
                Point(h188.prepare(point.joint), True)
                for point in h185.load_capture(
                    h185.DEFAULT_OUTPUT,
                    h185.ROOT / "capture-kit-captures" / "skylake-fsin-h185",
                )
                if point.joint.observed.family == "wide"
            ],
        ),
        (
            "h189",
            [Point(point, True) for point in h189.load_capture(
                h189.DEFAULT_OUTPUT,
                h189.ROOT / "capture-kit-captures" / "skylake-fsin-h189",
            )],
        ),
    ]
    h171_points = h171.load_capture(
        h171.DEFAULT_OUTPUT,
        h171.ROOT / "capture-kit-captures" / "skylake-fsin-h171",
    )
    result.append(("h171", standalone_points(h171_points)))
    h175_points = h175.load_capture(
        h175.DEFAULT_OUTPUT,
        h175.ROOT / "capture-kit-captures" / "skylake-fsin-h175",
    )
    metadata = h175.DEFAULT_METADATA.read_text().splitlines()
    result.append(("h175-all", standalone_points(h175_points)))
    for mechanism in h175.CANDIDATES:
        selected = [
            point
            for point, line in zip(h175_points, metadata)
            if any(
                item.split(":", 1)[0] == mechanism.name
                for item in line.split()[-1].split(",")
            )
        ]
        result.append(
            (f"h175-{mechanism.name}", standalone_points(selected))
        )
    return result


def sample(datasets, controls: int = 240):
    result = []
    for name, points in datasets:
        constrained = []
        correct = []
        for point in points:
            target = (
                constrained
                if point_metric(point, None)
                != ((0, 0, 0), (0, 0, 0))
                else correct
            )
            target.append(point)
        correct.sort(
            key=lambda point: (
                point.prepared.joint.observed.point.raw.sig
                ^ (point.prepared.joint.observed.index << 7)
                ^ point.prepared.joint.observed.signed_n
            )
        )
        result.append((name, constrained + correct[:controls]))
    return result


def trace_census(points, candidate: Candidate):
    counts = collections.Counter()
    for point in points:
        for shared in (False, True):
            for cosine_lane in (False, True):
                terms = lane_terms(
                    point.prepared,
                    shared,
                    cosine_lane,
                    candidate.products,
                )
                _, traces = reconstruct(terms, candidate)
                counts.update(
                    (trace.operation, trace.exponent_difference)
                    for trace in traces
                )
    return counts


def main() -> None:
    sweep = joint_partitions("sweep")
    focused = focused_datasets()
    selected = [*sample(sweep), *focused]
    baselines, baseline_signature = score_signature(selected, None)
    complete_baselines = score_signature(sweep, None)[0]
    values_to_test = tuple(candidates())
    print(
        f"h207 literal Tang FADD: candidates={len(values_to_test)} "
        f"sample={sum(len(points) for _, points in selected)} "
        f"wide-sweep={sum(len(points) for _, points in sweep)}"
    )
    for (name, points), baseline in zip(selected, baselines):
        print(f"  baseline {name:44s} n={len(points):5d} {baseline}")

    profiles = collections.defaultdict(list)
    for index, candidate in enumerate(values_to_test, 1):
        scored = gated_score(selected, baselines, candidate)
        if scored is None:
            if index % 2048 == 0:
                print(f"  progress {index}/{len(values_to_test)}", flush=True)
            continue
        values, signature = scored
        item = (*objective(values), candidate.short(), candidate)
        if (
            signature != baseline_signature
            and any(
                value != baseline
                for value, baseline in zip(values, baselines)
            )
        ):
            profiles[signature].append(item)
        if index % 2048 == 0:
            print(f"  progress {index}/{len(values_to_test)}", flush=True)
    representatives = sorted(min(items) for items in profiles.values())
    print(
        f"h207 sample gate: "
        f"{sum(len(items) for items in profiles.values())} survivors "
        f"in {len(representatives)} profiles"
    )
    final = []
    for item in representatives:
        candidate = item[4]
        values, _ = score_signature(sweep, candidate)
        if all(
            no_worse(value, baseline)
            for value, baseline in zip(values, complete_baselines)
        ) and any(
            value != baseline
            for value, baseline in zip(values, complete_baselines)
        ):
            final.append((*objective(values), candidate.short(), candidate))
    final.sort()
    print(f"h207 complete sweep: {len(final)} survivors")
    if final:
        validation = [*joint_partitions("dense"), *focused]
        validation_baselines = score_signature(validation, None)[0]
        surviving = []
        for item in final:
            candidate = item[4]
            values, _ = score_signature(validation, candidate)
            if all(
                no_worse(value, baseline)
                for value, baseline in zip(values, validation_baselines)
            ) and any(
                value != baseline
                for value, baseline in zip(values, validation_baselines)
            ):
                surviving.append(candidate)
        print(f"h207 dense/focused: {len(surviving)} survivors")
        for candidate in surviving:
            print(f"  {candidate.short()}")
            print(f"    census={trace_census(selected[0][1], candidate)}")


if __name__ == "__main__":
    main()
