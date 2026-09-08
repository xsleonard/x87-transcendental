#!/usr/bin/env python3
"""Test an exact-polynomial-tail representation of the R59 residual.

The staged P5 cosine kernel is algebraically a fixed six-term dyadic
polynomial.  This experiment collapses it to that exact rational polynomial
and exposes only arithmetic signals: bits of the exact correction, bits of
the difference from the materialized terminal correction, bits of individual
terms/Horner nodes, and direct-sum carries across binary columns.  It then
tests all sixteen two-input gates with the incumbent R59 carry.

This is not an input-boundary fit.  Every feature is fixed by the published
P5 ROM coefficients and exact integer arithmetic before hardware labels are
consulted.
"""

from __future__ import annotations

import argparse
import csv
import os
from fractions import Fraction

import numpy as np

from h1110_carry_gate_mine import (
    GATE_NAMES,
    allmode_allowed,
    extract_carry_state,
    gate_changes,
    gate_errors,
    state_bad_counts,
)


COEFFICIENTS = (
    (-1, -68, (0x7 << 64) | 0xFFFFFFFFFFFFFFFE),
    (+1, -71, (0x5 << 64) | 0x5555555555554277),
    (-1, -76, (0x5 << 64) | 0xB05B05B05A18A1BA),
    (+1, -82, (0x6 << 64) | 0x80680675B559F2CF),
    (-1, -88, (0x4 << 64) | 0x9F93AF61F5349300),
    (+1, -95, (0x4 << 64) | 0x7A4F2483514C1AF8),
)
COEFFICIENT_VALUES = tuple(
    sign * Fraction(significand) * Fraction(2) ** exponent
    for sign, exponent, significand in COEFFICIENTS
)
RELATIVE_BITS = range(-160, 17)


def floor_fraction(value: Fraction) -> int:
    return value.numerator // value.denominator


def scaled_floor(value: Fraction, exponent: int) -> int:
    return floor_fraction(value / (Fraction(2) ** exponent))


def scaled_bit(value: Fraction, exponent: int) -> int:
    return scaled_floor(value, exponent) & 1


def operand_value(operand: str) -> Fraction:
    se_text, significand_text = operand.split()
    se = int(se_text, 16)
    exponent = (se & 0x7FFF) - 16383
    sign = -1 if se >> 15 else 1
    return (
        sign
        * Fraction(int(significand_text, 16))
        * Fraction(2) ** (exponent - 63)
    )


def polynomial_state(operand: str) -> dict[str, object]:
    x = operand_value(operand)
    square = x * x
    powers = []
    power = square
    terms = []
    for coefficient in COEFFICIENT_VALUES:
        powers.append(power)
        terms.append(-coefficient * power)
        power *= square
    correction = sum(terms, Fraction(0))

    # Algebraically equivalent odd/even Horner partition used by the kernel.
    fourth = square * square
    negative = -COEFFICIENT_VALUES[0] + fourth * (
        -COEFFICIENT_VALUES[2] + fourth * -COEFFICIENT_VALUES[4]
    )
    positive = -COEFFICIENT_VALUES[1] + fourth * (
        -COEFFICIENT_VALUES[3] + fourth * -COEFFICIENT_VALUES[5]
    )
    factored = square * negative + fourth * positive
    if factored != correction:
        raise AssertionError("exact polynomial factorization mismatch")
    return {
        "correction": correction,
        "terms": terms,
        "negative": negative,
        "positive": positive,
        "square": square,
        "fourth": fourth,
    }


def arithmetic_features(row: dict[str, str]) -> dict[str, int]:
    state = polynomial_state(row["op"])
    correction = state["correction"]
    terms = state["terms"]
    retained_exponent = int(row["rscale"]) + int(row["k"])
    staged = Fraction(int(row["umag"], 16)) * Fraction(2) ** int(
        row["rscale"]
    )
    selected = Fraction(int(row["br_r"], 16)) * Fraction(2) ** retained_exponent
    values: dict[str, int] = {}
    families = {
        "correction": correction,
        "tail_vs_materialized": correction - staged,
        "tail_vs_selected": correction - selected,
        "exact_square": state["square"],
        "exact_fourth": state["fourth"],
        "odd_horner": state["negative"],
        "even_horner": state["positive"],
    }
    for index, term in enumerate(terms, 1):
        families[f"term{index}"] = term

    for family, number in families.items():
        for offset in RELATIVE_BITS:
            values[f"{family}.bit.{offset:+04d}"] = scaled_bit(
                number, retained_exponent + offset
            )

    # A direct polynomial summation has a well-defined cross-column carry.
    # Expose its signed carry count and low bits without choosing thresholds
    # from observed labels.
    for offset in RELATIVE_BITS:
        exponent = retained_exponent + offset
        direct_carry = scaled_floor(correction, exponent) - sum(
            scaled_floor(term, exponent) for term in terms
        )
        values[f"direct_sum.carry.nonzero.{offset:+04d}"] = direct_carry != 0
        values[f"direct_sum.carry.negative.{offset:+04d}"] = direct_carry < 0
        for bit_index in range(3):
            values[f"direct_sum.carry.bit{bit_index}.{offset:+04d}"] = (
                direct_carry >> bit_index
            ) & 1

    return values


