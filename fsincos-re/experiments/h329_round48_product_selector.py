#!/usr/bin/env python3
"""Search physical one-term selectors for the remaining p-product unit.

h328 shows that 78 of the 80 post-Round-48 paired residual lanes are exactly
reachable by changing the cross-table chop67 product by one magnitude unit.
This pass applies that change independently to the two local reconstruction
lanes and searches only pre-correction datapath features: route/family state,
the 67-bit shared-sine carrier, the table-cross operand, exact-product
normalization and GRS, retained product bits, and the q/p combine alignment.

A selector is eligible only when it improves both deterministic halves of the
complete structured table sweep componentwise.  Input index and hardware
outcome are not features.
"""

from __future__ import annotations

import collections
import itertools

import h58_constraint_search as h58
import h60_round16_parity as h60
import h110_fsin_standalone as h110
import h200_p5_fadd_bitvector as h200
import h206_p5_fadd_complete as h206
import h207_tang_literal_fadd as h207
import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230
import h283_trig_sine_bias_selector as h283
import h291_trig_sine_bias_coordinate_scan as h291
import h322_trig_narrow_sine_fraction3_rule as h322
import h326_p6_tmp_sine_projection as h326


Metric = tuple[tuple[int, int, int], tuple[int, int, int]]
ZERO = h226.ZERO_JOINT
DIRECTIONS = (-1, 1)
PAIR_ATOMS = 64


def add(left: Metric, right: Metric) -> Metric:
    return tuple(
        tuple(a + b for a, b in zip(old_lane, new_lane))
        for old_lane, new_lane in zip(left, right)
    )  # type: ignore[return-value]


def subtract(left: Metric, right: Metric) -> Metric:
    return tuple(
        tuple(a - b for a, b in zip(new_lane, old_lane))
        for new_lane, old_lane in zip(left, right)
    )  # type: ignore[return-value]


def no_worse(value: Metric, baseline: Metric) -> bool:
    return all(
        new <= old
        for new_lane, old_lane in zip(value, baseline)
        for new, old in zip(new_lane, old_lane)
    )


def violation(values, baselines) -> int:
    return sum(
        max(0, new - old)
        for value, baseline in zip(values, baselines)
        for new_lane, old_lane in zip(value, baseline)
        for new, old in zip(new_lane, old_lane)
    )


def local_value(point, cosine_lane: bool, changed_lane: int, delta: int):
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
    if int(cosine_lane) == changed_lane:
        p_product = (
            p_product[0], p_product[1] + delta, p_product[2]
        )
    if cosine_lane:
        p_product = h58.neg(p_product)
    correction = h226.quantize(
        h58.add_exact(q_product, p_product), "away67"
    )
    return h58.add_exact(lead, correction)


def hidden_values(point, changed_lane: int, delta: int):
    sine = local_value(point, False, changed_lane, delta)
    cosine = local_value(point, True, changed_lane, delta)
    if point.prepared.joint.observed.point.raw.sign:
        sine = h58.neg(sine)
    return h60.rotate(
        (sine, cosine), point.prepared.joint.observed.signed_n
    )


def low_bits(result: dict[str, int], prefix: str, value: h58.FP):
    result[f"{prefix}.sign"] = value[0]
    result[f"{prefix}.width"] = value[1].bit_length()
    result[f"{prefix}.top-exponent"] = (
        value[2] + value[1].bit_length() - 1
    )
    for bit in range(12):
        result[f"{prefix}.bit{bit}"] = (value[1] >> bit) & 1


