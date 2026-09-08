#!/usr/bin/env python3
"""Validate the trigonometric table index and midpoint reconstruction.

The numerical model couples table indexing with midpoint construction. The
index combines exponent parity with the two leading fraction bits of a
positive magnitude. The midpoint preserves those fraction bits and inserts
the next bit. This script evaluates both operations on every table-path
argument in the dense and structured corpora and compares their results with
the previously established cell, anchor, and residual.

Four-fraction-bit alternatives are tested as a falsifier. They produce a
32-entry index and a finer breakpoint and therefore cannot select the
eight-entry trigonometric table used by this model.
"""

from __future__ import annotations

from decimal import Decimal, getcontext

import h58_constraint_search as h58
import h228_p6_four_term_c_parity as h228


INTERNAL_EXPONENT_BIAS = 0xFFFF
J_BIT = 66
FRACTION_HIGH_BIT = 65
INDEX_FOR_CELL = {
    36: 0,
    44: 1,
    52: 2,
    60: 3,
    18: 4,
    22: 5,
    26: 6,
    30: 7,
}


def internal_fields(value: h58.FP) -> tuple[int, int]:
    if value[0] or not value[1]:
        raise ValueError(f"expected positive finite magnitude: {value}")
    width = value[1].bit_length()
    if width > J_BIT + 1:
        raise ValueError(f"magnitude exceeds P6 carrier: {value}")
    unbiased = value[2] + width - 1
    exponent = (unbiased + INTERNAL_EXPONENT_BIAS) & 0x1FFFF
    mantissa = value[1] << (J_BIT + 1 - width)
    assert (mantissa >> J_BIT) == 1
    return exponent, mantissa


def sem_index(value: h58.FP, fraction_bits: int) -> int:
    exponent, mantissa = internal_fields(value)
    fraction = (
        mantissa >> (FRACTION_HIGH_BIT - fraction_bits + 1)
    ) & ((1 << fraction_bits) - 1)
    return ((exponent & 1) << fraction_bits) | fraction


def breakpoint(value: h58.FP, fraction_bits: int) -> h58.FP:
    exponent, mantissa = internal_fields(value)
    retained_low_bit = FRACTION_HIGH_BIT - fraction_bits + 1
    retained = mantissa & ~((1 << retained_low_bit) - 1)
    retained |= 1 << (retained_low_bit - 1)
    unbiased = exponent - INTERNAL_EXPONENT_BIAS
    return 1, retained, unbiased - J_BIT


def fp_equal(left: h58.FP, right: h58.FP) -> bool:
    return h58.add_exact(left, h58.neg(right))[1] == 0


def check_points() -> None:
    totals = {
        "dense": 0,
        "sweep": 0,
    }
    four_bit_index_mismatches = 0
    four_bit_residual_mismatches = 0
    seen_cells: set[int] = set()
    seen_sources: set[str] = set()
    for name in totals:
        for point in h228.points(name):
            observed = point.prepared.joint.observed
            prepared = observed.point
            totals[name] += 1
            seen_cells.add(prepared.cell)
            seen_sources.add(observed.source)

            expected_anchor = (1, prepared.cell, -6)
            magnitude = h58.add_exact(prepared.a, h58.neg(expected_anchor))

            index = sem_index(magnitude, 2)
            expected_index = INDEX_FOR_CELL[prepared.cell]
            if index != expected_index:
                raise AssertionError(
                    f"{name} index {index} != {expected_index}: {observed}"
                )

            anchor = breakpoint(magnitude, 2)
            if not fp_equal(anchor, expected_anchor):
                raise AssertionError(
                    f"{name} anchor {anchor} != {expected_anchor}: {observed}"
                )
            residual = h58.add_exact(magnitude, anchor)
            if not fp_equal(residual, prepared.a):
                raise AssertionError(
                    f"{name} residual {residual} != {prepared.a}: {observed}"
                )

            if sem_index(magnitude, 4) != expected_index:
                four_bit_index_mismatches += 1
            four_bit_residual = h58.add_exact(
                magnitude, breakpoint(magnitude, 4)
            )
            if not fp_equal(four_bit_residual, prepared.a):
                four_bit_residual_mismatches += 1

    expected_cells = set(INDEX_FOR_CELL) - {60}
    if seen_cells != expected_cells:
        raise AssertionError(f"active cells {seen_cells} != {expected_cells}")
    if seen_sources != {"direct", "reduced"}:
        raise AssertionError(f"active sources: {seen_sources}")
    count = sum(totals.values())
    print(
        "Two-fraction-bit index, anchor, residual parity: "
        f"{count}/{count} ({totals})"
    )
    print(
        "Four-fraction-bit index/midpoint falsifier: "
        f"index mismatches={four_bit_index_mismatches}/{count}, "
        f"residual mismatches={four_bit_residual_mismatches}/{count}"
    )


def sincos(x: Decimal) -> tuple[Decimal, Decimal]:
    square = x * x
    sine = x
    term = x
    n = 1
    while True:
        term = -term * square / Decimal((2 * n) * (2 * n + 1))
        updated = sine + term
        if updated == sine:
            break
        sine = updated
        n += 1

    cosine = Decimal(1)
    term = Decimal(1)
    n = 1
    while True:
        term = -term * square / Decimal((2 * n - 1) * (2 * n))
        updated = cosine + term
        if updated == cosine:
            break
        cosine = updated
        n += 1
    return sine, cosine


def nearest_even(value: Decimal) -> int:
    lower = int(value)
    fraction = value - lower
    if fraction > Decimal("0.5") or (
        fraction == Decimal("0.5") and lower & 1
    ):
        return lower + 1
    return lower


def check_table_constants() -> None:
    getcontext().prec = 180
    checked = 0
    for cosine, rows in ((False, h58.SIN_ROW), (True, h58.COS_ROW)):
        for cell, row in rows.items():
            value = h58.ROM[row]
            sine, cosine_value = sincos(Decimal(cell) / 64)
            exact = cosine_value if cosine else sine
            expected = nearest_even(exact * (Decimal(2) ** -value[2]))
            if value[0] or value[1] != expected or value[1].bit_length() != 67:
                raise AssertionError(
                    f"row {row} is not RN67 {'cos' if cosine else 'sin'}"
                    f"({cell}/64): {value} expected significand {expected:x}"
                )
            checked += 1
    print(f"table constants equal mathematical RN67 sin/cos: {checked}/{checked}")


def main() -> None:
    check_points()
    check_table_constants()


if __name__ == "__main__":
    main()
