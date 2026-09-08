#!/usr/bin/env python3
"""Map the remaining standalone-FSIN table residue onto Tang/P5 state.

The current hidden value uses h135's path-aware terminal coefficients and
h143's direct/reduced P5 route for narrow cells.  RN/RD/RU observations are
inverted into a magnitude interval.  The pass reports correction direction
by family/source/quadrant/cell and correlates it with the exact Tang linear,
C*p, Sj*q, nonlinear-sum, and RN67 correction state.
"""

from __future__ import annotations

import collections
import fractions

import h58_constraint_search as h58
import h110_fsin_standalone as h110
import h131_fsin_table_c1_search as h131
import h134_fsin_table_per_edge_search as h134
import h135_fsin_table_terminal_discriminator as h135
import h136_tang_reconstruction_search as h136
import h139_p5_fmul_route_search as h139
import h143_p5_fmul_c_parity as h143
import h146_fsin_cosine_boolean_search as h146
import h155_fsin_cosine_state_tomography as h155


Fraction = fractions.Fraction


def hidden(point: h131.Observed) -> h58.FP:
    if point.family == "narrow":
        route = h143.SCHEDULE.route(
            point.source == "reduced"
        )
        return h139.hidden_value(point, route)
    return h134.hidden_value(
        point, h135.path_candidate(point)
    )


def interval(
    point: h131.Observed,
) -> tuple[Fraction, Fraction]:
    rn, rd, ru = (
        h155.output_fraction(value)
        for value in point.outputs
    )
    low, high = sorted((rd, ru))
    if low != high:
        midpoint = (low + high) / 2
        if rn == low:
            high = midpoint
        elif rn == high:
            low = midpoint
        else:
            raise ValueError("RN does not bisect RD/RU")
    return low, high


def magnitude_relation(
    point: h131.Observed, value: h58.FP
) -> tuple[str, Fraction]:
    low, high = interval(point)
    current = h155.fp_fraction(value)
    if current < 0:
        current, low, high = -current, -high, -low
    midpoint = (low + high) / 2
    directions = set()
    for index, rc in enumerate(h58.RCS):
        predicted = h58.x87_round(value, rc)
        expected = point.outputs[index]
        if predicted == expected:
            continue
        predicted_magnitude = abs(
            h155.output_fraction(predicted)
        )
        expected_magnitude = abs(
            h155.output_fraction(expected)
        )
        directions.add(
            "need-up"
            if expected_magnitude > predicted_magnitude
            else "need-down"
        )
    if len(directions) > 1:
        return "mixed", midpoint - current
    return (
        next(iter(directions)) if directions else "inside",
        midpoint - current,
    )


def lane_state(
    point: h131.Observed,
) -> tuple[
    h136.State,
    h58.FP,
    h58.FP,
    bool,
    h139.Route | None,
]:
    prepared = point.point
    state = h136.standalone_state(
        prepared, h135.path_candidate(point)
    )
    quadrant = point.signed_n & 3
    if quadrant & 1:
        lead, cross, subtract = (
            prepared.cos_t,
            prepared.sin_t,
            True,
        )
    else:
        lead, cross, subtract = (
            prepared.sin_t,
            prepared.cos_t,
            False,
        )
    route = (
        h143.SCHEDULE.route(point.source == "reduced")
        if point.family == "narrow"
        else None
    )
    return state, lead, cross, subtract, route


def routed_product_exact(
    constant: h58.FP,
    value: h58.FP,
    route: h139.Route | None,
) -> h58.FP:
    if route is None:
        return h58.mul_exact(constant, value)
    if route.constant_bus == "x":
        x_value, y_value = constant, value
    else:
        x_value, y_value = value, constant
    x_value = h139.quantize(x_value, 67, route.x_mode)
    y_value = h139.quantize(y_value, 64, route.y_mode)
    return h58.mul_exact(x_value, y_value)


