#!/usr/bin/env python3
"""Search product-local carry/sticky conditions around Round 49.

Round 49 normally retains one unit below the open upper product bound.  Of
its 13 paired residual lanes, 11 are reachable by selecting the adjacent
product unit instead.  This pass searches only arithmetic facts available at
that multiply: upper/lower interval span, normalization, discarded product
bits, retained bits, operand bits, and the following combine alignment.

Every atom is applied to all structured points and must be componentwise
non-regressing on both deterministic halves.  Input index and hardware
outcome are not features.
"""

from __future__ import annotations

import collections
import itertools

import h58_constraint_search as h58
import h60_round16_parity as h60
import h207_tang_literal_fadd as h207
import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230
import h283_trig_sine_bias_selector as h283
import h329_round48_product_selector as h329
import h333_p6_carrier_metadata_semantics as h333


DIRECTIONS = (-1, 1)
PAIR_ATOMS = 64
CANDIDATE = h333.CANDIDATES["interval-low1-last-interior"]


def adjusted_hidden_values(point, changed_lane: int, delta: int):
    prepared = point.prepared.joint.observed.point
    _, cosine_tail = h230.state(point, h228.CANDIDATE)
    outputs = []
    for local_lane in (0, 1):
        cosine_lane = bool(local_lane)
        if cosine_lane:
            lead, cross = prepared.cos_t, prepared.sin_t
        else:
            lead, cross = prepared.sin_t, prepared.cos_t
        q_product = h226.quantize(
            h58.mul_exact(lead, cosine_tail), "odd67"
        )
        product = h333.p_product(
            cross, h333.universal_carrier(point), CANDIDATE
        )
        if local_lane == changed_lane:
            product = product[0], product[1] + delta, product[2]
        if cosine_lane:
            product = h58.neg(product)
        correction = h226.quantize(
            h58.add_exact(q_product, product), "away67"
        )
        outputs.append(h58.add_exact(lead, correction))
    if prepared.raw.sign:
        outputs[0] = h58.neg(outputs[0])
    return h60.rotate(
        tuple(outputs), point.prepared.joint.observed.signed_n
    )


def low_bits(result, prefix: str, value: h58.FP, count: int = 12):
    result[f"{prefix}.width"] = value[1].bit_length()
    for bit in range(count):
        result[f"{prefix}.bit{bit}"] = (value[1] >> bit) & 1


def features(point, local_lane: int):
    prepared = point.prepared.joint.observed.point
    _, cosine_tail = h230.state(point, h228.CANDIDATE)
    if local_lane:
        lead, cross = prepared.cos_t, prepared.sin_t
    else:
        lead, cross = prepared.sin_t, prepared.cos_t
    carrier = h333.universal_carrier(point)
    lower = carrier[0], carrier[1] & ~1, carrier[2]
    upper = carrier[0], lower[1] + 2, carrier[2]
    exact_upper = h58.mul_exact(cross, upper)
    low_product = h226.quantize(
        h58.mul_exact(cross, lower), "chop67"
    )
    high_product = h333.upper_exclusive_product(cross, upper)
    product = h333.p_product(cross, carrier, CANDIDATE)
    q_product = h226.quantize(
        h58.mul_exact(lead, cosine_tail), "odd67"
    )
    result = {
        "interval.span": high_product[1] - low_product[1],
        "interval.current-from-high": high_product[1] - product[1],
        "multiply.normalization-high": int(
            exact_upper[1].bit_length()
            == cross[1].bit_length() + upper[1].bit_length()
        ),
        "multiply.shift": exact_upper[1].bit_length() - 67,
        "multiply.trailing-zeroes": (
            exact_upper[1] & -exact_upper[1]
        ).bit_length() - 1,
    }
    shift = result["multiply.shift"]
    remainder = (
        exact_upper[1] & ((1 << shift) - 1)
        if shift > 0
        else 0
    )
    result["multiply.discarded"] = int(bool(remainder))
    result["multiply.guard"] = (
        (exact_upper[1] >> (shift - 1)) & 1 if shift >= 1 else 0
    )
    result["multiply.round"] = (
        (exact_upper[1] >> (shift - 2)) & 1 if shift >= 2 else 0
    )
    result["multiply.sticky"] = int(
        bool(remainder & ((1 << (shift - 2)) - 1))
    ) if shift > 2 else 0
    for bit in range(20):
        position = shift - 1 - bit
        result[f"multiply.discard{bit}"] = (
            (exact_upper[1] >> position) & 1 if position >= 0 else 0
        )
        result[f"multiply.raw-low{bit}"] = (exact_upper[1] >> bit) & 1
    low_bits(result, "carrier", carrier)
    low_bits(result, "upper", upper)
    low_bits(result, "cross", cross)
    low_bits(result, "retained", high_product)
    low_bits(result, "q-product", q_product)
    result["combine.exponent-distance"] = abs(
        q_product[2] + q_product[1].bit_length()
        - product[2] - product[1].bit_length()
    )
    result["combine.sign-xor"] = q_product[0] ^ product[0] ^ local_lane
    return tuple(sorted(result.items()))


