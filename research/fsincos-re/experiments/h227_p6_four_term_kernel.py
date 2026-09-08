#!/usr/bin/env python3
"""Test the reconstructed P6 four-term table polynomial against captures.

The P6 operation graph uses four-term sine/cosine kernels after table
reduction for every cell.  The existing empirical model instead uses the P5
six-term kernels for the wide cells.  This pass changes only that structural
choice and separately tests the P6 highest-degree sine coefficient's
payload-bit-60 difference from the P5 value.  It retains the current
equivalent materializations so that a gross structural improvement or
regression is visible before a larger search.
"""

from __future__ import annotations

import argparse
import dataclasses
import functools

import h58_constraint_search as h58
import h79_table_state_bias as h79
import h110_fsin_standalone as h110
import h134_fsin_table_per_edge_search as h134
import h136_tang_reconstruction_search as h136
import h207_tang_literal_fadd as h207
import h218_fadd_residual_programs as h218
import h226_p6_full_sine_graph as h226


P6_S4_C9_DELTA = -(1 << 60)
RN64 = h110.Quant(64, "rn")
P6_GRAPH = h226.Candidate(
    sine_state="exact",
    cosine_state="exact",
    lead_constant="rn64",
    cross_constant="exact",
    q_product="chop67",
    p_product="exact",
    correction="rn67",
)


def coefficient(row: int, quant: h110.Quant, adjust_p6_c9: bool) -> h58.FP:
    raw = h58.ROM[row]
    delta = P6_S4_C9_DELTA if adjust_p6_c9 and row == 172 else 0
    return h110.quantize((raw[0], raw[1] + delta, raw[2]), quant)


def horner(
    rows: tuple[int, ...],
    square: h58.FP,
    coefficients: tuple[h110.Quant, ...],
    products: tuple[h110.Quant, ...],
    sums: tuple[h110.Quant, ...],
    adjust_p6_c9: bool,
) -> h58.FP:
    value = coefficient(rows[0], coefficients[0], adjust_p6_c9)
    for index, row in enumerate(rows[1:]):
        product = h110.quantize(
            h58.mul_exact(value, square), products[index]
        )
        value = h110.quantize(
            h58.add_exact(
                product,
                coefficient(row, coefficients[index + 1], adjust_p6_c9),
            ),
            sums[index],
        )
    return value


@functools.lru_cache(maxsize=None)
def p6_state(point: h207.Point, adjust_p6_c9: bool) -> h136.State:
    prepared = point.prepared
    observed = prepared.joint.observed
    schedule = prepared.base
    p = horner(
        h58.S4,
        prepared.square,
        schedule.p_coefficients,
        schedule.p_products,
        schedule.p_sums,
        adjust_p6_c9,
    )
    q = horner(
        h58.C4,
        prepared.square,
        schedule.q_coefficients,
        schedule.q_products,
        schedule.q_sums,
        adjust_p6_c9,
    )
    p_square = h110.quantize(
        h58.mul_exact(p, prepared.square), RN64
    )
    correction = h110.quantize(
        h58.mul_exact(p_square, observed.point.a), RN64
    )
    sine_a = h110.quantize(
        h58.add_exact(observed.point.a, correction), RN64
    )
    sine_a = h79.bias_toward_zero(sine_a, 5)
    sine_correction = h58.add_exact(sine_a, h58.neg(observed.point.a))
    cosine_tail = h110.quantize(
        h58.mul_exact(q, prepared.square), RN64
    )
    return h136.State(observed.point.a, sine_correction, cosine_tail)