def read_tsv(path: str) -> list[dict[str, str]]:
    with open(path, newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features")
    parser.add_argument("positive_allmode")
    parser.add_argument("control_allmode")
    parser.add_argument("output")
    args = parser.parse_args()
    if os.path.exists(args.output):
        raise SystemExit(f"refusing to overwrite {args.output}")

    positive_delta = allmode_allowed(args.positive_allmode)
    control_delta = allmode_allowed(args.control_allmode)
    rows = read_tsv(args.features)
    states = []
    feature_rows = []
    names = None
    for index, row in enumerate(rows):
        allowed_delta = (
            positive_delta if row["label"] == "POS" else control_delta
        )[row["op"]]
        states.append(extract_carry_state(row, allowed_delta))
        values = arithmetic_features(row)
        if names is None:
            names = sorted(values)
        elif set(values) != set(names):
            raise AssertionError("feature schema changed")
        feature_rows.append([int(values[name]) for name in names])
        if (index + 1) % 2000 == 0:
            print(f"features {index + 1}/{len(rows)}", flush=True)
    if names is None:
        raise SystemExit("empty feature table")

    matrix = np.asarray(feature_rows, dtype=np.uint8)
    current = np.asarray([state[2] for state in states], dtype=np.uint8)
    allowed = np.asarray(
        [[carry in state[3] for carry in (0, 1)] for state in states],
        dtype=bool,
    )
    capable = allowed.any(axis=1)
    positives = np.asarray([row["label"] == "POS" for row in rows])
    subsets = {
        "base": (~positives) & capable,
        "positive": positives & capable,
        "all": capable,
    }
    counts = {
        name: state_bad_counts(matrix, current, allowed, subset)
        for name, subset in subsets.items()
    }

    scores = []
    for gate in range(16):
        errors = {name: gate_errors(group, gate) for name, group in counts.items()}
        changes = gate_changes(matrix, current, subsets["base"], gate)
        for feature, name in enumerate(names):
            scores.append(
                (
                    int(errors["all"][feature]),
                    int(errors["positive"][feature]),
                    int(errors["base"][feature]),
                    int(changes[feature]),
                    GATE_NAMES[gate],
                    gate,
                    name,
                )
            )
    scores.sort()
    improvements = [score for score in scores if score[2] == 0 and score[1] < 26]
    exact = [score for score in scores if score[0] == 0]

    # Independently ask whether one arithmetic signal recognizes exactly the
    # three rows needing an upstream decrement.
    decrement_target = (~capable).astype(np.uint8)
    decrement_scores = []
    for feature, name in enumerate(names):
        column = matrix[:, feature]
        for invert in (0, 1):
            predicted = column ^ invert
            all_bad = int(np.count_nonzero(predicted != decrement_target))
            positive_bad = int(
                np.count_nonzero(positives & (predicted != decrement_target))
            )
            base_bad = int(
                np.count_nonzero((~positives) & (predicted != decrement_target))
            )
            decrement_scores.append(
                (all_bad, positive_bad, base_bad, invert, name)
            )
    decrement_scores.sort()

    with open(args.output, "w") as target:
        target.write(
            f"rows\t{len(rows)}\nfeatures\t{len(names)}\n"
            f"carry_capable\t{int(capable.sum())}\n"
            f"carry_impossible\t{int((~capable).sum())}\n"
        )
        target.write("\n[carry gate ranking]\n")
        target.write(
            "all_bad\tpositive_bad\tbase_bad\tbase_changes"
            "\tgate\tgate_mask\tfeature\n"
        )
        for score in scores[:1000]:
            target.write("\t".join(map(str, score)) + "\n")
        target.write(f"\n[zero-collateral improvements]\ncount\t{len(improvements)}\n")
        for score in improvements[:2000]:
            target.write("\t".join(map(str, score)) + "\n")
        target.write(f"\n[zero-error carry gates]\ncount\t{len(exact)}\n")
        for score in exact[:2000]:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[upstream decrement signal ranking]\n")
        target.write("all_bad\tpositive_bad\tbase_bad\tinvert\tfeature\n")
        for score in decrement_scores[:1000]:
            target.write("\t".join(map(str, score)) + "\n")

    print(
        "wrote",
        args.output,
        "rows",
        len(rows),
        "features",
        len(names),
        "best_carry",
        scores[0],
        "zero_collateral_improvements",
        len(improvements),
        "zero_error",
        len(exact),
        "best_decrement",
        decrement_scores[0],
        flush=True,
    )


if __name__ == "__main__":
    main()
