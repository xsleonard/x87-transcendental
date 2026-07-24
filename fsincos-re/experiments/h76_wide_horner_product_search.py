#!/usr/bin/env python3
"""Search product-before-add materialization in the wide table Horner DAG."""

from __future__ import annotations

import argparse
import dataclasses
import pathlib

import h58_constraint_search as h58
import h59_discriminator as h59
import h70_poly_outlier_forensics as h70


ROOT = pathlib.Path(__file__).resolve().parents[1]
DENSE_CAPTURE = ROOT / "capture-kit-captures" / "pentiumII"
H59_CAPTURE = (
    ROOT / "capture-kit-captures" / "skylake-h59-constraints"
)
H67_CAPTURE = (
    ROOT / "capture-kit-captures" / "skylake-h67-wide-producer"
)
H67_INPUTS = (
    ROOT / "capture-kit" / "inputs" / "constraint_wide_producer_h67.txt"
)


@dataclasses.dataclass(frozen=True)
class Variant:
    edge: int
    bits: int
    mode: str

    def short(self) -> str:
        if self.edge < 0:
            return "baseline-separate-rn64"
        edge = "all" if self.edge == 0 else str(self.edge)
        return f"edge={edge}:product-{self.mode}{self.bits}->add-rn64"


BASE = Variant(-1, 64, "rn")


def horner(
    rows: tuple[int, ...],
    asq: h58.FP,
    variant: Variant,
) -> h58.FP:
    if variant.edge < 0:
        return h58.horner(rows, asq, h58.BASE_PRODUCER)
    value = h58.coefficient(rows[0], h58.BASE_PRODUCER)
    for step, row in enumerate(rows[1:], 1):
        product = h58.mul_exact(value, asq)
        if variant.edge in (0, step):
            product = h70.pre_round(
                product, variant.bits, variant.mode
            )
        else:
            product = h58.round_fp(product, 64, "rn")
        value = h58.fadd(
            product,
            h58.coefficient(row, h58.BASE_PRODUCER),
            64,
            "rn",
        )
    return value


def values(
    point: h58.PreparedPoint,
    chain: str,
    variant: Variant,
) -> tuple[h58.FP, h58.FP]:
    if chain in ("p", "both"):
        point = dataclasses.replace(
            point, p=horner(h58.S6, point.asq, variant)
        )
    if chain in ("q", "both"):
        point = dataclasses.replace(
            point, q=horner(h58.C6, point.asq, variant)
        )
    return h58.table_tail(point, h58.BASE)


def score(
    points: list[h58.PreparedPoint],
    chain: str,
    variant: Variant,
) -> h58.Score:
    result = h58.Score(total_outputs=2 * len(points))
    for point in points:
        predicted = values(point, chain, variant)
        for side, value in enumerate(predicted):
            output_missed = False
            for rc_index, rc in enumerate(h58.RCS):
                mismatch = (
                    h58.x87_round(value, rc)
                    != point.raw.hw[rc_index][side]
                )
                result.mode_misses += mismatch
                result.rn_misses += mismatch if rc == "rn" else 0
                output_missed |= mismatch
            result.constrained_output_misses += output_missed
    return result


def rank(result: h58.Score) -> tuple[int, int, int]:
    return (
        int(result.mode_misses),
        int(result.constrained_output_misses),
        int(result.rn_misses),
    )


def variants() -> list[Variant]:
    return [
        Variant(edge, bits, mode)
        for edge in (0, 5)
        for bits in range(64, 73)
        for mode in ("rn", "chop", "away", "odd")
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--chain", choices=("p", "q", "both"), required=True
    )
    args = parser.parse_args()
    dense_raw = [
        raw
        for raw in h58.load_points(DENSE_CAPTURE)
        if raw.exponent == -1
    ]
    h59_raw = h59.load_score_points(
        H59_CAPTURE / "wide_inputs.txt", H59_CAPTURE, "wide"
    )
    h67_raw = h59.load_score_points(
        H67_INPUTS, H67_CAPTURE, "constraint_wide_producer"
    )
    datasets = (
        (
            "dense",
            [h58.prepare(raw, h58.BASE_PRODUCER) for raw in dense_raw],
        ),
        (
            "h59",
            [h58.prepare(raw, h58.BASE_PRODUCER) for raw in h59_raw],
        ),
        (
            "h67",
            [h58.prepare(raw, h58.BASE_PRODUCER) for raw in h67_raw],
        ),
    )
    baseline = tuple(
        score(points, args.chain, BASE) for _, points in datasets
    )
    print(f"{args.chain}-chain baseline")
    for (name, _), result in zip(datasets, baseline):
        print(f"  {name:5s} {result.describe()}")
    rows = []
    for variant in variants():
        results = tuple(
            score(points, args.chain, variant)
            for _, points in datasets
        )
        if all(
            rank(actual) <= rank(expected)
            for actual, expected in zip(results, baseline)
        ) and any(
            rank(actual) < rank(expected)
            for actual, expected in zip(results, baseline)
        ):
            combined = tuple(
                sum(rank(result)[index] for result in results)
                for index in range(3)
            )
            rows.append((combined, variant, results))
    rows.sort(key=lambda row: (row[0], row[1].short()))
    print(f"jointly non-worse: {len(rows)}")
    for _, variant, results in rows[:24]:
        print(f"  {variant.short()}")
        for (name, _), result in zip(datasets, results):
            print(f"    {name:5s} {result.describe()}")


if __name__ == "__main__":
    main()
