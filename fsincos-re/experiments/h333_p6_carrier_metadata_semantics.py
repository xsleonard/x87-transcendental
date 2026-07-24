#!/usr/bin/env python3
"""Test bounded P6 carrier/sticky interpretations at the sine-to-FMUL edge.

The Round-48 output-equivalent sine proxies all materialize as one legal
67-bit numeric carrier: the RN64 significand in carrier bits 66:3, minus one
carrier unit, so bits 2:0 are ``111``.  This pass asks whether those low bits
are all numerical or whether a suffix is unresolved producer metadata.

Two deliberately small model families are tested:

* scalar controls move the carrier by -7..+1 units and apply each established
  67-bit product materialization;
* interval models clear a suffix of one, two, or three low carrier bits and
  propagate the resulting half-open magnitude interval through FMUL.  The
  multiplier can retain the lower or upper product bound, jam a sticky low
  bit, or retain the first/last interior product unit.

These are complete arithmetic semantics, applied identically to both table
lanes.  No input identity, table cell, coordinate, or hardware result selects
an outcome.  The structured sweep is the discovery corpus; ``--candidate``
then gates a named result on the independent dense corpus.
"""

from __future__ import annotations

import argparse
import dataclasses

import h58_constraint_search as h58
import h60_round16_parity as h60
import h110_fsin_standalone as h110
import h207_tang_literal_fadd as h207
import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230
import h283_trig_sine_bias_selector as h283
import h322_trig_narrow_sine_fraction3_rule as h322
import h326_p6_tmp_sine_projection as h326


PRODUCT_MODES = ("chop67", "rn67", "away67", "odd67")
INTERVAL_POLICIES = (
    "lower",
    "lower-odd",
    "upper",
    "first-interior",
    "last-interior",
)


@dataclasses.dataclass(frozen=True)
class Candidate:
    kind: str
    parameter: int
    policy: str

    @property
    def name(self) -> str:
        if self.kind == "scalar":
            return f"scalar-{self.parameter:+d}-{self.policy}"
        return f"interval-low{self.parameter}-{self.policy}"


def candidates():
    for delta in range(-7, 2):
        for mode in PRODUCT_MODES:
            yield Candidate("scalar", delta, mode)
    for low_bits in (1, 2, 3):
        for policy in INTERVAL_POLICIES:
            yield Candidate("interval", low_bits, policy)


CANDIDATES = {candidate.name: candidate for candidate in candidates()}


def universal_carrier(point):
    proxy = h326.proxy_sine(point)
    carrier = h110.quantize(proxy, h110.Quant(67, "rn"))
    rn64 = h283.state_inputs(point)[-1]
    expected = h110.quantize(
        # One internal unit is 1/8 architectural ulp.
        h58.add_exact(
            rn64,
            (rn64[0] ^ 1, 1, rn64[2] + rn64[1].bit_length() - 67),
        ),
        h110.Quant(67, "rn"),
    )
    if carrier != expected or carrier[1] & 7 != 7:
        raise AssertionError((carrier, expected))
    return carrier


def magnitude_delta(value: h58.FP, delta: int) -> h58.FP:
    sign, significand, scale = value
    if significand + delta <= 0:
        raise ValueError((value, delta))
    return sign, significand + delta, scale


def upper_exclusive_product(cross: h58.FP, upper: h58.FP) -> h58.FP:
    exact = h58.mul_exact(cross, upper)
    result = h226.quantize(exact, "chop67")
    # If the open endpoint itself is exactly representable at this width,
    # values immediately below it truncate to the preceding retained unit.
    significand = exact[1]
    trailing = (significand & -significand).bit_length() - 1
    significant_width = significand.bit_length() - trailing
    if significant_width <= 67:
        result = magnitude_delta(result, -1)
    return result


