#!/usr/bin/env python3
"""Trace and constrain the two residual Round-18 polynomial cosine misses.

The h65 capture leaves three directed-mode misses on two cosine outputs.
This pass first reports the exact candidate position inside the RD/RU output
interval and every q-Horner rounding residue.  It then tests a bounded family
of lower-bit retention mechanisms in the final negative q*a^2 tail:

* wider chop/RN materialization and an exact unmaterialized product;
* one retained guard/sticky unit below the candidate's 67-bit tail.

Any h65 improvement is verified against all 80,000 direct polynomial inputs,
where the Round-18 candidate is exact in RN/RD/RU.
"""

from __future__ import annotations

import dataclasses
import fractions
import pathlib

import h58_constraint_search as h58
import h64_poly_constraints as h64
import h65_poly_discriminator as h65


ROOT = pathlib.Path(__file__).resolve().parents[1]
H65_INPUTS = ROOT / "capture-kit" / "inputs" / "constraint_poly_h65.txt"
H65_CAPTURE = ROOT / "capture-kit-captures" / "skylake-h65-poly"
OUTLIER_INDICES = (1753, 1829)


@dataclasses.dataclass(frozen=True)
class TailVariant:
    kind: str
    bits: int = 67
    mode: str = "chop"
    depth: int = 0
    condition: str = "any"

    def short(self) -> str:
        if self.kind == "materialize":
            return f"{self.mode}{self.bits}"
        if self.kind == "exact":
            return "exact-product"
        return f"sticky-{self.condition}@-{self.depth}"


@dataclasses.dataclass(frozen=True)
class TailPoint:
    raw: h64.PolyRaw
    exact_product: h58.FP
    base_tail: h58.FP
    shift: int
    top: int
    remainder: int


BASE = TailVariant("materialize")


@dataclasses.dataclass(frozen=True)
class HornerVariant:
    edge: int
    bits: int
    mode: str

    def short(self) -> str:
        if self.edge < 0:
            return "direct-rn64"
        edge = "all" if self.edge == 0 else str(self.edge)
        return f"edge={edge}:pre-{self.mode}{self.bits}->rn64"


def fp_fraction(value: h58.FP) -> fractions.Fraction:
    sign, significand, scale = value
    numerator = -significand if sign else significand
    if scale >= 0:
        return fractions.Fraction(numerator << scale, 1)
    return fractions.Fraction(numerator, 1 << -scale)


def output_fp(output: tuple[int, int]) -> h58.FP:
    se, sig = output
    return se >> 15, sig, (se & 0x7FFF) - 16383 - 63


def prepare_tail(raw: h64.PolyRaw) -> TailPoint:
    point = h64.prepare(raw, h65.CANDIDATE_PRODUCER)
    exact_product = h58.mul_exact(point.q, point.asq)
    base_tail = h58.round_fp(exact_product, 67, "chop")
    shift = exact_product[1].bit_length() - 67
    top = exact_product[1] >> shift
    remainder = exact_product[1] & ((1 << shift) - 1)
    return TailPoint(
        raw=raw,
        exact_product=exact_product,
        base_tail=base_tail,
        shift=shift,
        top=top,
        remainder=remainder,
    )


def condition_matches(point: TailPoint, condition: str) -> bool:
    guard = bool(point.remainder & (1 << (point.shift - 1)))
    sticky = bool(
        point.remainder & ((1 << (point.shift - 1)) - 1)
    )
    if condition == "any":
        return bool(point.remainder)
    if condition == "guard":
        return guard
    if condition == "sticky":
        return sticky
    if condition == "guard-sticky":
        return guard and sticky
    if condition == "guard-or-sticky":
        return guard or sticky
    if condition == "tie":
        return guard and not sticky
    if condition == "odd":
        return bool(point.top & 1) and bool(point.remainder)
    if condition == "even":
        return not (point.top & 1) and bool(point.remainder)
    raise ValueError(condition)


def tail_value(point: TailPoint, variant: TailVariant) -> h58.FP:
    if variant.kind == "materialize":
        return h58.round_fp(
            point.exact_product, variant.bits, variant.mode
        )
    if variant.kind == "exact":
        return point.exact_product
    if not condition_matches(point, variant.condition):
        return point.base_tail
    correction = (
        point.base_tail[0],
        1,
        point.base_tail[2] - variant.depth,
    )
    return h58.add_exact(point.base_tail, correction)


def hidden_value(point: TailPoint, variant: TailVariant) -> h58.FP:
    return h58.add_exact(h58.ONE, tail_value(point, variant))


