#!/usr/bin/env python3
"""Search narrow p-Horner sequencing after the h97 coefficient signal.

h75 tested product materialization against the then-current Round-17 tail,
only at the final or every edge, and before the Round-21 shared-S evidence
or h97 row-169 discriminator existed.  This pass crosses the supported
row-169 correction direction with:

* exact fused product-plus-coefficient rounding at one or every edge; and
* RN/chop/away/odd product materialization at 65..72 bits before the
  64-bit coefficient add, at one or every edge.

Candidates are ranked jointly on h59, h78, h95, and h97.  The complete dense
capture and independent master sweep are used only to validate finalists.
"""

from __future__ import annotations

import dataclasses
import pathlib

import h58_constraint_search as h58
import h59_discriminator as h59
import h70_poly_outlier_forensics as h70
import h79_table_state_bias as h79
import h99_narrow_candidate_crossvalidate as h99


DELTAS = (0, 2048, 4096, 6144, 7168, 7680, 8192)


@dataclasses.dataclass(frozen=True)
class Variant:
    kind: str
    edge: int = 0
    bits: int = 64
    mode: str = "rn"

    def short(self) -> str:
        if self.kind == "baseline":
            return "baseline"
        edge = "all" if self.edge == 0 else str(self.edge)
        if self.kind == "fused":
            return f"fused-edge-{edge}"
        return f"product-{self.mode}{self.bits}-edge-{edge}"


BASE = Variant("baseline")


def variants() -> tuple[Variant, ...]:
    return (
        BASE,
        *(
            Variant("fused", edge)
            for edge in (0, 1, 2, 3)
        ),
        *(
            Variant("product", edge, bits, mode)
            for edge in (0, 1, 2, 3)
            for bits in range(65, 73)
            for mode in ("rn", "chop", "away", "odd")
        ),
    )


def coefficient(row: int, delta: int) -> h58.FP:
    value = h58.coefficient(row, h58.BASE_PRODUCER)
    if row != h58.S4[-1] or not delta:
        return value
    return value[0], value[1] + delta, value[2]


def p_value(
    point: h58.PreparedPoint,
    delta: int,
    variant: Variant,
) -> h58.FP:
    value = coefficient(h58.S4[0], delta)
    for step, row in enumerate(h58.S4[1:], 1):
        constant = coefficient(row, delta)
        selected = variant.edge in (0, step)
        if variant.kind == "fused" and selected:
            value = h58.round_fp(
                h58.add_exact(
                    h58.mul_exact(value, point.asq),
                    constant,
                ),
                64,
                "rn",
            )
        else:
            product = h58.mul_exact(value, point.asq)
            if variant.kind == "product" and selected:
                product = h70.pre_round(
                    product,
                    variant.bits,
                    variant.mode,
                )
            else:
                product = h58.round_fp(product, 64, "rn")
            value = h58.fadd(product, constant, 64, "rn")
    return value


def values(
    point: h58.PreparedPoint,
    delta: int,
    variant: Variant,
) -> tuple[h58.FP, h58.FP]:
    altered = dataclasses.replace(
        point,
        p=p_value(point, delta, variant),
    )
    return h79.values(
        altered,
        h79.BASE,
        4,
    )


def score(
    points: list[h58.PreparedPoint],
    delta: int,
    variant: Variant,
) -> tuple[int, int, int]:
    mode_misses = 0
    output_misses = 0
    rn_misses = 0
    for point in points:
        predicted = values(point, delta, variant)
        for side, value in enumerate(predicted):
            missed_output = False
            for rc_index, rc in enumerate(h58.RCS):
                mismatch = (
                    h58.x87_round(value, rc)
                    != point.raw.hw[rc_index][side]
                )
                mode_misses += mismatch
                rn_misses += mismatch if rc_index == 0 else 0
                missed_output |= mismatch
            output_misses += missed_output
    return mode_misses, output_misses, rn_misses


def master_score(
    points: list[
        tuple[
            tuple[int, h58.PreparedPoint, bool] | None,
            tuple[tuple[int, int], tuple[int, int]] | None,
        ]
    ],
    delta: int,
    variant: Variant,
) -> tuple[int, int, int]:
    misses = 0
    narrow = 0
    wide = 0
    for active, expected in points:
        if active is None:
            continue
        if expected is None:
            raise AssertionError("table-active master input returned C2")
        signed_n, point, _ = active
        if point.wide:
            predicted = h79.values(point, h79.BASE, 5)
        else:
            predicted = values(point, delta, variant)
        actual = tuple(
            h58.x87_round(value, "rn")
            for value in h99.h60.rotate(predicted, signed_n)
        )
        mismatch = actual != expected
        misses += mismatch
        narrow += mismatch if not point.wide else 0
        wide += mismatch if point.wide else 0
    return misses, narrow, wide


def main() -> None:
    raw_datasets = (
        (
            "h59",
            h99.load_narrow(
                h99.H59_INPUTS,
                h99.H59_CAPTURE,
                "narrow",
            ),
        ),
        (
            "h78",
            h99.load_narrow(
                h99.H78_INPUTS,
                h99.H78_CAPTURE,
                "constraint_paired_table",
            ),
        ),
        (
            "h95",
            h99.load_narrow(
                h99.H95_INPUTS,
                h99.H95_CAPTURE,
                "constraint_table_local",
            ),
        ),
        (
            "h97",
            h99.load_narrow(
                h99.H97_INPUTS,
                h99.H97_CAPTURE,
                "constraint_narrow_coefficient",
            ),
        ),
    )
    datasets = tuple(
        (
            name,
            [h58.prepare(point) for point in raw],
        )
        for name, raw in raw_datasets
    )
    candidates = []
    print(
        "h100 search: "
        + " ".join(
            f"{name}={len(points)}" for name, points in datasets
        )
        + f"; {len(DELTAS)} deltas x {len(variants())} variants"
    )
    for delta in DELTAS:
        for variant in variants():
            scores = tuple(
                score(points, delta, variant)
                for _, points in datasets
            )
            candidates.append(
                (
                    sum(result[0] for result in scores),
                    sum(result[1] for result in scores),
                    sum(result[2] for result in scores),
                    delta,
                    variant,
                    scores,
                )
            )
    candidates.sort(
        key=lambda item: (
            item[:3],
            item[3],
            item[4].short(),
        )
    )

    dense = [
        h58.prepare(point)
        for point in h58.load_points(
            h99.ROOT / "capture-kit-captures" / "pentiumII"
        )
        if point.exponent == -2
    ]
    master = h99.master_points()
    print("joint finalists with untouched complete/master validation:")
    for (
        total_mode,
        total_output,
        total_rn,
        delta,
        variant,
        scores,
    ) in candidates[:24]:
        dense_result = score(dense, delta, variant)
        master_result = master_score(master, delta, variant)
        print(
            f"  delta={delta:+5d} {variant.short():30s}: "
            f"search={total_mode:4d}/{total_output:4d}/{total_rn:4d} "
            f"dense={dense_result[0]:4d} "
            f"master={master_result[0]:3d}"
            f"(N={master_result[1]:2d},W={master_result[2]:3d}); "
            + " ".join(
                f"{name}={result[0]}"
                for (name, _), result in zip(datasets, scores)
            )
        )


if __name__ == "__main__":
    main()
