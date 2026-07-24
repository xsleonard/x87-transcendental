#!/usr/bin/env python3
"""Model the sine product as separately retained upper and bias products.

Round 49 is numerically equivalent to truncating ``cross*RN64`` and then
subtracting one retained product unit.  A literal unresolved-borrow account
is that the multiplier separately materializes the upper product and the
sub-ulp sine correction before their retained integer subtraction.

This pass tests the established four materialization classes independently
on those two magnitudes.  The correction is either the frozen Round-48
fraction (which may straddle one retained product unit) or a fixed carrier
fraction.  No point-dependent rule is added beyond the previously captured
producer fraction itself.
"""

from __future__ import annotations

import dataclasses

import h58_constraint_search as h58
import h60_round16_parity as h60
import h110_fsin_standalone as h110
import h207_tang_literal_fadd as h207
import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230
import h283_trig_sine_bias_selector as h283
import h326_p6_tmp_sine_projection as h326
import h333_p6_carrier_metadata_semantics as h333


A_MODES = ("chop67", "rn67", "away67", "odd67")
B_MODES = ("chop", "rn", "away", "odd")
BIAS_SOURCES = ("round48", "fixed21", "fixed29", "fixed32", "fixed40")
ROUND49 = h333.CANDIDATES["interval-low1-last-interior"]


@dataclasses.dataclass(frozen=True)
class Candidate:
    a_mode: str
    b_mode: str
    bias_source: str

    @property
    def name(self):
        return f"A-{self.a_mode}-B-{self.b_mode}-{self.bias_source}"


CANDIDATES = tuple(
    Candidate(a_mode, b_mode, bias_source)
    for bias_source in BIAS_SOURCES
    for a_mode in A_MODES
    for b_mode in B_MODES
)


def round_integer(value: h58.FP, scale: int, mode: str) -> int:
    if value[0]:
        raise ValueError(value)
    shift = scale - value[2]
    if shift <= 0:
        return value[1] << -shift
    top = value[1] >> shift
    remainder = value[1] & ((1 << shift) - 1)
    if not remainder:
        return top
    if mode == "chop":
        return top
    if mode == "away":
        return top + 1
    if mode == "odd":
        return top | 1
    if mode == "rn":
        half = 1 << (shift - 1)
        return top + int(remainder > half or (remainder == half and (top & 1)))
    raise ValueError(mode)


def bias(point, source: str):
    rn64 = h283.state_inputs(point)[-1]
    numerator = (
        h326.numerator(point)
        if source == "round48"
        else int(source.removeprefix("fixed"))
    )
    top = rn64[2] + rn64[1].bit_length() - 1
    return 0, numerator, top - 63 - 8


def product(point, cross: h58.FP, candidate: Candidate):
    rn64 = h283.state_inputs(point)[-1]
    upper = h226.quantize(
        h58.mul_exact(cross, rn64), candidate.a_mode
    )
    correction = h58.mul_exact(
        (0, cross[1], cross[2]), bias(point, candidate.bias_source)
    )
    correction_units = round_integer(
        correction, upper[2], candidate.b_mode
    )
    if correction_units >= upper[1]:
        raise AssertionError((upper, correction_units))
    return upper[0], upper[1] - correction_units, upper[2]


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
    p_product = product(point, cross, candidate)
    if cosine_lane:
        p_product = h58.neg(p_product)
    correction = h226.quantize(
        h58.add_exact(q_product, p_product), "away67"
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
        baseline_values = h333.hidden_values(point, ROUND49)
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
    points = h228.points("sweep")
    baseline, _ = score(points, None)
    ranked = []
    for candidate in CANDIDATES:
        values, changed = score(points, candidate)
        ranked.append((
            h226.objective(values),
            h226.regressions(values, baseline),
            candidate.name,
            changed,
            values,
        ))
    ranked.sort()
    print(
        "h342 decomposed sine product: "
        f"points={len(points)} baseline={h226.objective(baseline)}"
    )
    for objective, regressions, name, changed, values in ranked:
        print(
            f"  {name}: objective={objective} regressions={regressions} "
            f"changed-values={changed}/{len(points)} values={values}"
        )


if __name__ == "__main__":
    main()