def score(
    points: list[TailPoint],
    variant: TailVariant,
) -> tuple[int, int, int]:
    mode_misses = 0
    output_misses = 0
    rn_misses = 0
    for point in points:
        value = hidden_value(point, variant)
        misses = 0
        for rc_index, rc in enumerate(h58.RCS):
            mismatch = (
                h58.x87_round(value, rc)
                != point.raw.sincos[rc_index][1]
            )
            mode_misses += mismatch
            rn_misses += mismatch if rc == "rn" else 0
            misses += mismatch
        output_misses += bool(misses)
    return mode_misses, output_misses, rn_misses


def round_to_odd(value: h58.FP, bits: int) -> h58.FP:
    if value[1].bit_length() <= bits:
        return value
    shift = value[1].bit_length() - bits
    top = value[1] >> shift
    remainder = value[1] & ((1 << shift) - 1)
    if remainder:
        top |= 1
    return value[0], top, value[2] + shift


def pre_round(value: h58.FP, bits: int, mode: str) -> h58.FP:
    if mode == "odd":
        return round_to_odd(value, bits)
    return h58.round_fp(value, bits, mode)


def q_horner(
    raw: h64.PolyRaw,
    variant: HornerVariant,
) -> tuple[h58.FP, h58.FP]:
    point = h64.prepare(raw, h65.CANDIDATE_PRODUCER)
    value = h58.coefficient(h58.C6[0], h65.CANDIDATE_PRODUCER)
    for step, row in enumerate(h58.C6[1:], 1):
        exact = h58.add_exact(
            h58.mul_exact(value, point.asq),
            h58.coefficient(row, h65.CANDIDATE_PRODUCER),
        )
        if variant.edge in (0, step):
            exact = pre_round(exact, variant.bits, variant.mode)
        value = h58.round_fp(exact, 64, "rn")
    return value, point.asq


def horner_hidden(
    raw: h64.PolyRaw,
    variant: HornerVariant,
) -> h58.FP:
    q, asq = q_horner(raw, variant)
    tail = h58.fmul(q, asq, 67, "chop")
    return h58.add_exact(h58.ONE, tail)


def score_horner(
    raw_points: list[h64.PolyRaw],
    variant: HornerVariant,
) -> tuple[int, int, int]:
    mode_misses = 0
    output_misses = 0
    rn_misses = 0
    for raw in raw_points:
        value = horner_hidden(raw, variant)
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


def horner_variants() -> list[HornerVariant]:
    return [
        HornerVariant(edge, bits, mode)
        for edge in range(0, 6)
        for bits in range(65, 97)
        for mode in ("rn", "chop", "away", "odd")
    ]


def describe_outlier(point: TailPoint) -> None:
    raw = point.raw
    hidden = hidden_value(point, BASE)
    rd = output_fp(raw.sincos[1][1])
    ru = output_fp(raw.sincos[2][1])
    midpoint = h58.fmul(
        h58.add_exact(rd, ru), (0, 1, -1), 256, "chop"
    )
    ulp = fractions.Fraction(1, 1 << -rd[2])
    hidden_fraction = fp_fraction(hidden)
    midpoint_fraction = fp_fraction(midpoint)
    upper_fraction = fp_fraction(ru)
    exact_fraction = fp_fraction(
        h58.add_exact(h58.ONE, point.exact_product)
    )
    print(
        f"index {raw.index}: "
        f"{(raw.sign << 15) | 0x3ffc:04x} {raw.sig:016x}"
    )
    print(
        "  hardware cos: "
        + " ".join(
            f"{rc}={raw.sincos[index][1][0]:04x}:"
            f"{raw.sincos[index][1][1]:016x}"
            for index, rc in enumerate(h58.RCS)
        )
    )
    print(
        f"  candidate relative to midpoint: "
        f"{float((hidden_fraction - midpoint_fraction) / ulp):+.12g} ulp"
    )
    print(
        f"  candidate relative to RU: "
        f"{float((hidden_fraction - upper_fraction) / ulp):+.12g} ulp"
    )
    print(
        f"  exact q*a^2 relative to candidate tail: "
        f"{float((exact_fraction - hidden_fraction) / ulp):+.12g} ulp"
    )
    print(
        f"  final product: width={point.exact_product[1].bit_length()} "
        f"shift={point.shift} guard="
        f"{(point.remainder >> (point.shift - 1)) & 1} "
        f"sticky={int(bool(point.remainder & ((1 << (point.shift - 1)) - 1)))} "
        f"kept-lsb={point.top & 1}"
    )

    prepared = h64.prepare(raw, h65.CANDIDATE_PRODUCER)
    value = h58.coefficient(h58.C6[0], h65.CANDIDATE_PRODUCER)
    print("  q Horner RN64 residues:")
    for step, row in enumerate(h58.C6[1:], 1):
        exact = h58.add_exact(
            h58.mul_exact(value, prepared.asq),
            h58.coefficient(row, h65.CANDIDATE_PRODUCER),
        )
        rounded = h58.round_fp(exact, 64, "rn")
        local_ulp = fractions.Fraction(1, 1 << -rounded[2])
        residue = (
            fp_fraction(exact) - fp_fraction(rounded)
        ) / local_ulp
        print(
            f"    step {step}: row={row} "
            f"residue={float(residue):+.12g} local-ulp "
            f"rounded-lsb={rounded[1] & 1}"
        )
        value = rounded


