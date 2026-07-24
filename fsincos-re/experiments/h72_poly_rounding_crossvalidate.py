#!/usr/bin/env python3
"""Cross-validate q-Horner pre-round schedules on h65, h71, and dense data."""

from __future__ import annotations

import pathlib

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


def rank(
    raw: list[h64.PolyRaw],
    variant: h70.HornerVariant,
) -> tuple[int, int, int]:
    return h70.score_horner(raw, variant)


def main() -> None:
    h65_raw = h65.load_captured(
        H65_INPUTS, H65_CAPTURE, "constraint_poly"
    )
    h71_raw = h65.load_captured(
        H71_INPUTS, H71_CAPTURE, "constraint_poly_round75"
    )
    direct = h70.HornerVariant(-1, 64, "rn")
    final75 = h70.HornerVariant(5, 75, "away")
    all75 = h70.HornerVariant(0, 75, "away")
    references = {
        "direct": direct,
        "final75": final75,
        "all75": all75,
    }
    print(
        f"datasets: h65={len(h65_raw)}, h71={len(h71_raw)}, "
        f"dense=80000"
    )
    for name, variant in references.items():
        print(
            f"{name:8s} h65={rank(h65_raw, variant)} "
            f"h71={rank(h71_raw, variant)}"
        )

    rows = []
    for variant in h70.horner_variants():
        h65_score = rank(h65_raw, variant)
        h71_score = rank(h71_raw, variant)
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
    print("best combined schedules:")
    for _, variant, h65_score, h71_score in rows[:32]:
        print(
            f"  {variant.short():34s} "
            f"h65={h65_score} h71={h71_score}"
        )

    final65 = rank(h65_raw, final75)
    final71 = rank(h71_raw, final75)
    candidates = [
        (variant, h65_score, h71_score)
        for _, variant, h65_score, h71_score in rows
        if h65_score <= final65 and h71_score <= final71
    ]
    print(
        f"jointly non-worse than final75 before dense: "
        f"{len(candidates)}"
    )
    dense_raw = h64.load_raw()
    survivors = []
    for variant, h65_score, h71_score in candidates:
        dense_score = rank(dense_raw, variant)
        if dense_score == (0, 0, 0):
            survivors.append(
                (variant, h65_score, h71_score, dense_score)
            )
    print(f"dense-exact survivors: {len(survivors)}")
    for variant, h65_score, h71_score, dense_score in survivors:
        print(
            f"  {variant.short():34s} "
            f"h65={h65_score} h71={h71_score} dense={dense_score}"
        )


if __name__ == "__main__":
    main()