def main() -> None:
    points = h228.points("sweep")
    baselines = [h226.ZERO_JOINT, h226.ZERO_JOINT]
    rows = []
    for point in points:
        baseline = h226.metric_for(
            point, h333.hidden_values(point, CANDIDATE)
        )
        split = int(not h207.h131.is_train(point.prepared.joint.observed))
        baselines[split] = h329.add(baselines[split], baseline)
        for lane in (0, 1):
            atoms = features(point, lane)
            for direction in DIRECTIONS:
                metric = h226.metric_for(
                    point, adjusted_hidden_values(point, lane, direction)
                )
                delta = h329.subtract(metric, baseline)
                if delta != h226.ZERO_JOINT:
                    rows.append((split, direction, atoms, delta))
    baseline_tuple = tuple(baselines)
    totals = collections.defaultdict(
        lambda: [h226.ZERO_JOINT, h226.ZERO_JOINT]
    )
    active = collections.Counter()
    for split, direction, atoms, delta in rows:
        for atom in atoms:
            key = direction, atom
            totals[key][split] = h329.add(totals[key][split], delta)
            active[key] += 1
    ranked = []
    near = []
    for (direction, atom), deltas in totals.items():
        values = tuple(
            h329.add(baseline, delta)
            for baseline, delta in zip(baseline_tuple, deltas)
        )
        item = (
            h329.violation(values, baseline_tuple),
            h226.objective(values),
            direction,
            atom,
            active[direction, atom],
            values,
        )
        near.append(item)
        if item[0] == 0 and item[1] < h226.objective(baseline_tuple):
            ranked.append(item)
    ranked.sort(key=lambda item: (item[1], item[2], item[3]))
    print(
        "h339 Round-49 interval borrow selector: "
        f"points={len(points)} rows={len(rows)} "
        f"baseline={h226.objective(baseline_tuple)} "
        f"one-atom-survivors={len(ranked)}"
    )
    for item in ranked[:80]:
        print(
            f"  objective={item[1]} direction={item[2]:+d} "
            f"active={item[4]} {item[3][0]}={item[3][1]} "
            f"values={item[5]}"
        )
    if not ranked:
        print("closest one-atom candidates:")
        for item in sorted(near)[:40]:
            print(
                f"  violation={item[0]} objective={item[1]} "
                f"direction={item[2]:+d} active={item[4]} "
                f"{item[3][0]}={item[3][1]} values={item[5]}"
            )

    allowed = {
        direction: {
            item[3]
            for item in sorted(row for row in near if row[2] == direction)[
                :PAIR_ATOMS
            ]
        }
        for direction in DIRECTIONS
    }
    pair_totals = collections.defaultdict(
        lambda: [h226.ZERO_JOINT, h226.ZERO_JOINT]
    )
    pair_active = collections.Counter()
    for split, direction, atoms, delta in rows:
        selected = tuple(atom for atom in atoms if atom in allowed[direction])
        for pair in itertools.combinations(selected, 2):
            key = direction, pair
            pair_totals[key][split] = h329.add(
                pair_totals[key][split], delta
            )
            pair_active[key] += 1
    pair_ranked = []
    for (direction, pair), deltas in pair_totals.items():
        values = tuple(
            h329.add(baseline, delta)
            for baseline, delta in zip(baseline_tuple, deltas)
        )
        if not all(
            h329.no_worse(value, baseline)
            for value, baseline in zip(values, baseline_tuple)
        ):
            continue
        objective = h226.objective(values)
        if objective >= h226.objective(baseline_tuple):
            continue
        pair_ranked.append((
            objective,
            direction,
            pair,
            pair_active[direction, pair],
            values,
        ))
    pair_ranked.sort()
    print(f"two-atom-survivors={len(pair_ranked)}")
    for objective, direction, pair, count, values in pair_ranked[:80]:
        terms = " & ".join(f"{name}={value}" for name, value in pair)
        print(
            f"  objective={objective} direction={direction:+d} "
            f"active={count} {terms} values={values}"
        )


if __name__ == "__main__":
    main()
