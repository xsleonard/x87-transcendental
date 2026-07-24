#!/usr/bin/env python3
"""Gate h329's leading multiplier predicate on a disjoint dense corpus.

The best structured-sweep conjunction changes the p-product magnitude by one
when the sine-FADD exponent distance is 14 and the carrier/cross product has
the low normalization form.  It removes five of 80 sweep residuals without a
component regression on either sweep half.  This pass applies the predicate
independently to both local reconstruction products and checks every affected
point in the much larger dense table capture.
"""

from __future__ import annotations

import argparse
import collections

import h58_constraint_search as h58
import h60_round16_parity as h60
import h110_fsin_standalone as h110
import h207_tang_literal_fadd as h207
import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230
import h291_trig_sine_bias_coordinate_scan as h291
import h322_trig_narrow_sine_fraction3_rule as h322
import h326_p6_tmp_sine_projection as h326


RULES = {
    "distance14-normalization-low": 1,
    "cell22-qtop-12": -1,
    "combine8-normalization-low": 1,
    "distance14-combine6": 1,
    "distance17-qtop-16": 1,
}


def product_features(point, local_lane: int, need_q: bool):
    prepared = point.prepared.joint.observed.point
    if local_lane:
        lead, cross = prepared.cos_t, prepared.sin_t
    else:
        lead, cross = prepared.sin_t, prepared.cos_t
    carrier = h110.quantize(
        h326.proxy_sine(point), h110.Quant(67, "rn")
    )
    exact_product = h58.mul_exact(cross, carrier)
    p_product = h226.quantize(
        h58.mul_exact(cross, h326.proxy_sine(point)), "chop67"
    )
    result = {
        "normalization-low": int(
            exact_product[1].bit_length()
            != cross[1].bit_length() + carrier[1].bit_length()
        ),
        "coordinate-distance": h291.coordinate(point)[0][1],
    }
    if need_q:
        _, cosine_tail = h230.state(point, h228.CANDIDATE)
        q_product = h226.quantize(
            h58.mul_exact(lead, cosine_tail), "odd67"
        )
        q_top = q_product[2] + q_product[1].bit_length() - 1
        p_top = p_product[2] + p_product[1].bit_length() - 1
        result["q-top"] = q_top
        result["combine-distance"] = abs(q_top - p_top)
    return result


def selected(point, local_lane: int, rule: str) -> bool:
    observed = point.prepared.joint.observed
    if rule == "distance14-normalization-low":
        values = product_features(point, local_lane, False)
        return (
            values["coordinate-distance"] == 14
            and values["normalization-low"] == 1
        )
    if rule == "cell22-qtop-12":
        if observed.point.cell != 22:
            return False
        values = product_features(point, local_lane, True)
        return observed.point.cell == 22 and values["q-top"] == -12
    if rule == "combine8-normalization-low":
        values = product_features(point, local_lane, True)
        return (
            values["combine-distance"] == 8
            and values["normalization-low"] == 1
        )
    if rule == "distance14-combine6":
        values = product_features(point, local_lane, False)
        if values["coordinate-distance"] != 14:
            return False
        values = product_features(point, local_lane, True)
        return (
            values["coordinate-distance"] == 14
            and values["combine-distance"] == 6
        )
    if rule == "distance17-qtop-16":
        values = product_features(point, local_lane, False)
        if values["coordinate-distance"] != 17:
            return False
        values = product_features(point, local_lane, True)
        return (
            values["coordinate-distance"] == 17
            and values["q-top"] == -16
        )
    raise ValueError(rule)


def local_value(point, cosine_lane: bool, direction: int, active: bool):
    prepared = point.prepared.joint.observed.point
    sine = h326.proxy_sine(point)
    _, cosine_tail = h230.state(point, h228.CANDIDATE)
    if cosine_lane:
        lead, cross = prepared.cos_t, prepared.sin_t
    else:
        lead, cross = prepared.sin_t, prepared.cos_t
    q_product = h226.quantize(
        h58.mul_exact(lead, cosine_tail), "odd67"
    )
    p_product = h226.quantize(
        h58.mul_exact(cross, sine), "chop67"
    )
    if active:
        p_product = (
            p_product[0],
            p_product[1] + direction,
            p_product[2],
        )
    if cosine_lane:
        p_product = h58.neg(p_product)
    correction = h226.quantize(
        h58.add_exact(q_product, p_product), "away67"
    )
    return h58.add_exact(lead, correction)


def hidden_values(point, direction: int, lane_selection):
    sine = local_value(point, False, direction, lane_selection[0])
    cosine = local_value(point, True, direction, lane_selection[1])
    if point.prepared.joint.observed.point.raw.sign:
        sine = h58.neg(sine)
    return h60.rotate(
        (sine, cosine), point.prepared.joint.observed.signed_n
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=("dense", "sweep"), default="dense")
    parser.add_argument("--rule", choices=tuple(RULES), default=next(iter(RULES)))
    parser.add_argument("--family", choices=("all", "narrow", "wide"), default="all")
    args = parser.parse_args()
    totals = {
        split: [h226.ZERO_JOINT, h226.ZERO_JOINT]
        for split in ("train", "held")
    }
    active = collections.Counter()
    changed = collections.Counter()
    for point_index, point in enumerate(h228.points(args.scope)):
        observed = point.prepared.joint.observed
        if args.family != "all" and observed.family != args.family:
            continue
        if (
            args.rule == "cell22-qtop-12"
            and observed.point.cell != 22
        ):
            continue
        required_distance = {
            "distance14-normalization-low": 14,
            "distance14-combine6": 14,
            "distance17-qtop-16": 17,
        }.get(args.rule)
        if (
            required_distance is not None
            and h291.coordinate(point)[0][1] != required_distance
        ):
            continue
        lane_selection = tuple(
            selected(point, lane, args.rule) for lane in (0, 1)
        )
        if not any(lane_selection):
            if point_index % 512 == 0:
                h230.state.cache_clear()
            continue
        split = "train" if h207.h131.is_train(observed) else "held"
        baseline = h226.metric_for(point, h322.hidden_values(point))
        candidate = h226.metric_for(
            point,
            hidden_values(point, RULES[args.rule], lane_selection),
        )
        totals[split][0] = h226.add_metric(totals[split][0], baseline)
        totals[split][1] = h226.add_metric(totals[split][1], candidate)
        for lane, value in enumerate(lane_selection):
            active[split, lane] += value
        changed[split] += candidate != baseline
        if point_index % 512 == 0:
            h230.state.cache_clear()
    print(
        "h330 product-rule gate: "
        f"scope={args.scope} family={args.family} rule={args.rule} "
        f"active={dict(sorted(active.items()))} "
        f"changed={dict(sorted(changed.items()))}"
    )
    for split in ("train", "held"):
        baseline, candidate = totals[split]
        print(f"  {split}: {baseline} -> {candidate}")
    baseline_values = tuple(totals[split][0] for split in ("train", "held"))
    candidate_values = tuple(totals[split][1] for split in ("train", "held"))
    print(
        f"  objective={h226.objective(baseline_values)} -> "
        f"{h226.objective(candidate_values)} "
        f"regressions={h226.regressions(candidate_values, baseline_values)}"
    )


if __name__ == "__main__":
    main()