def local_value(
    point: h207.Point,
    cosine_lane: bool,
    candidate: h226.Candidate,
    adjust_p6_c9: bool,
) -> h58.FP:
    prepared = point.prepared.joint.observed.point
    state = p6_state(point, adjust_p6_c9)
    sine_a = h226.quantize(
        h58.add_exact(state.residual, state.sine_correction),
        candidate.sine_state,
    )
    cosine_tail = h226.quantize(
        state.cosine_tail, candidate.cosine_state
    )
    if cosine_lane:
        lead, cross = prepared.cos_t, prepared.sin_t
    else:
        lead, cross = prepared.sin_t, prepared.cos_t
    q_product = h226.quantize(
        h58.mul_exact(
            h226.quantize(lead, candidate.lead_constant), cosine_tail
        ),
        candidate.q_product,
    )
    p_product = h226.quantize(
        h58.mul_exact(
            h226.quantize(cross, candidate.cross_constant), sine_a
        ),
        candidate.p_product,
    )
    if cosine_lane:
        p_product = h58.neg(p_product)
    correction = h226.quantize(
        h58.add_exact(q_product, p_product), candidate.correction
    )
    return h58.add_exact(lead, correction)


def hidden_values(
    point: h207.Point,
    candidate: h226.Candidate,
    adjust_p6_c9: bool,
) -> tuple[h58.FP, h58.FP]:
    sine = local_value(point, False, candidate, adjust_p6_c9)
    cosine = local_value(point, True, candidate, adjust_p6_c9)
    if point.prepared.joint.observed.point.raw.sign:
        sine = h58.neg(sine)
    return h226.h60.rotate(
        (sine, cosine), point.prepared.joint.observed.signed_n
    )


def score(datasets, candidate: h226.Candidate, adjust_p6_c9: bool):
    totals = []
    for _, points in datasets:
        total = h226.ZERO_JOINT
        for point in points:
            total = h226.add_metric(
                total,
                h226.metric_for(
                    point,
                    hidden_values(point, candidate, adjust_p6_c9),
                ),
            )
        totals.append(total)
    return tuple(totals)


def search(datasets, width: int, rounds: int) -> list[h226.Candidate]:
    selected = [h226.sample_dataset(name, points) for name, points in datasets]
    baselines = h226.score(selected, None)
    beam = [P6_GRAPH]
    ranked_by_candidate = {}
    for round_index in range(1, rounds + 1):
        tested = 0
        for candidate in h226.expand(beam):
            if candidate in ranked_by_candidate:
                continue
            values = score(selected, candidate, True)
            ranked_by_candidate[candidate] = (
                h226.regressions(values, baselines),
                h226.objective(values),
                candidate.short(),
                candidate,
            )
            tested += 1
        ranked = sorted(ranked_by_candidate.values())
        beam = [item[3] for item in ranked[:width]]
        print(
            f"search round {round_index}: new={tested} "
            f"seen={len(ranked_by_candidate)} best={ranked[0][:3]}",
            flush=True,
        )
    return beam


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--search", action="store_true")
    parser.add_argument("--width", type=int, default=16)
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()
    datasets = h218.datasets()
    baseline = h226.score(datasets, None)
    print(f"current objective={h226.objective(baseline)}")
    for adjust_p6_c9 in (False, True):
        values = score(datasets, h226.CURRENT, adjust_p6_c9)
        print(
            f"P6 S4/C4 adjusted_c9={adjust_p6_c9} "
            f"objective={h226.objective(values)} "
            f"regressions={h226.regressions(values, baseline)}"
        )
        for (name, _), value, old in zip(datasets, values, baseline):
            if value != old:
                print(f"  {name}: {old} -> {value}")
    p6_values = score(datasets, P6_GRAPH, True)
    print(
        f"P6 graph objective={h226.objective(p6_values)} "
        f"regressions={h226.regressions(p6_values, baseline)} "
        f"{P6_GRAPH.short()}"
    )
    if args.search:
        beam = search(datasets, args.width, args.rounds)
        selected = [
            h226.sample_dataset(name, points)
            for name, points in datasets
        ]
        selected_baseline = h226.score(selected, None)
        complete = []
        for candidate in beam:
            selected_values = score(selected, candidate, True)
            if not h226.no_worse(selected_values, selected_baseline):
                continue
            values = score(datasets, candidate, True)
            if not h226.no_worse(values, baseline):
                continue
            complete.append((
                h226.regressions(values, baseline),
                h226.objective(values),
                candidate.short(),
            ))
        complete.sort()
        print("complete finalists:")
        for item in complete:
            print(f"  {item}")


if __name__ == "__main__":
    main()
