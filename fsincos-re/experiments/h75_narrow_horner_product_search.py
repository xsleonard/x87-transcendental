#!/usr/bin/env python3
"""Search product-before-add materialization in the narrow table Horner DAG.

The polynomial cosine path established ``RN64(chop67(product)+coefficient)``.
This pass tests the analogous operation, at one or every four-term p/q
Horner edge, while keeping the independently validated Round-17 narrow tail.
Candidates must improve or preserve both the complete narrow capture and the
fresh h59 narrow discriminator.
"""

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
H59_INPUTS = H59_CAPTURE / "narrow_inputs.txt"


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
            point, p=horner(h58.S4, point.asq, variant)
        )
    if chain in ("q", "both"):
        point = dataclasses.replace(
            point, q=horner(h58.C4, point.asq, variant)
        )
    return h58.table_tail(point, h58.NARROW_TAIL)


def score(
    points: list[h58.PreparedPoint],
    chain: str,
    variant: Variant,
) -> h58.Score:
    result = h58.Score(total_outputs=2 * len(points))
    for point in points:
        raw = point.raw
        predicted = values(point, chain, variant)
        for side, value in enumerate(predicted):
            output_missed = False
            for rc_index, rc in enumerate(h58.RCS):
                mismatch = (
                    h58.x87_round(value, rc)
                    != raw.hw[rc_index][side]
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
        for edge in (0, 3)
        for bits in range(64, 73)
        for mode in ("rn", "chop", "away", "odd")
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--chain",
        choices=("p", "q", "both", "all"),
        default="all",
    )
    args = parser.parse_args()
    dense = [
        raw
        for raw in h58.load_points(DENSE_CAPTURE)
        if raw.exponent == -2
    ]
    h59_raw = h59.load_score_points(
        H59_INPUTS, H59_CAPTURE, "narrow"
    )
    datasets = (
        (
            "dense",
            [h58.prepare(raw, h58.BASE_PRODUCER) for raw in dense],
        ),
        (
            "h59",
            [h58.prepare(raw, h58.BASE_PRODUCER) for raw in h59_raw],
        ),
    )
    print(
        "datasets: "
        + ", ".join(
            f"{name}={len(raw)} inputs" for name, raw in datasets
        )
    )
    chains = (
        ("p", "q", "both")
        if args.chain == "all"
        else (args.chain,)
    )
    for chain in chains:
        baseline = tuple(
            score(raw, chain, BASE) for _, raw in datasets
        )
        print(f"{chain}-chain baseline")
        for (name, _), result in zip(datasets, baseline):
            print(f"  {name:5s} {result.describe()}")
        rows = []
        for variant in variants():
            results = tuple(
                score(raw, chain, variant) for _, raw in datasets
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
        print(f"  jointly non-worse: {len(rows)}")
        for _, variant, results in rows[:24]:
            print(f"    {variant.short()}")
            for (name, _), result in zip(datasets, results):
                print(f"      {name:5s} {result.describe()}")


if __name__ == "__main__":
    main()
