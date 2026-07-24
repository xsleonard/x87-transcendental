#!/usr/bin/env python3
"""Evaluate the literal F2XM1 value graph before operation materialization.

The polynomial coefficients come from the public P5 constant table.  The
range-reduction lookup values are regenerated independently as RN67 values of
2**b - 1, including all positive and negative cells.
"""

from __future__ import annotations

import collections
import fractions
import functools

import h58_constraint_search as h58
import h251_f2xm1_exact_baseline as h251


SHORT = tuple(range(33, 39))  # C2..C7
LONG = tuple(range(39, 50))  # C2..C12
LN2 = h58.ROM[32]


def fp_fraction(value: h58.FP) -> fractions.Fraction:
    sign, significand, scale = value
    result = fractions.Fraction(significand) * fractions.Fraction(2) ** scale
    return -result if sign else result


def fraction_fp(value: fractions.Fraction, bits: int) -> h58.FP:
    if not value:
        return h58.ZERO
    sign = int(value < 0)
    magnitude = abs(value)
    exponent = h251.floor_log2(magnitude)
    scaled = magnitude * fractions.Fraction(2) ** (bits - 1 - exponent)
    significand, remainder = divmod(scaled.numerator, scaled.denominator)
    if 2 * remainder > scaled.denominator or (
        2 * remainder == scaled.denominator and bool(significand & 1)
    ):
        significand += 1
    if significand == 1 << bits:
        significand >>= 1
        exponent += 1
    return sign, significand, exponent - (bits - 1)


def input_fp(se: int, significand: int) -> h58.FP:
    if not significand:
        return (se >> 15, 0, 0)
    exponent_field = se & 0x7FFF
    exponent = (
        exponent_field - 16383 if exponent_field else h251.MIN_NORMAL_EXP
    )
    return se >> 15, significand, exponent - 63


def fmul(left: h58.FP, right: h58.FP) -> h58.FP:
    return h58.mul_exact(left, right)


def fadd(left: h58.FP, right: h58.FP) -> h58.FP:
    return h58.add_exact(left, right)


def table_anchor(x: h58.FP) -> fractions.Fraction:
    magnitude = abs(fp_fraction(x))
    if magnitude >= fractions.Fraction(1, 2):
        lane = int((magnitude - fractions.Fraction(1, 2)) * 32)
        numerator = 66 + 4 * min(lane, 15)
    else:
        lane = int((magnitude - fractions.Fraction(1, 4)) * 64)
        numerator = 33 + 2 * min(max(lane, 0), 15)
    anchor = fractions.Fraction(numerator, 128)
    return -anchor if x[0] else anchor


@functools.cache
def table_value(anchor: fractions.Fraction) -> h58.FP:
    return fraction_fp(h251.expm1_decimal(anchor, 180), 67)


def short_polynomial(z: h58.FP) -> h58.FP:
    z2 = fmul(z, z)
    c2, c3, c4, c5, c6, c7 = (h58.ROM[row] for row in SHORT)

    even = fadd(c4, fmul(z2, c6))
    even = fadd(c2, fmul(z2, even))
    even = fadd(z, fmul(z2, even))

    odd = fadd(c5, fmul(z2, c7))
    odd = fadd(c3, fmul(z2, odd))
    odd = fmul(z, fmul(z2, odd))
    return fadd(even, odd)


def long_polynomial(z: h58.FP) -> h58.FP:
    z2 = fmul(z, z)
    coefficients = [h58.ROM[row] for row in LONG]
    odd = coefficients[9]  # C11
    even = coefficients[10]  # C12
    for degree in range(10, 2, -2):
        odd = fadd(coefficients[degree - 3], fmul(z2, odd))
        even = fadd(coefficients[degree - 2], fmul(z2, even))
    odd = fmul(z, fmul(z2, odd))
    even = fmul(z2, fmul(z2, even))
    c2_term = fmul(z2, coefficients[0])
    return fadd(z, fadd(c2_term, fadd(odd, even)))


def values(x: h58.FP) -> dict[str, h58.FP]:
    z = fmul(LN2, x)
    result = {
        "linear": z,
        "long": long_polynomial(z),
    }
    if abs(fp_fraction(x)) >= fractions.Fraction(1, 4):
        anchor = table_anchor(x)
        residual = fadd(x, h58.neg(fraction_fp(anchor, 67)))
        residual_z = fmul(LN2, residual)
        polynomial = short_polynomial(residual_z)
        lookup = table_value(anchor)
        result["table"] = fadd(
            lookup,
            fmul(fadd(h58.ONE, lookup), polynomial),
        )
    return result


def rounded(value: h58.FP, rc: str) -> tuple[int, int]:
    return h251.round_x87(fp_fraction(value), rc)[0]


def score_dataset(name: str) -> None:
    inputs = [
        tuple(int(field, 16) for field in line.split())
        for line in h251.INPUTS[name].read_text().splitlines()
    ]
    captures = {
        rc: [
            h251.parse_output(line)[0]
            for line in (
                h251.CAPTURE / f"{name}_f2xm1_{rc}_status.txt"
            ).read_text().splitlines()
        ]
        for rc in h251.RCS
    }
    modes = collections.Counter()
    inputs_exact = collections.Counter()
    best = collections.Counter()
    by_exponent: dict[int, collections.Counter] = collections.defaultdict(
        collections.Counter
    )
    domain = 0

    for index, (se, sig) in enumerate(inputs):
        x_fraction = h251.decode_input(se, sig)
        if abs(x_fraction) > 1:
            continue
        domain += 1
        candidates = values(input_fp(se, sig))
        row_scores = {}
        for path, value in candidates.items():
            misses = sum(
                rounded(value, rc) != captures[rc][index] for rc in h251.RCS
            )
            row_scores[path] = misses
            modes[path] += misses
            inputs_exact[path] += not misses
        minimum = min(row_scores.values())
        for path, misses in row_scores.items():
            if misses == minimum:
                best[path] += 1
                if sig:
                    exponent_field = se & 0x7FFF
                    exponent = (
                        exponent_field - 16383
                        if exponent_field
                        else h251.MIN_NORMAL_EXP
                    )
                    by_exponent[exponent][path] += 1

    print(f"{name}: domain={domain}")
    for path in ("linear", "long", "table"):
        if path in modes:
            print(
                f"  {path}: mode misses={modes[path]}, "
                f"all-mode exact inputs={inputs_exact[path]}, "
                f"best/tied={best[path]}"
            )
    print("  target-path evidence by input exponent:")
    for exponent in sorted(by_exponent):
        counts = by_exponent[exponent]
        if sum(counts.values()) and (
            exponent >= -40 or len(counts) > 1
        ):
            print(f"    {exponent:6d}: {dict(counts)}")


def main() -> None:
    for name in ("target", "dense", "sweep"):
        score_dataset(name)


if __name__ == "__main__":
    main()
