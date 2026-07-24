#!/usr/bin/env python3
"""Search final table-combine partial materialization with current states.

Tomography now rejects alternate 64..69-bit producers for both narrow and
wide S, leaving the fused table rotation itself as the concrete unexhausted
location.  This pass tests whether Intel materializes a shared partial before
the architectural rounding:

* either or both direct products T1*U and T2*S;
* either or both delta-form products T1*(U-1) and T2*S;
* the combined delta correction before adding T1; or
* one of the two sequential partial sums.

Materialization spans 64..80 significant bits with RN, chop, away, and odd.
The narrow search uses Round 23's row-169 correction and both families use
the Round-21 shared-S state.  Selected captures rank candidates; complete
dense and master inputs validate finalists.
"""

from __future__ import annotations

import dataclasses

import h58_constraint_search as h58
import h59_discriminator as h59
import h60_round16_parity as h60
import h70_poly_outlier_forensics as h70
import h79_table_state_bias as h79
import h99_narrow_candidate_crossvalidate as h99
import h97_narrow_coefficient_discriminator as h97


@dataclasses.dataclass(frozen=True)
class Variant:
    kind: str
    bits: int = 0
    mode: str = "rn"

    def short(self) -> str:
        if self.kind == "exact":
            return "exact"
        return f"{self.kind}-{self.mode}{self.bits}"


EXACT = Variant("exact")


def variants() -> tuple[Variant, ...]:
    return (
        EXACT,
        *(
            Variant(kind, bits, mode)
            for kind in (
                "products",
                "s-product",
                "u-product",
                "delta-products",
                "delta-s-product",
                "delta-correction",
                "lead-plus-s",
                "lead-plus-u",
            )
            for bits in range(64, 81)
            for mode in ("rn", "chop", "away", "odd")
        ),
    )


def materialize(value: h58.FP, variant: Variant) -> h58.FP:
    return h70.pre_round(value, variant.bits, variant.mode)


def lane_value(
    lead: h58.FP,
    cross: h58.FP,
    one_plus_tail: h58.FP,
    sine_a: h58.FP,
    subtract_cross: bool,
    variant: Variant,
) -> h58.FP:
    direct_u = h58.mul_exact(lead, one_plus_tail)
    cross_product = h58.mul_exact(cross, sine_a)
    signed_cross = (
        h58.neg(cross_product)
        if subtract_cross
        else cross_product
    )
    if variant.kind == "exact":
        return h58.add_exact(direct_u, signed_cross)
    if variant.kind == "products":
        return h58.add_exact(
            materialize(direct_u, variant),
            materialize(signed_cross, variant),
        )
    if variant.kind == "s-product":
        return h58.add_exact(
            direct_u,
            materialize(signed_cross, variant),
        )
    if variant.kind == "u-product":
        return h58.add_exact(
            materialize(direct_u, variant),
            signed_cross,
        )

    tail = h58.add_exact(one_plus_tail, h58.neg(h58.ONE))
    tail_product = h58.mul_exact(lead, tail)
    if variant.kind == "delta-products":
        correction = h58.add_exact(
            materialize(tail_product, variant),
            materialize(signed_cross, variant),
        )
        return h58.add_exact(lead, correction)
    if variant.kind == "delta-s-product":
        correction = h58.add_exact(
            tail_product,
            materialize(signed_cross, variant),
        )
        return h58.add_exact(lead, correction)
    if variant.kind == "delta-correction":
        correction = materialize(
            h58.add_exact(tail_product, signed_cross),
            variant,
        )
        return h58.add_exact(lead, correction)
    if variant.kind == "lead-plus-s":
        partial = materialize(
            h58.add_exact(lead, signed_cross),
            variant,
        )
        return h58.add_exact(partial, tail_product)
    if variant.kind == "lead-plus-u":
        partial = materialize(
            h58.add_exact(lead, tail_product),
            variant,
        )
        return h58.add_exact(partial, signed_cross)
    raise ValueError(variant.kind)


def state(
    point: h58.PreparedPoint,
    narrow_delta: int = 7168,
    narrow_bias: int = 4,
    wide_bias: int = 5,
) -> tuple[h58.PreparedPoint, h58.FP, h58.FP]:
    if point.wide:
        altered = point
        bias = wide_bias
    else:
        altered = h97.alter_p(point, narrow_delta)
        bias = narrow_bias
    one_plus_tail, sine_a = h79.table_state(
        altered,
        h79.BASE,
    )
    sine_a = h79.bias_toward_zero(sine_a, bias)
    return altered, one_plus_tail, sine_a


