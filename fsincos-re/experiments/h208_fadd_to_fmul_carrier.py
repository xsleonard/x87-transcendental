#!/usr/bin/env python3
"""Preserve retained FADD representation through the next P5 FMUL.

h200/h205 convert a retained FAMUBUS carrier to a numerical FP value before
the next Horner product.  Although that preserves its approximate magnitude,
it does not explicitly enforce the P5 multiplier boundary.  This pass routes
the carrier word, including J=0 and G/R/S, directly to X67; the RN64 square
occupies Y64.  FMUL returns either its sticky 67-bit carrier or a physical
64-bit materialization.

Every P/Q retain mask is collapsed by exact producer profile before global,
direct, and reduced gates are crossed.  Both FRND normalization states and
all four FADD sticky/borrow readings are tested.  Selection uses the same
joint and final-addition focused datasets as h207.
"""

from __future__ import annotations

import collections
import dataclasses
import functools
import hashlib

import h58_constraint_search as h58
import h79_table_state_bias as h79
import h110_fsin_standalone as h110
import h134_fsin_table_per_edge_search as h134
import h136_tang_reconstruction_search as h136
import h173_fsin_table_fadd_topology as h173
import h184_table_lookup_firc_routes as h184
import h188_table_stage_local_pairs as h188
import h189_table_stage_local_discriminator as h189
import h200_p5_fadd_bitvector as h200
import h201_p5_fadd_path_gate as h201
import h206_p5_fadd_complete as h206
import h207_tang_literal_fadd as h207


JointMetric = h207.JointMetric
OUTPUTS = ("odd67", "rn64", "chop64", "away64", "odd64")
GATES = h201.GATES


@dataclasses.dataclass(frozen=True)
class Candidate:
    mode: str
    normalize_retained: bool
    output: str
    p_mask: int | None
    p_gate: str | None
    q_mask: int | None
    q_gate: str | None

    def short(self) -> str:
        normalization = "norm" if self.normalize_retained else "raw"

        def show(name, mask, gate):
            if mask is None:
                return f"{name}=scalar"
            stages = "".join(
                str(index + 1)
                for index in range(h200.STAGES)
                if mask & (1 << index)
            )
            return f"{name}={gate}[{stages or '-'}]"

        return (
            f"{self.mode}/{normalization} FMUL={self.output} "
            f"{show('P', self.p_mask, self.p_gate)} "
            f"{show('Q', self.q_mask, self.q_gate)}"
        )


def selected(gate: str | None, point: h188.Point) -> bool:
    if gate is None:
        return False
    source = point.joint.observed.source
    return gate == "all" or gate == source


@functools.lru_cache(maxsize=None)
def producer(
    point: h188.Point,
    chain: str,
    mask: int,
    mode: str,
    normalize_retained: bool,
    output: str,
    shared: bool,
) -> h58.FP:
    base = h134.CURRENT if shared else point.base
    if chain == "p":
        rows = h58.S6
        coefficients = (*base.p_coefficients[:-1], h206.AWAY64)
        sums = (*base.p_sums[:-1], h110.Quant(65, "chop"))
    else:
        rows = h58.C6
        coefficients = base.q_coefficients
        sums = base.q_sums
    value = h200.normalized_bus(
        h134.coefficient(rows[0], coefficients[0])
    )
    square = h200.normalized_bus(point.square)
    for index, row in enumerate(rows[1:]):
        product = h206.fmul_x67_y64(
            value,
            square,
            output=output,
        )
        coefficient = h200.normalized_bus(
            h134.coefficient(row, coefficients[index + 1])
        )
        retain = bool(mask & (1 << index))
        value, _ = h206.fadd(
            product,
            coefficient,
            mode,
            normalize=normalize_retained or not retain,
        )
        if not retain:
            value = h200.materialize_bus(value, sums[index])
    return value.value()


def current_producer(point: h188.Point, chain: str, shared: bool):
    if chain == "p":
        return h188.producer(point, h189.CANDIDATES[1])
    if shared:
        return h134.horner(
            h58.C6,
            point.square,
            h134.CURRENT.q_coefficients,
            h134.CURRENT.q_products,
            h134.CURRENT.q_sums,
        )
    return point.q_current


def producer_for(
    point: h188.Point,
    candidate: Candidate,
    chain: str,
    shared: bool,
):
    mask = candidate.p_mask if chain == "p" else candidate.q_mask
    gate = candidate.p_gate if chain == "p" else candidate.q_gate
    if mask is None or not selected(gate, point):
        return current_producer(point, chain, shared)
    return producer(
        point,
        chain,
        mask,
        candidate.mode,
        candidate.normalize_retained,
        candidate.output,
        shared,
    )


def state(point: h188.Point, candidate: Candidate, shared: bool):
    observed = point.joint.observed
    p = producer_for(point, candidate, "p", shared)
    q = producer_for(point, candidate, "q", shared)
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
    return h136.State(
        observed.point.a,
        h58.add_exact(sine_a, h58.neg(observed.point.a)),
        h110.quantize(h58.mul_exact(q, point.square), h206.RN64),
    )


def hidden_values(point: h188.Point, candidate: Candidate):
    sine = h184.values(
        h184.Point(point.joint, state(point, candidate, False), None),
        h188.ROUND34,
    )[0]
    cosine = h184.values(
        h184.Point(point.joint, state(point, candidate, True), None),
        h188.ROUND34,
    )[1]
    return sine, cosine


