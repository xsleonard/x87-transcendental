#!/usr/bin/env python3
"""Coordinate surviving FADD-to-FMUL profiles with literal Tang FADD.

h207 finds no literal final-reconstruction schedule on the current producer.
h208 finds 40 exact producer profiles that pass every focused sample but fail
the complete sweep under the current scalar reconstruction.  A coordinated
microcode sequence could make neither half independently valid, so this pass
crosses one representative of each h208 sample profile with all seven Tang
trees under coherent controls:

* the same sticky/borrow interpretation is used in producer and reconstruction;
* the producer's FMUL output carrier is used for all three Tang products;
* both intermediate FADD controls remain independent;
* final normalization is independently enabled or disabled.

This is the bounded end-to-end FIRC search justified by the two preceding
passes, not an arbitrary cross of every rejected scalar schedule.
"""

from __future__ import annotations

import collections
import dataclasses
import functools
import hashlib

import h58_constraint_search as h58
import h60_round16_parity as h60
import h173_fsin_table_fadd_topology as h173
import h188_table_stage_local_pairs as h188
import h200_p5_fadd_bitvector as h200
import h206_p5_fadd_complete as h206
import h207_tang_literal_fadd as h207
import h208_fadd_to_fmul_carrier as h208


@dataclasses.dataclass(frozen=True)
class Candidate:
    producer: h208.Candidate
    reconstruction: h207.Candidate

    def short(self) -> str:
        return (
            f"producer=({self.producer.short()}) "
            f"reconstruct=({self.reconstruction.short()})"
        )


def producer_representatives(selected, baselines, baseline_signature):
    profiles = collections.defaultdict(list)
    for mode in h206.MODES:
        for normalize_retained in (False, True):
            for output in h208.OUTPUTS:
                p_profiles = h208.mask_profiles(
                    selected,
                    "p",
                    mode,
                    normalize_retained,
                    output,
                )
                q_profiles = h208.mask_profiles(
                    selected,
                    "q",
                    mode,
                    normalize_retained,
                    output,
                )
                for candidate in h208.candidates(
                    mode,
                    normalize_retained,
                    output,
                    p_profiles,
                    q_profiles,
                ):
                    values, signature = h208.score_signature(
                        selected, candidate
                    )
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
    return sorted(min(items) for items in profiles.values())


def value_bus(value: h58.FP, quant=None):
    if quant is not None:
        value = h207.h110.quantize(value, quant)
    return h200.normalized_bus(value)


@functools.lru_cache(maxsize=None)
def lane_terms(
    point: h188.Point,
    producer: h208.Candidate,
    shared: bool,
    cosine_lane: bool,
) -> h207.Terms:
    prepared = point.joint.observed.point
    current = h208.state(point, producer, shared)
    if cosine_lane:
        lead, cross, subtract = prepared.cos_t, prepared.sin_t, True
    else:
        lead, cross, subtract = prepared.sin_t, prepared.cos_t, False
    output = producer.output
    linear = h206.fmul_x67_y64(
        value_bus(cross), value_bus(current.residual), output=output
    )
    q_product = h206.fmul_x67_y64(
        value_bus(lead), value_bus(current.cosine_tail), output=output
    )
    p_product = h206.fmul_x67_y64(
        value_bus(current.sine_correction),
        value_bus(cross, h206.RN64),
        output=output,
    )
    if subtract:
        linear = h207.negate(linear)
        p_product = h207.negate(p_product)
    return h207.Terms(value_bus(lead), linear, q_product, p_product)


def local_values(
    point: h188.Point,
    candidate: Candidate,
    shared: bool,
):
    sine = h207.reconstruct(
        lane_terms(point, candidate.producer, shared, False),
        candidate.reconstruction,
    )[0].value()
    cosine = h207.reconstruct(
        lane_terms(point, candidate.producer, shared, True),
        candidate.reconstruction,
    )[0].value()
    if point.joint.observed.point.raw.sign:
        sine = h58.neg(sine)
    return h60.rotate(
        (sine, cosine), point.joint.observed.signed_n
    )


