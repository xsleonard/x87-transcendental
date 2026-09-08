#!/usr/bin/env python3
"""Search physical low-bit phase maps for the Round-21 S correction.

h81 tested one retained/discarded bit at a time.  A truncated partial product
or accumulator, however, is selected by a multi-bit phase.  This pass fits
small 2..6-bit lookup tables on the even half of the dense capture and
requires them to be non-worse than the fixed Round-21 bias on the odd half
and every independent family capture.

The lookup inputs are the leading discarded bits or low retained bits of
specific reconstructed products and sums.  The master sweep is not read.
"""

from __future__ import annotations

import dataclasses

import h58_constraint_search as h58
import h79_table_state_bias as h79
import h81_table_bias_bit_search as h81


@dataclasses.dataclass(frozen=True)
class PhasePoint:
    phases: tuple[int, ...]
    costs: tuple[tuple[int, int, int], ...]


def discarded_phase(value: h58.FP, bits: int) -> int:
    shift = value[1].bit_length() - 64
    if shift <= 0:
        return 0
    if shift >= bits:
        return (value[1] >> (shift - bits)) & ((1 << bits) - 1)
    return (value[1] & ((1 << shift) - 1)) << (bits - shift)


def retained_phase(value: h58.FP, bits: int) -> int:
    rounded = h58.round_fp(value, 64, "rn")
    return rounded[1] & ((1 << bits) - 1)


def carriers(
    point: h58.PreparedPoint,
) -> tuple[tuple[str, h58.FP], ...]:
    m_product = h58.mul_exact(point.p, point.asq)
    m = h58.round_fp(m_product, 64, "rn")
    correction_product = h58.mul_exact(m, point.a)
    correction = h58.round_fp(correction_product, 64, "rn")
    sine_sum = h58.add_exact(point.a, correction)
    tail_product = h58.mul_exact(point.q, point.asq)
    one_plus_m = h58.fadd(h58.ONE, m, 64, "rn")
    factored_product = h58.mul_exact(point.a, one_plus_m)
    return (
        ("p*asq", m_product),
        ("m*a", correction_product),
        ("a+correction", sine_sum),
        ("a*(1+m)", factored_product),
        ("q*asq", tail_product),
        ("a", point.a),
        ("asq", point.asq),
        ("p", point.p),
        ("q", point.q),
        ("m", m),
        ("correction", correction),
    )


def feature_specs() -> tuple[tuple[str, str, int], ...]:
    specs = []
    for name in (
        "p*asq",
        "m*a",
        "a+correction",
        "a*(1+m)",
        "q*asq",
    ):
        for bits in range(2, 7):
            specs.append((name, "discarded", bits))
    for name in (
        "a",
        "asq",
        "p",
        "q",
        "m",
        "correction",
        "a+correction",
    ):
        for bits in range(2, 7):
            specs.append((name, "retained", bits))
    return tuple(specs)


SPECS = feature_specs()


def prepare(raw: list[h58.RawPoint]) -> list[PhasePoint]:
    result = []
    for item in raw:
        point = h58.prepare(item)
        by_name = dict(carriers(point))
        phases = []
        for name, kind, bits in SPECS:
            value = by_name[name]
            phases.append(
                discarded_phase(value, bits)
                if kind == "discarded"
                else retained_phase(value, bits)
            )
        result.append(
            PhasePoint(
                phases=tuple(phases),
                costs=tuple(
                    h81.mismatch_cost(point, numerator)
                    for numerator in range(9)
                ),
            )
        )
    return result


def sum_cost(
    points: list[PhasePoint],
    feature: int | None,
    biases: tuple[int, ...],
) -> tuple[int, int, int]:
    total = [0, 0, 0]
    for point in points:
        branch = 0 if feature is None else point.phases[feature]
        cost = point.costs[biases[branch]]
        for index in range(3):
            total[index] += cost[index]
    return tuple(total)


def fit(
    points: list[PhasePoint],
    feature: int,
    bits: int,
    fixed_bias: int,
) -> tuple[int, ...]:
    result = []
    for branch in range(1 << bits):
        selected = [
            point
            for point in points
            if point.phases[feature] == branch
        ]
        if not selected:
            result.append(fixed_bias)
            continue
        ranked = [
            (
                sum_cost(selected, None, (numerator,)),
                numerator,
            )
            for numerator in range(9)
        ]
        ranked.sort()
        result.append(ranked[0][1])
    return tuple(result)


def main() -> None:
    datasets = h79.load_datasets()
    for family, fixed_bias in (("narrow", 4), ("wide", 5)):
        family_raw = [
            (name, raw)
            for name, actual_family, raw in datasets
            if actual_family == family
        ]
        dense_name, dense_raw = family_raw[0]
        train_raw = [
            point
            for index, point in enumerate(dense_raw)
            if index % 2 == 0
        ]
        heldout_raw = [
            point
            for index, point in enumerate(dense_raw)
            if index % 2
        ]
        scored = [
            ("dense-train", prepare(train_raw)),
            ("dense-heldout", prepare(heldout_raw)),
            *[
                (name, prepare(raw))
                for name, raw in family_raw[1:]
            ],
        ]
        baselines = {
            name: sum_cost(
                points, None, (fixed_bias,)
            )
            for name, points in scored
        }
        survivors = []
        for feature, spec in enumerate(SPECS):
            bits = spec[2]
            biases = fit(
                scored[0][1],
                feature,
                bits,
                fixed_bias,
            )
            if len(set(biases)) == 1:
                continue
            results = {
                name: sum_cost(points, feature, biases)
                for name, points in scored
            }
            validation_names = [
                name for name, _ in scored if name != "dense-train"
            ]
            if not all(
                results[name] <= baselines[name]
                for name in validation_names
            ):
                continue
            validation_total = tuple(
                sum(results[name][index] for name in validation_names)
                for index in range(3)
            )
            survivors.append(
                (
                    validation_total,
                    spec,
                    biases,
                    results,
                )
            )
        survivors.sort(
            key=lambda row: (row[0], row[1], row[2])
        )
        print(
            f"{family}: fixed={fixed_bias}/32; "
            f"phase-features={len(SPECS)}; "
            f"survivors={len(survivors)}"
        )
        for _, spec, biases, results in survivors[:12]:
            print(
                f"  {spec[0]}.{spec[1]}[{spec[2]}]: "
                f"biases={','.join(map(str, biases))}"
            )
            for name, _ in scored:
                print(
                    f"    {name:14s} "
                    f"{results[name][0]}/{results[name][1]}/"
                    f"{results[name][2]} "
                    f"(fixed {baselines[name][0]}/"
                    f"{baselines[name][1]}/{baselines[name][2]})"
                )


if __name__ == "__main__":
    main()