def point_metric(point: h207.Point, candidate: Candidate | None):
    if candidate is None:
        return h207.point_metric(point, None)
    sine, cosine = hidden_values(point.prepared, candidate)
    sine_metric = h207.h170.point_metric(
        point.prepared.joint.observed, sine
    )
    cosine_metric = (
        h207.h182.point_metric(
            point.prepared.joint.cosine_outputs,
            point.prepared.joint.cosine_c1,
            cosine,
        )
        if point.cosine_hardware
        else (0, 0, 0)
    )
    return sine_metric, cosine_metric


def score_signature(datasets, candidate: Candidate | None):
    digest = hashlib.sha256()
    values = []
    cache = {}
    for name, points in datasets:
        digest.update(name.encode("ascii"))
        result: JointMetric = ((0, 0, 0), (0, 0, 0))
        for point in points:
            metric = cache.get(point)
            if metric is None:
                metric = point_metric(point, candidate)
                cache[point] = metric
            digest.update(bytes((*metric[0], *metric[1])))
            result = h207.add_metric(result, metric)
        values.append(result)
    return values, digest.digest()


def mask_profiles(
    datasets,
    chain: str,
    mode: str,
    normalize_retained: bool,
    output: str,
):
    classes = collections.defaultdict(list)
    unique = tuple(
        dict.fromkeys(
            point.prepared
            for _, points in datasets
            for point in points
        )
    )
    for mask in range(32):
        digest = hashlib.sha256()
        for point in unique:
            if chain == "p":
                h201.value_digest(
                    producer(
                        point,
                        chain,
                        mask,
                        mode,
                        normalize_retained,
                        output,
                        False,
                    ),
                    digest,
                )
            else:
                for shared in (False, True):
                    h201.value_digest(
                        producer(
                            point,
                            chain,
                            mask,
                            mode,
                            normalize_retained,
                            output,
                            shared,
                        ),
                        digest,
                    )
        classes[digest.digest()].append(mask)
    return {min(masks): tuple(masks) for masks in classes.values()}


def candidates(mode, normalize_retained, output, p_masks, q_masks):
    p_options = [(None, None)] + [
        (mask, gate) for mask in p_masks for gate in GATES
    ]
    q_options = [(None, None)] + [
        (mask, gate) for mask in q_masks for gate in GATES
    ]
    for p_mask, p_gate in p_options:
        for q_mask, q_gate in q_options:
            if p_mask is not None or q_mask is not None:
                yield Candidate(
                    mode,
                    normalize_retained,
                    output,
                    p_mask,
                    p_gate,
                    q_mask,
                    q_gate,
                )


def main() -> None:
    sweep = h207.joint_partitions("sweep")
    focused = h207.focused_datasets()
    selected = [*h207.sample(sweep), *focused]
    baselines, baseline_signature = score_signature(selected, None)
    complete_baselines = score_signature(sweep, None)[0]
    profiles = collections.defaultdict(list)
    tested = 0
    for mode in h206.MODES:
        for normalize_retained in (False, True):
            for output in OUTPUTS:
                p_profiles = mask_profiles(
                    selected,
                    "p",
                    mode,
                    normalize_retained,
                    output,
                )
                q_profiles = mask_profiles(
                    selected,
                    "q",
                    mode,
                    normalize_retained,
                    output,
                )
                print(
                    f"  {mode}/{'norm' if normalize_retained else 'raw'} "
                    f"{output}: P={p_profiles} Q={q_profiles}",
                    flush=True,
                )
                for candidate in candidates(
                    mode,
                    normalize_retained,
                    output,
                    p_profiles,
                    q_profiles,
                ):
                    tested += 1
                    values, signature = score_signature(selected, candidate)
                    if (
                        signature != baseline_signature
                        and all(
                            h207.no_worse(value, baseline)
                            for value, baseline in zip(values, baselines)
                        )
                        and any(
                            value != baseline
                            for value, baseline in zip(values, baselines)
                        )
                    ):
                        profiles[signature].append(
                            (*h207.objective(values), candidate.short(), candidate)
                        )
    representatives = sorted(min(items) for items in profiles.values())
    print(
        f"h208 sample: tested={tested} "
        f"survivors={sum(len(items) for items in profiles.values())} "
        f"profiles={len(representatives)}"
    )
    final = []
    for item in representatives:
        candidate = item[4]
        values, _ = score_signature(sweep, candidate)
        if all(
            h207.no_worse(value, baseline)
            for value, baseline in zip(values, complete_baselines)
        ) and any(
            value != baseline
            for value, baseline in zip(values, complete_baselines)
        ):
            final.append((*h207.objective(values), candidate.short(), candidate))
    final.sort()
    print(f"h208 complete sweep: {len(final)} survivors")
    if final:
        validation = [*h207.joint_partitions("dense"), *focused]
        validation_baselines = score_signature(validation, None)[0]
        surviving = []
        for item in final:
            candidate = item[4]
            values, _ = score_signature(validation, candidate)
            if all(
                h207.no_worse(value, baseline)
                for value, baseline in zip(values, validation_baselines)
            ):
                surviving.append(candidate)
        print(f"h208 dense/focused: {len(surviving)} survivors")
        for candidate in surviving:
            print(f"  {candidate.short()}")


if __name__ == "__main__":
    main()
