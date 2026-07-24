#!/usr/bin/env python3
"""Test product-materialization mechanisms for the q-Horner survivor.

The whole-sum away75 model explains 62/64 fresh h71 discriminator choices.
This pass tests the more physical alternative of materializing q*a^2 before
the coefficient add, at one or every Horner edge, followed by the established
fused-sum RN64 result.
"""

from __future__ import annotations

import dataclasses
import pathlib

import h58_constraint_search as h58
import h64_poly_constraints as h64
import h65_poly_discriminator as h65
import h70_poly_outlier_forensics as h70


ROOT = pathlib.Path(__file__).resolve().parents[1]
H65_INPUTS = ROOT / "capture-kit" / "inputs" / "constraint_poly_h65.txt"
H65_CAPTURE = ROOT / "capture-kit-captures" / "skylake-h65-poly"
H71_INPUTS = (
    ROOT / "capture-kit" / "inputs" / "constraint_poly_round75_h71.txt"
)
H71_CAPTURE = (
    ROOT / "capture-kit-captures" / "skylake-h71-poly-round75"
)


@dataclasses.dataclass(frozen=True)
class ProductVariant:
    edge: int
    bits: int
    mode: str

    def short(self) -> str:
        if self.edge < 0:
            return "direct-fma-rn64"
        edge = "all" if self.edge == 0 else str(self.edge)
        return f"edge={edge}:product-{self.mode}{self.bits}->add-rn64"


DIRECT = ProductVariant(-1, 64, "rn")


def hidden(
    raw: h64.PolyRaw,
    variant: ProductVariant,
) -> h58.FP:
    point = h64.prepare(raw, h65.CANDIDATE_PRODUCER)
    value = h58.coefficient(h58.C6[0], h65.CANDIDATE_PRODUCER)
    for step, row in enumerate(h58.C6[1:], 1):
        product = h58.mul_exact(value, point.asq)
        if variant.edge in (0, step):
            product = h70.pre_round(
                product, variant.bits, variant.mode
            )
        exact = h58.add_exact(
            product,
            h58.coefficient(row, h65.CANDIDATE_PRODUCER),
        )
        value = h58.round_fp(exact, 64, "rn")
    tail = h58.fmul(value, point.asq, 67, "chop")
    return h58.add_exact(h58.ONE, tail)


def score(
    raw_points: list[h64.PolyRaw],
    variant: ProductVariant,
) -> tuple[int, int, int]:
    mode_misses = 0
    output_misses = 0
    rn_misses = 0
    for raw in raw_points:
        value = hidden(raw, variant)
        misses = 0
        for rc_index, rc in enumerate(h58.RCS):
            mismatch = (
                h58.x87_round(value, rc)
                != raw.sincos[rc_index][1]
            )
            mode_misses += mismatch
            rn_misses += mismatch if rc == "rn" else 0
            misses += mismatch
        output_misses += bool(misses)
    return mode_misses, output_misses, rn_misses


def variants() -> list[ProductVariant]:
    return [
        ProductVariant(edge, bits, mode)
        for edge in range(0, 6)
        for bits in range(64, 97)
        for mode in ("rn", "chop", "away", "odd")
    ]


def main() -> None:
    h65_raw = h65.load_captured(
        H65_INPUTS, H65_CAPTURE, "constraint_poly"
    )
    h71_raw = h65.load_captured(
        H71_INPUTS, H71_CAPTURE, "constraint_poly_round75"
    )
    final75 = h70.HornerVariant(5, 75, "away")
    reference65 = h70.score_horner(h65_raw, final75)
    reference71 = h70.score_horner(h71_raw, final75)
    print(
        f"references: direct h65={score(h65_raw, DIRECT)} "
        f"h71={score(h71_raw, DIRECT)}; "
        f"whole-sum-away75 h65={reference65} h71={reference71}"
    )

    rows = []
    for variant in variants():
        h65_score = score(h65_raw, variant)
        h71_score = score(h71_raw, variant)
        rows.append(
            (
                (
                    h65_score[0] + h71_score[0],
                    h65_score[1] + h71_score[1],
                    h65_score[2] + h71_score[2],
                    h65_score,
                    h71_score,
                    variant.short(),
                ),
                variant,
                h65_score,
                h71_score,
            )
        )
    rows.sort(key=lambda row: row[0])
    print("best product schedules:")
    for _, variant, h65_score, h71_score in rows[:40]:
        print(
            f"  {variant.short():46s} "
            f"h65={h65_score} h71={h71_score}"
        )

    candidates = [
        (variant, h65_score, h71_score)
        for _, variant, h65_score, h71_score in rows
        if h65_score <= reference65 and h71_score <= reference71
    ]
    print(f"jointly non-worse before dense: {len(candidates)}")
    dense_raw = h64.load_raw()
    survivors = []
    for variant, h65_score, h71_score in candidates:
        dense_score = score(dense_raw, variant)
        if dense_score == (0, 0, 0):
            survivors.append(
                (variant, h65_score, h71_score, dense_score)
            )
    print(f"dense-exact product survivors: {len(survivors)}")
    for variant, h65_score, h71_score, dense_score in survivors:
        print(
            f"  {variant.short():46s} "
            f"h65={h65_score} h71={h71_score} dense={dense_score}"
        )


if __name__ == "__main__":
    main()