def values(
    point: h58.PreparedPoint,
    variant: Variant,
    narrow_delta: int = 7168,
    narrow_bias: int = 4,
    wide_bias: int = 5,
) -> tuple[h58.FP, h58.FP]:
    altered, one_plus_tail, sine_a = state(
        point,
        narrow_delta,
        narrow_bias,
        wide_bias,
    )
    sine = lane_value(
        altered.sin_t,
        altered.cos_t,
        one_plus_tail,
        sine_a,
        False,
        variant,
    )
    cosine = lane_value(
        altered.cos_t,
        altered.sin_t,
        one_plus_tail,
        sine_a,
        True,
        variant,
    )
    if point.raw.sign:
        sine = h58.neg(sine)
    return sine, cosine


def score(
    points: list[h58.PreparedPoint],
    variant: Variant,
) -> tuple[int, int, int]:
    mode_misses = 0
    output_misses = 0
    rn_misses = 0
    for point in points:
        predicted = values(point, variant)
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
    family: str,
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
        selected = ("wide" if point.wide else "narrow") == family
        predicted = values(point, variant if selected else EXACT)
        actual = tuple(
            h58.x87_round(value, "rn")
            for value in h60.rotate(predicted, signed_n)
        )
        mismatch = actual != expected
        misses += mismatch
        narrow += mismatch if not point.wide else 0
        wide += mismatch if point.wide else 0
    return misses, narrow, wide


def load_family(
    inputs,
    capture,
    prefix: str,
    family: str,
) -> list[h58.PreparedPoint]:
    exponent = -1 if family == "wide" else -2
    return [
        h58.prepare(point)
        for point in h59.load_score_points(inputs, capture, prefix)
        if point.exponent == exponent
    ]


def search_family(family: str) -> None:
    if family == "narrow":
        datasets = (
            (
                "h59",
                load_family(
                    h99.H59_INPUTS,
                    h99.H59_CAPTURE,
                    "narrow",
                    family,
                ),
            ),
            (
                "h78",
                load_family(
                    h99.H78_INPUTS,
                    h99.H78_CAPTURE,
                    "constraint_paired_table",
                    family,
                ),
            ),
            (
                "h95",
                load_family(
                    h99.H95_INPUTS,
                    h99.H95_CAPTURE,
                    "constraint_table_local",
                    family,
                ),
            ),
            (
                "h97",
                load_family(
                    h99.H97_INPUTS,
                    h99.H97_CAPTURE,
                    "constraint_narrow_coefficient",
                    family,
                ),
            ),
        )
    else:
        datasets = (
            (
                "h59",
                load_family(
                    h99.H59_CAPTURE / "wide_inputs.txt",
                    h99.H59_CAPTURE,
                    "wide",
                    family,
                ),
            ),
            (
                "h67",
                load_family(
                    h79.H67_INPUTS,
                    h79.H67_CAPTURE,
                    "constraint_wide_producer",
                    family,
                ),
            ),
            (
                "h78",
                load_family(
                    h99.H78_INPUTS,
                    h99.H78_CAPTURE,
                    "constraint_paired_table",
                    family,
                ),
            ),
            (
                "h95",
                load_family(
                    h99.H95_INPUTS,
                    h99.H95_CAPTURE,
                    "constraint_table_local",
                    family,
                ),
            ),
        )
    ranked = []
    for variant in variants():
        scores = tuple(
            score(points, variant)
            for _, points in datasets
        )
        ranked.append(
            (
                sum(result[0] for result in scores),
                sum(result[1] for result in scores),
                sum(result[2] for result in scores),
                variant,
                scores,
            )
        )
    ranked.sort(
        key=lambda item: (
            item[:3],
            item[3].short(),
        )
    )

    target_exponent = -1 if family == "wide" else -2
    dense = [
        h58.prepare(point)
        for point in h58.load_points(
            h99.ROOT / "capture-kit-captures" / "pentiumII"
        )
        if point.exponent == target_exponent
    ]
    master = h99.master_points()
    print(f"{family} finalists with complete/master validation:")
    for total_mode, total_output, total_rn, variant, scores in ranked[:24]:
        dense_result = score(dense, variant)
        master_result = master_score(master, family, variant)
        print(
            f"  {variant.short():32s}: "
            f"search={total_mode:5d}/{total_output:5d}/{total_rn:4d} "
            f"dense={dense_result[0]:4d} "
            f"master={master_result[0]:3d}"
            f"(N={master_result[1]:2d},W={master_result[2]:3d}); "
            + " ".join(
                f"{name}={result[0]}"
                for (name, _), result in zip(datasets, scores)
            )
        )


def main() -> None:
    print(f"h104: {len(variants())} final-partial variants")
    for family in ("narrow", "wide"):
        search_family(family)


if __name__ == "__main__":
    main()