def producer_features(point):
    a, _, _, _, p_times_a, exact_sum, rn64 = h283.state_inputs(point)
    left = h200.normalized_bus(a)
    right = h200.normalized_bus(p_times_a)
    result = {}
    for mode in h206.MODES:
        for normalize in (False, True):
            bus, trace = h206.fadd(left, right, mode, normalize=normalize)
            prefix = f"producer.{mode}.{'norm' if normalize else 'raw'}"
            result[f"{prefix}.exponent-parity"] = bus.exponent & 1
            result[f"{prefix}.exponent-mod4"] = bus.exponent & 3
            for bit in range(12):
                result[f"{prefix}.bit{bit}"] = (bus.word >> bit) & 1
    comparison = h206.compare_magnitude(left, right)
    big, small = (left, right) if comparison > 0 else (right, left)
    difference = big.exponent - small.exponent
    shifted, discarded = h200.shift_right(small.word << 1, difference)
    jammed = shifted | int(discarded)
    minuend = big.word << 1
    result["producer.align.discarded"] = int(discarded)
    for bit in range(12):
        result[f"producer.align.shifted.bit{bit}"] = (shifted >> bit) & 1
        result[f"producer.align.jammed.bit{bit}"] = (jammed >> bit) & 1
        result[f"producer.align.raw.bit{bit}"] = (
            (minuend - jammed) >> bit
        ) & 1
        if bit:
            mask = (1 << bit) - 1
            result[f"producer.align.borrow-into{bit}"] = int(
                (minuend & mask) < (jammed & mask)
            )
    for name, value in (("sum", exact_sum), ("rn64", rn64)):
        low_bits(result, f"producer.{name}", value)
    return result


def features(point, local_lane: int, producer=None):
    observed = point.prepared.joint.observed
    prepared = observed.point
    cosine_lane = bool(local_lane)
    if cosine_lane:
        lead, cross = prepared.cos_t, prepared.sin_t
    else:
        lead, cross = prepared.sin_t, prepared.cos_t
    sine = h326.proxy_sine(point)
    carrier = h110.quantize(sine, h110.Quant(67, "rn"))
    _, cosine_tail = h230.state(point, h228.CANDIDATE)
    q_product = h226.quantize(
        h58.mul_exact(lead, cosine_tail), "odd67"
    )
    exact_product = h58.mul_exact(cross, carrier)
    p_product = h226.quantize(exact_product, "chop67")
    if cosine_lane:
        p_product = h58.neg(p_product)
    result = {
        "route.reduced": int(observed.source == "reduced"),
        "family.wide": int(observed.family == "wide"),
        "table.cell": prepared.cell,
        "quadrant.bit0": observed.signed_n & 1,
        "quadrant.bit1": (observed.signed_n >> 1) & 1,
        "input.sign": prepared.raw.sign,
        "residual.sign": prepared.a[0],
        "coordinate.top": h291.coordinate(point)[0][0],
        "coordinate.distance": h291.coordinate(point)[0][1],
    }
    result.update(producer if producer is not None else producer_features(point))
    low_bits(result, "carrier", carrier)
    low_bits(result, "cross", cross)
    low_bits(result, "q-product", q_product)
    low_bits(result, "p-product", p_product)
    shift = exact_product[1].bit_length() - 67
    remainder = (
        exact_product[1] & ((1 << shift) - 1)
        if shift > 0
        else 0
    )
    result["multiply.normalization-high"] = int(
        exact_product[1].bit_length()
        == cross[1].bit_length() + carrier[1].bit_length()
    )
    result["multiply.guard"] = (
        (exact_product[1] >> (shift - 1)) & 1 if shift >= 1 else 0
    )
    result["multiply.round"] = (
        (exact_product[1] >> (shift - 2)) & 1 if shift >= 2 else 0
    )
    result["multiply.sticky"] = int(
        bool(remainder & ((1 << (shift - 2)) - 1))
    ) if shift > 2 else 0
    for bit in range(10):
        position = shift - 1 - bit
        result[f"multiply.discard{bit}"] = (
            (exact_product[1] >> position) & 1
            if position >= 0
            else 0
        )
    result["combine.exponent-distance"] = abs(
        q_product[2] + q_product[1].bit_length()
        - p_product[2] - p_product[1].bit_length()
    )
    result["combine.sign-xor"] = q_product[0] ^ p_product[0]
    return result


