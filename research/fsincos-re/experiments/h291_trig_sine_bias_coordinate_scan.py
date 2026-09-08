#!/usr/bin/env python3
"""Scan other physical shared-sine exponent/alignment coordinates.

Round 43 promotes bias 3 in the `(local top exponent=-5, FADD distance=13)`
bin.  This pass treats every other observed `(top exponent, distance)` pair as
one indivisible physical class and tests biases 0--8 there.  It scores all old
partitions plus h285; any survivor remains capture-required.
"""

from __future__ import annotations

import collections

import h58_constraint_search as h58
import h60_round16_parity as h60
import h79_table_state_bias as h79
import h218_fadd_residual_programs as h218
import h226_p6_full_sine_graph as h226
import h228_p6_four_term_c_parity as h228
import h230_p6_microop_materialization_search as h230
import h283_trig_sine_bias_selector as h283
import h287_trig_sine_bias_cegis as h287


ROUND43 = (-5, 13)
BIASES = tuple(range(9))


def coordinate(point):
    a, _, _, _, p_times_a, _, rn64 = h283.state_inputs(point)
    a_exponent = a[2] + a[1].bit_length() - 1
    p_exponent = p_times_a[2] + p_times_a[1].bit_length() - 1
    return (a_exponent, abs(a_exponent - p_exponent)), rn64


def hidden_values(point, sine):
    prepared = point.prepared.joint.observed.point
    _, cosine_tail = h230.state(point, h228.CANDIDATE)
    outputs = []
    for cosine_lane in (False, True):
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
        if cosine_lane:
            p_product = h58.neg(p_product)
        correction = h226.quantize(
            h58.add_exact(q_product, p_product), "away67"
        )
        outputs.append(h58.add_exact(lead, correction))
    if prepared.raw.sign:
        outputs[0] = h58.neg(outputs[0])
    return h60.rotate(tuple(outputs), point.prepared.joint.observed.signed_n)


def add_delta(value, delta):
    return tuple(
        tuple(old_item + change for old_item, change in zip(old, lane_delta))
        for old, lane_delta in zip(value, delta)
    )


def subtract_metric(left, right):
    return tuple(
        tuple(new - old for new, old in zip(new_lane, old_lane))
        for new_lane, old_lane in zip(left, right)
    )


def main() -> None:
    datasets = [*h218.datasets(), ("h285", h287.fresh_points())]
    baseline = []
    deltas = collections.defaultdict(
        lambda: [h226.ZERO_JOINT for _ in datasets]
    )
    populations = collections.Counter()
    changed = collections.Counter()
    for dataset_index, (_, points) in enumerate(datasets):
        total = h226.ZERO_JOINT
        for point in points:
            observed = point.prepared.joint.observed
            coord, rn64 = coordinate(point)
            current_bias = (
                4
                if observed.family != "wide"
                else 3
                if coord == ROUND43
                else 5
            )
            current_sine = h79.bias_toward_zero(rn64, current_bias)
            current_metric = h226.metric_for(
                point, hidden_values(point, current_sine)
            )
            total = h226.add_metric(total, current_metric)
            if observed.family != "wide" or coord == ROUND43:
                continue
            populations[coord] += 1
            for bias in BIASES:
                if bias == current_bias:
                    continue
                sine = h79.bias_toward_zero(rn64, bias)
                metric = h226.metric_for(point, hidden_values(point, sine))
                if metric == current_metric:
                    continue
                changed[coord, bias] += 1
                delta = subtract_metric(metric, current_metric)
                deltas[coord, bias][dataset_index] = add_delta(
                    deltas[coord, bias][dataset_index], delta
                )
        baseline.append(total)
    baseline_tuple = tuple(baseline)

    ranked = []
    for (coord, bias), partition_deltas in deltas.items():
        candidate = tuple(
            add_delta(value, delta)
            for value, delta in zip(baseline_tuple, partition_deltas)
        )
        ranked.append(
            (
                h226.regressions(candidate, baseline_tuple),
                h226.objective(candidate),
                coord,
                bias,
                populations[coord],
                changed[coord, bias],
                candidate,
            )
        )
    ranked.sort()
    print(
        "h291 coordinate scan: "
        f"datasets={len(datasets)} bins={len(populations)} "
        f"candidates={len(ranked)} baseline={h226.objective(baseline_tuple)}"
    )
    print("regression leaders:")
    for item in ranked[:40]:
        print(
            f"  regressions={item[0]} objective={item[1]} "
            f"coord={item[2]} bias={item[3]} "
            f"population={item[4]} changed={item[5]}"
        )
    print("objective leaders:")
    for item in sorted(ranked, key=lambda item: (item[1], item[0], item[2]))[:24]:
        print(
            f"  objective={item[1]} regressions={item[0]} "
            f"coord={item[2]} bias={item[3]} "
            f"population={item[4]} changed={item[5]}"
        )


if __name__ == "__main__":
    main()