def hidden_values(point: h188.Point, candidate: Candidate):
    return (
        local_values(point, candidate, False)[0],
        local_values(point, candidate, True)[1],
    )


def point_metric(point: h207.Point, candidate: Candidate):
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


def gated_score(datasets, baselines, candidate: Candidate):
    digest = hashlib.sha256()
    values = []
    cache = {}
    for (name, points), baseline in zip(datasets, baselines):
        digest.update(name.encode("ascii"))
        result: h207.JointMetric = ((0, 0, 0), (0, 0, 0))
        for point in points:
            metric = cache.get(point)
            if metric is None:
                metric = point_metric(point, candidate)
                cache[point] = metric
            digest.update(bytes((*metric[0], *metric[1])))
            result = h207.add_metric(result, metric)
        if not h207.no_worse(result, baseline):
            return None
        values.append(result)
    return values, digest.digest()


def score_signature(datasets, candidate: Candidate):
    digest = hashlib.sha256()
    values = []
    cache = {}
    for name, points in datasets:
        digest.update(name.encode("ascii"))
        result: h207.JointMetric = ((0, 0, 0), (0, 0, 0))
        for point in points:
            metric = cache.get(point)
            if metric is None:
                metric = point_metric(point, candidate)
                cache[point] = metric
            digest.update(bytes((*metric[0], *metric[1])))
            result = h207.add_metric(result, metric)
        values.append(result)
    return values, digest.digest()


def candidates(producer: h208.Candidate):
    products = h207.ProductRoute(
        producer.output, producer.output, producer.output
    )
    for topology in h173.TOPOLOGIES:
        for first in h207.ACTIONS:
            for second in h207.ACTIONS:
                for final_normalize in (False, True):
                    reconstruction = h207.Candidate(
                        topology,
                        producer.mode,
                        first,
                        second,
                        final_normalize,
                        products,
                    )
                    yield Candidate(producer, reconstruction)


def main() -> None:
    sweep = h207.joint_partitions("sweep")
    focused = h207.focused_datasets()
    selected = [*h207.sample(sweep), *focused]
    baselines, baseline_signature = h208.score_signature(selected, None)
    complete_baselines = h208.score_signature(sweep, None)[0]
    producers = producer_representatives(
        selected, baselines, baseline_signature
    )
    print(f"h209 producer sample profiles={len(producers)}", flush=True)
    profiles = collections.defaultdict(list)
    tested = 0
    for producer_index, item in enumerate(producers, 1):
        producer = item[4]
        for candidate in candidates(producer):
            tested += 1
            scored = gated_score(selected, baselines, candidate)
            if scored is None:
                continue
            values, signature = scored
            if (
                signature != baseline_signature
                and any(
                    value != baseline
                    for value, baseline in zip(values, baselines)
                )
            ):
                profiles[signature].append(
                    (*h207.objective(values), candidate.short(), candidate)
                )
        print(
            f"  producer {producer_index}/{len(producers)} "
            f"tested={tested}",
            flush=True,
        )
    representatives = sorted(min(items) for items in profiles.values())
    print(
        f"h209 sample: tested={tested} "
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
    print(f"h209 complete sweep: {len(final)} survivors")
    if final:
        validation = [*h207.joint_partitions("dense"), *focused]
        validation_baselines = h208.score_signature(validation, None)[0]
        surviving = []
        for item in final:
            candidate = item[4]
            values, _ = score_signature(validation, candidate)
            if all(
                h207.no_worse(value, baseline)
                for value, baseline in zip(values, validation_baselines)
            ):
                surviving.append(candidate)
        print(f"h209 dense/focused: {len(surviving)} survivors")
        for candidate in surviving:
            print(f"  {candidate.short()}")


if __name__ == "__main__":
    main()
