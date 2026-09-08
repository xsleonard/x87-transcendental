#!/usr/bin/env python3
"""Audit bounded attached precision differences at the terminal FSUB.

The terminal cosine operation consumes two independently chopped 67-bit
products.  A producer may attach a bounded precision difference to either
operand even though the scalar operand presented to FSUB remains chopped.
This experiment reconstructs the exact discarded product tails, quantizes
them on fixed binary grids, and injects the resulting signed correction into
the low-field subtraction carry.

Every candidate is a fixed arithmetic recurrence selected before labels are
examined: one-port or two-port history, joint or separately quantized tails,
and one of the standard directed/nearest/jammed quantizers.  Hardware labels
are used only to score the resulting carry.  No input identity, learned
threshold, or repeated hardware execution is involved.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path


ROUNDINGS = ("floor", "ceil", "zero", "away", "rn-even", "rn-away", "odd")
SOURCES = ("left", "minus-right", "left-minus-right")


@dataclass(frozen=True)
class Dyad:
    numerator: int
    exponent: int


@dataclass(frozen=True)
class Candidate:
    source: str
    layout: str
    rounding: str
    fractional_bits: int

    def name(self) -> str:
        return (f"{self.source}/{self.layout}/{self.rounding}/"
                f"frac{self.fractional_bits}")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def add(left: Dyad, right: Dyad) -> Dyad:
    exponent = min(left.exponent, right.exponent)
    return Dyad(
        (left.numerator << (left.exponent - exponent))
        + (right.numerator << (right.exponent - exponent)),
        exponent,
    )


def negate(value: Dyad) -> Dyad:
    return Dyad(-value.numerator, value.exponent)


def scaled(value: Dyad, exponent: int) -> int:
    shift = value.exponent - exponent
    if shift < 0:
        divisor = 1 << -shift
        if value.numerator % divisor:
            raise AssertionError("dyad is not integral at requested scale")
        return value.numerator // divisor
    return value.numerator << shift


def divide_round(numerator: int, denominator: int, mode: str) -> int:
    floor_value = numerator // denominator
    remainder = numerator - floor_value * denominator
    if not remainder:
        return floor_value
    ceil_value = floor_value + 1
    if mode == "floor":
        return floor_value
    if mode == "ceil":
        return ceil_value
    if mode == "zero":
        return ceil_value if numerator < 0 else floor_value
    if mode == "away":
        return floor_value if numerator < 0 else ceil_value
    if mode in ("rn-even", "rn-away"):
        doubled = 2 * remainder
        if doubled < denominator:
            return floor_value
        if doubled > denominator:
            return ceil_value
        if mode == "rn-away":
            return floor_value if numerator < 0 else ceil_value
        return floor_value if floor_value % 2 == 0 else ceil_value
    if mode == "odd":
        toward_zero = ceil_value if numerator < 0 else floor_value
        if toward_zero & 1:
            return toward_zero
        return toward_zero - 1 if numerator < 0 else toward_zero + 1
    raise ValueError(mode)


def quantize(value: Dyad, grid_exponent: int, mode: str) -> Dyad:
    shift = value.exponent - grid_exponent
    if shift >= 0:
        return Dyad(value.numerator << shift, grid_exponent)
    return Dyad(
        divide_round(value.numerator, 1 << -shift, mode), grid_exponent)


def product_tail(row: dict[str, str], first: str, second: str,
                 stored: str) -> Dyad:
    exact_exponent = int(row[f"tc_{first}_exp"]) + int(row[f"tc_{second}_exp"])
    exact = Dyad(
        int(row[f"tc_{first}_sig"], 16)
        * int(row[f"tc_{second}_sig"], 16),
        exact_exponent,
    )
    materialized = Dyad(
        int(row[f"tc_{stored}_sig"], 16),
        int(row[f"tc_{stored}_exp"]),
    )
    tail = add(exact, negate(materialized))
    if tail.numerator < 0:
        raise AssertionError(f"{stored} is not a chopped product for {row['op']}")
    return tail


def tails(row: dict[str, str]) -> tuple[Dyad, Dyad]:
    return (
        product_tail(row, "mul", "lf", "left"),
        product_tail(row, "f4", "rf", "right"),
    )


def source_value(left: Dyad, right: Dyad, source: str) -> Dyad:
    if source == "left":
        return left
    if source == "minus-right":
        return negate(right)
    if source == "left-minus-right":
        return add(left, negate(right))
    raise ValueError(source)


def quantized_correction(row: dict[str, str], candidate: Candidate) -> Dyad:
    left, right = tails(row)
    grid = int(row["rscale"]) - candidate.fractional_bits
    if candidate.layout == "joint":
        return quantize(
            source_value(left, right, candidate.source),
            grid,
            candidate.rounding,
        )
    if candidate.layout != "per-port":
        raise ValueError(candidate.layout)
    if candidate.source == "left":
        return quantize(left, grid, candidate.rounding)
    if candidate.source == "minus-right":
        return negate(quantize(right, grid, candidate.rounding))
    return add(
        quantize(left, grid, candidate.rounding),
        negate(quantize(right, grid, candidate.rounding)),
    )


def predicted_carry(row: dict[str, str], correction: Dyad) -> int:
    cut = int(row["k"])
    mask = (1 << cut) - 1
    low_difference = (
        (int(row["S"], 16) & mask) - (int(row["B"], 16) & mask)
    )
    base = Dyad(low_difference, int(row["rscale"]))
    corrected = add(base, correction)
    return int(corrected.numerator >= 0)


def exact_fraction(value: Dyad, exponent: int) -> Fraction:
    shift = value.exponent - exponent
    if shift >= 0:
        return Fraction(value.numerator << shift)
    return Fraction(value.numerator, 1 << -shift)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rows", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    with args.rows.open(newline="") as source:
        rows = [
            row for row in csv.DictReader(source, delimiter="\t")
            if row["physical_status"] == "constraining"
        ]
    candidates = [
        Candidate(source, layout, rounding, fractional_bits)
        for source in SOURCES
        for layout in ("joint", "per-port")
        for rounding in ROUNDINGS
        for fractional_bits in range(0, 17)
    ]

    ranking = []
    predictions: dict[Candidate, list[int]] = {}
    for candidate in candidates:
        values = [
            predicted_carry(row, quantized_correction(row, candidate))
            for row in rows
        ]
        target_miss = sum(
            prediction != int(row["physical_label"])
            and row["label"] == "POS"
            for row, prediction in zip(rows, values)
        )
        control_miss = sum(
            prediction != int(row["physical_label"])
            and row["label"] != "POS"
            for row, prediction in zip(rows, values)
        )
        ranking.append((
            target_miss + control_miss, target_miss, control_miss,
            candidate.name(), candidate,
        ))
        predictions[candidate] = values
    ranking.sort()

    # Include exact, unquantized one/two-port corrections as limiting cases.
    exact_scores = []
    exact_predictions = {}
    for source in SOURCES:
        values = [
            predicted_carry(row, source_value(*tails(row), source))
            for row in rows
        ]
        target_miss = sum(
            prediction != int(row["physical_label"])
            and row["label"] == "POS"
            for row, prediction in zip(rows, values)
        )
        control_miss = sum(
            prediction != int(row["physical_label"])
            and row["label"] != "POS"
            for row, prediction in zip(rows, values)
        )
        exact_scores.append((
            target_miss + control_miss, target_miss, control_miss, source,
        ))
        exact_predictions[source] = values
    exact_scores.sort()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"rows_sha256\t{digest(args.rows)}\n")
        target.write(f"rows\t{len(rows)}\n")
        target.write(
            f"targets\t{sum(row['label'] == 'POS' for row in rows)}\n")
        target.write(f"candidates\t{len(candidates)}\n")
        target.write("hardware_policy\tcached_labels_only_no_x87_execution\n")
        target.write("\n[quantized precision-difference ranking]\n")
        target.write("errors\ttarget_miss\tcontrol_miss\tcandidate\n")
        for score in ranking[:1000]:
            target.write("\t".join(map(str, score[:4])) + "\n")
        target.write("\n[exact precision-difference limits]\n")
        target.write("errors\ttarget_miss\tcontrol_miss\tsource\n")
        for score in exact_scores:
            target.write("\t".join(map(str, score)) + "\n")

        target.write("\n[target diagnostics]\n")
        target.write(
            "op\tphysical_carry\tbase_carry\tleft_tail_rscale\t"
            "right_tail_rscale\tdifference_rscale\tbest_prediction\t"
            "exact_left\texact_minus_right\texact_both\n"
        )
        best = ranking[0][4]
        best_values = predictions[best]
        for index, row in enumerate(rows):
            if row["label"] != "POS":
                continue
            left, right = tails(row)
            cut = int(row["k"])
            mask = (1 << cut) - 1
            base_carry = int(
                (int(row["S"], 16) & mask)
                >= (int(row["B"], 16) & mask)
            )
            rscale = int(row["rscale"])
            fields = (
                row["op"], int(row["physical_label"]), base_carry,
                exact_fraction(left, rscale),
                exact_fraction(right, rscale),
                exact_fraction(add(left, negate(right)), rscale),
                best_values[index],
                exact_predictions["left"][index],
                exact_predictions["minus-right"][index],
                exact_predictions["left-minus-right"][index],
            )
            target.write("\t".join(map(str, fields)) + "\n")

    print(
        f"wrote {args.report} rows={len(rows)} candidates={len(candidates)} "
        f"best={ranking[0][:4]} exact_best={exact_scores[0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