def variants() -> list[TailVariant]:
    result = [BASE, TailVariant("exact")]
    for bits in range(64, 97):
        for mode in ("rn", "chop"):
            result.append(TailVariant("materialize", bits, mode))
    for depth in range(1, 33):
        for condition in (
            "any",
            "guard",
            "sticky",
            "guard-sticky",
            "guard-or-sticky",
            "tie",
            "odd",
            "even",
        ):
            result.append(
                TailVariant(
                    "sticky",
                    depth=depth,
                    condition=condition,
                )
            )
    return list(dict.fromkeys(result))


def main() -> None:
    h65_raw = h65.load_captured(
        H65_INPUTS, H65_CAPTURE, "constraint_poly"
    )
    by_index = {point.index: prepare_tail(point) for point in h65_raw}
    print("outlier traces")
    for index in OUTLIER_INDICES:
        describe_outlier(by_index[index])

    h65_points = [prepare_tail(point) for point in h65_raw]
    baseline = score(h65_points, BASE)
    ranked = []
    for variant in variants():
        result = score(h65_points, variant)
        if result < baseline:
            ranked.append((result, variant))
    ranked.sort(key=lambda row: (row[0], row[1].short()))
    print(
        f"h65: {len(ranked)} variants improve candidate "
        f"{baseline[0]}/{3 * len(h65_points)} mode, "
        f"{baseline[1]}/{len(h65_points)} output, "
        f"{baseline[2]}/{len(h65_points)} RN"
    )
    for result, variant in ranked[:24]:
        print(
            f"  {variant.short():28s} "
            f"{result[0]}/{3 * len(h65_points)} mode, "
            f"{result[1]}/{len(h65_points)} output, "
            f"{result[2]}/{len(h65_points)} RN"
        )

    dense_points = [prepare_tail(point) for point in h64.load_raw()]
    survivors = []
    for h65_score, variant in ranked:
        dense_score = score(dense_points, variant)
        if dense_score == (0, 0, 0):
            survivors.append((h65_score, variant))
    print(
        f"complete-capture survivors: {len(survivors)} "
        f"(Round-18 baseline is 0/{3 * len(dense_points)} mode)"
    )
    for result, variant in survivors[:40]:
        print(
            f"  {variant.short():28s} "
            f"h65={result[0]}/{3 * len(h65_points)} mode, "
            f"{result[1]}/{len(h65_points)} output, "
            f"{result[2]}/{len(h65_points)} RN"
        )

    print("q-Horner pre-round search")
    candidate_score = score_horner(
        h65_raw, HornerVariant(-1, 64, "rn")
    )
    horner_ranked = []
    for variant in horner_variants():
        result = score_horner(h65_raw, variant)
        if result < candidate_score:
            horner_ranked.append((result, variant))
    horner_ranked.sort(key=lambda row: (row[0], row[1].short()))
    print(
        f"h65: {len(horner_ranked)} double-round variants improve "
        f"{candidate_score[0]}/{3 * len(h65_raw)} mode"
    )
    for result, variant in horner_ranked[:40]:
        print(
            f"  {variant.short():34s} "
            f"{result[0]}/{3 * len(h65_raw)} mode, "
            f"{result[1]}/{len(h65_raw)} output, "
            f"{result[2]}/{len(h65_raw)} RN"
        )

    dense_raw = h64.load_raw()
    horner_survivors = []
    for h65_score, variant in horner_ranked:
        dense_score = score_horner(dense_raw, variant)
        if dense_score == (0, 0, 0):
            horner_survivors.append((h65_score, variant))
    print(
        f"complete-capture Horner survivors: {len(horner_survivors)}"
    )
    for result, variant in horner_survivors[:60]:
        print(
            f"  {variant.short():34s} "
            f"h65={result[0]}/{3 * len(h65_raw)} mode, "
            f"{result[1]}/{len(h65_raw)} output, "
            f"{result[2]}/{len(h65_raw)} RN"
        )


if __name__ == "__main__":
    main()