def features(point: h131.Observed) -> dict[str, int]:
    state, lead, cross, subtract, route = lane_state(point)
    linear = h58.mul_exact(cross, state.residual)
    p_exact = routed_product_exact(
        cross, state.sine_correction, route
    )
    p_product = (
        h139.p5_fmul(
            cross, state.sine_correction, route
        )
        if route is not None
        else h110.quantize(
            p_exact, h110.Quant(64, "rn")
        )
    )
    q_product = h58.mul_exact(
        lead, state.cosine_tail
    )
    if subtract:
        linear = h58.neg(linear)
        p_product = h58.neg(p_product)
        p_exact = h58.neg(p_exact)
    nonlinear = h58.add_exact(q_product, p_product)
    correction_exact = h58.add_exact(linear, nonlinear)
    result = {
        "cell": point.point.cell,
        "wide": int(point.point.wide),
        "reduced": int(point.source == "reduced"),
        "quadrant": point.signed_n & 3,
        "a.low3": point.point.a[1] & 7,
        "lead.low3": lead[1] & 7,
        "cross.low3": cross[1] & 7,
        "pstate.low3": state.sine_correction[1] & 7,
        "qstate.low3": state.cosine_tail[1] & 7,
    }
    for name, exact, quant, left, right in (
        (
            "linear",
            linear,
            h110.Quant(67, "rn"),
            cross,
            state.residual,
        ),
        (
            "p-product",
            p_exact,
            h110.Quant(64, "rn"),
            cross,
            state.sine_correction,
        ),
        (
            "q-product",
            q_product,
            h110.Quant(67, "rn"),
            lead,
            state.cosine_tail,
        ),
        (
            "correction",
            correction_exact,
            h110.Quant(67, "rn"),
            None,
            None,
        ),
    ):
        result.update(
            h146.rounded_features(
                name, exact, quant, left, right
            )
        )
    result.update(
        h146.rounded_features(
            "nonlinear",
            nonlinear,
            h110.Quant(67, "rn"),
        )
    )
    return result


def main() -> None:
    points = h131.load_dataset(
        "sweep", h131.INPUTS / "sweep_inputs.txt"
    )
    relations: collections.Counter[str] = collections.Counter()
    deltas: collections.Counter[int] = collections.Counter()
    groups: dict[
        tuple[str, str, int, int],
        collections.Counter[str],
    ] = collections.defaultdict(collections.Counter)
    feature_counts: dict[
        tuple[str, int], collections.Counter[str]
    ] = collections.defaultdict(collections.Counter)
    for point in points:
        kind, delta = magnitude_relation(
            point, hidden(point)
        )
        relations[kind] += 1
        deltas[h155.rounded_scaled(delta, 67)] += 1
        key = (
            point.family,
            point.source,
            point.signed_n & 3,
            point.point.cell,
        )
        groups[key][kind] += 1
        for name, value in features(point).items():
            feature_counts[(name, value)][kind] += 1
    print(
        f"h169 table sweep: n={len(points)} "
        f"relations={dict(relations)}"
    )
    print(
        "  hidden-magnitude midpoint delta, units 2^-67: "
        + " ".join(
            f"{value:+d}:{count}"
            for value, count in deltas.most_common(20)
        )
    )
    print("  outside states by family/source/quadrant/cell:")
    ranked_groups = sorted(
        groups.items(),
        key=lambda item: (
            -item[1]["need-up"] - item[1]["need-down"],
            item[0],
        ),
    )
    for key, counts in ranked_groups:
        outside = counts["need-up"] + counts["need-down"]
        if outside:
            print(
                f"    {key}: outside={outside} "
                f"{dict(counts)}"
            )
    ranked = []
    for (name, value), counts in feature_counts.items():
        outside = counts["need-up"] + counts["need-down"]
        selected = sum(counts.values())
        if outside < 3:
            continue
        dominant = max(
            counts["need-up"], counts["need-down"]
        )
        purity = dominant / outside
        rate = outside / selected
        ranked.append(
            (
                -(purity * rate),
                -dominant,
                selected,
                name,
                value,
                counts,
            )
        )
    ranked.sort()
    print("  strongest Tang/P5 state partitions:")
    for _, _, selected, name, value, counts in ranked[:30]:
        print(
            f"    {name}={value}: selected={selected} "
            f"{dict(counts)}"
        )


if __name__ == "__main__":
    main()