def main() -> None:
    points = h228.points("sweep")
    baselines = [ZERO, ZERO]
    rows = []
    changed = collections.Counter()
    for point in points:
        baseline_metric = h226.metric_for(point, h322.hidden_values(point))
        split = int(not h207.h131.is_train(point.prepared.joint.observed))
        baselines[split] = add(baselines[split], baseline_metric)
        producer = producer_features(point)
        for local_lane in (0, 1):
            lane_features = features(point, local_lane, producer)
            atoms = tuple(sorted(lane_features.items()))
            for direction in DIRECTIONS:
                metric = h226.metric_for(
                    point, hidden_values(point, local_lane, direction)
                )
                delta = subtract(metric, baseline_metric)
                if delta == ZERO:
                    continue
                changed[direction] += 1
                rows.append((split, direction, atoms, delta))
    baseline_tuple = tuple(baselines)
    totals = collections.defaultdict(lambda: [ZERO, ZERO])
    active = collections.Counter()
    for split, direction, atoms, delta in rows:
        for atom in atoms:
            key = direction, atom
            totals[key][split] = add(totals[key][split], delta)
            active[key] += 1

    ranked = []
    atom_ranked = []
    for (direction, atom), deltas in totals.items():
        values = tuple(
            add(baseline, delta)
            for baseline, delta in zip(baseline_tuple, deltas)
        )
        atom_ranked.append(
            (
                violation(values, baseline_tuple),
                h226.objective(values),
                direction,
                atom,
                active[direction, atom],
                values,
            )
        )
        if not all(
            no_worse(value, baseline)
            for value, baseline in zip(values, baseline_tuple)
        ):
            continue
        objective = h226.objective(values)
        if objective >= h226.objective(baseline_tuple):
            continue
        ranked.append(
            (objective, direction, atom, active[direction, atom], values)
        )
    ranked.sort()
    print(
        "h329 Round-48 p-product selector: "
        f"points={len(points)} rows={len(rows)} changed={dict(changed)} "
        f"baseline={h226.objective(baseline_tuple)}"
    )
    print(f"componentwise one-atom survivors={len(ranked)}")
    for objective, direction, atom, count, values in ranked[:80]:
        print(
            f"  objective={objective} direction={direction:+d} "
            f"active={count} {atom[0]}={atom[1]} values={values}"
        )
    atom_ranked.sort()
    print("closest one-atom candidates:")
    for violation_count, objective, direction, atom, count, values in atom_ranked[:40]:
        print(
            f"  violation={violation_count} objective={objective} "
            f"direction={direction:+d} active={count} "
            f"{atom[0]}={atom[1]} values={values}"
        )

    allowed = {
        direction: {
            item[3]
            for item in sorted(
                (row for row in atom_ranked if row[2] == direction)
            )[:PAIR_ATOMS]
        }
        for direction in DIRECTIONS
    }
    pair_totals = collections.defaultdict(lambda: [ZERO, ZERO])
    pair_active = collections.Counter()
    for split, direction, atoms, delta in rows:
        selected = tuple(atom for atom in atoms if atom in allowed[direction])
        for pair in itertools.combinations(selected, 2):
            key = direction, pair
            pair_totals[key][split] = add(pair_totals[key][split], delta)
            pair_active[key] += 1
    pair_ranked = []
    pair_near = []
    for (direction, pair), deltas in pair_totals.items():
        values = tuple(
            add(baseline, delta)
            for baseline, delta in zip(baseline_tuple, deltas)
        )
        item = (
            violation(values, baseline_tuple),
            h226.objective(values),
            direction,
            pair,
            pair_active[direction, pair],
            values,
        )
        pair_near.append(item)
        if (
            item[0] == 0
            and item[1] < h226.objective(baseline_tuple)
        ):
            pair_ranked.append(item)
    pair_ranked.sort(key=lambda item: (item[1], item[2], item[3]))
    print(f"componentwise two-atom survivors={len(pair_ranked)}")
    for _, objective, direction, pair, count, values in pair_ranked[:80]:
        terms = " & ".join(f"{name}={value}" for name, value in pair)
        print(
            f"  objective={objective} direction={direction:+d} "
            f"active={count} {terms} values={values}"
        )
    if not pair_ranked:
        print("closest two-atom candidates:")
        for item in sorted(pair_near)[:40]:
            terms = " & ".join(
                f"{name}={value}" for name, value in item[3]
            )
            print(
                f"  violation={item[0]} objective={item[1]} "
                f"direction={item[2]:+d} active={item[4]} "
                f"{terms} values={item[5]}"
            )


if __name__ == "__main__":
    main()