def interval_product(cross: h58.FP, carrier: h58.FP, low_bits: int, policy: str):
    mask = (1 << low_bits) - 1
    if carrier[1] & mask != mask:
        raise AssertionError((carrier, low_bits))
    lower = carrier[0], carrier[1] & ~mask, carrier[2]
    upper = carrier[0], lower[1] + (1 << low_bits), carrier[2]
    low_product = h226.quantize(h58.mul_exact(cross, lower), "chop67")
    high_product = upper_exclusive_product(cross, upper)
    if low_product[0] != high_product[0] or low_product[2] != high_product[2]:
        raise AssertionError((low_product, high_product))
    if low_product[1] > high_product[1]:
        raise AssertionError((low_product, high_product))
    if policy == "lower":
        return low_product
    if policy == "upper":
        return high_product
    if policy == "lower-odd":
        return low_product[0], low_product[1] | 1, low_product[2]
    if policy == "first-interior":
        return magnitude_delta(low_product, int(low_product != high_product))
    if policy == "last-interior":
        return magnitude_delta(high_product, -int(low_product != high_product))
    raise ValueError(policy)


def p_product(cross: h58.FP, carrier: h58.FP, candidate: Candidate):
    if candidate.kind == "scalar":
        operand = magnitude_delta(carrier, candidate.parameter)
        return h226.quantize(h58.mul_exact(cross, operand), candidate.policy)
    return interval_product(
        cross, carrier, candidate.parameter, candidate.policy
    )


def local_value(point, cosine_lane: bool, candidate: Candidate):
    prepared = point.prepared.joint.observed.point
    _, cosine_tail = h230.state(point, h228.CANDIDATE)
    if cosine_lane:
        lead, cross = prepared.cos_t, prepared.sin_t
    else:
        lead, cross = prepared.sin_t, prepared.cos_t
    q_product = h226.quantize(
        h58.mul_exact(lead, cosine_tail), "odd67"
    )
    product = p_product(cross, universal_carrier(point), candidate)
    if cosine_lane:
        product = h58.neg(product)
    correction = h226.quantize(
        h58.add_exact(q_product, product), "away67"
    )
    return h58.add_exact(lead, correction)


def hidden_values(point, candidate: Candidate):
    sine = local_value(point, False, candidate)
    cosine = local_value(point, True, candidate)
    if point.prepared.joint.observed.point.raw.sign:
        sine = h58.neg(sine)
    return h60.rotate(
        (sine, cosine), point.prepared.joint.observed.signed_n
    )


def score(points, candidate: Candidate | None):
    totals = [h226.ZERO_JOINT, h226.ZERO_JOINT]
    changed = 0
    for index, point in enumerate(points):
        baseline_values = h322.hidden_values(point)
        baseline_metric = h226.metric_for(point, baseline_values)
        values = (
            baseline_values
            if candidate is None
            else hidden_values(point, candidate)
        )
        metric = h226.metric_for(point, values)
        split = int(not h207.h131.is_train(point.prepared.joint.observed))
        totals[split] = h226.add_metric(totals[split], metric)
        changed += values != baseline_values
        if index % 512 == 0:
            h230.state.cache_clear()
    return tuple(totals), changed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=("sweep", "dense"), default="sweep")
    parser.add_argument("--candidate", choices=tuple(CANDIDATES))
    args = parser.parse_args()
    points = h228.points(args.scope)
    baseline, _ = score(points, None)
    selected = (
        (CANDIDATES[args.candidate],)
        if args.candidate
        else tuple(CANDIDATES.values())
    )
    ranked = []
    for candidate in selected:
        values, changed = score(points, candidate)
        ranked.append(
            (
                h226.objective(values),
                h226.regressions(values, baseline),
                candidate.name,
                changed,
                values,
            )
        )
    ranked.sort()
    print(
        "h333 P6 carrier metadata semantics: "
        f"scope={args.scope} points={len(points)} "
        f"baseline={h226.objective(baseline)} candidates={len(ranked)}"
    )
    for objective, regressions, name, changed, values in ranked[:80]:
        print(
            f"  {name}: objective={objective} regressions={regressions} "
            f"changed-values={changed}/{len(points)} values={values}"
        )


if __name__ == "__main__":
    main()
