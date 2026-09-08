#!/usr/bin/env python3
"""Audit the radix-8 signed-low-digit square representation for dcc.

The existing QX square decomposition writes ``m = 8*h + low3`` and merges
the positive row ``low3*m`` after a 67x64 product of ``m*h``.  A radix-8
Booth recoder uses an isomorphic but structurally different representation:

    low3 = digit + 8*carry,  digit in [-4, 3]
    m*m  = 8*m*(h + carry) + digit*m.

For low3=6, the external row is therefore -2*m and the high multiplier is
incremented.  This audit constructs that literal signed representation and
feeds its residue pair into fixed block-local comparator recurrences.  It
scores the resulting comparator endpoints over the complete cached dcc cell;
hardware is never executed and no operand threshold is fitted.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
from collections import Counter
from pathlib import Path

from h1100_p5_multiplier_tree import TREE_MASK, csa3, multiplier_tree
from h1101_p5_tree_mine import carry_between as tree_carry_between
from h1129_r60_redundant_comparator_mine import (
    MASK,
    WIDTH,
    carry_between,
    less_with_carry,
    negate_rows,
    reduce_balanced,
)
from h1172_p5_cpa_predictor_mine import add_cpa_features
from h1178_round_history_state_audit import signed128
from h1275_dcc_dense_structural_audit import SCOPE, TARGET


OFFSETS = range(-32, 17)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def bit(value: int, position: int) -> int:
    return (value >> position) & 1 if position >= 0 else 0


def signed_square(multiplier: int):
    low3 = multiplier & 7
    carry_digit = int(low3 >= 4)
    digit = low3 - 8 * carry_digit
    high = (multiplier >> 3) + carry_digit
    if not 0 <= high < (1 << 64):
        raise OverflowError("signed radix-8 high digit exceeded 64 bits")
    state = multiplier_tree(multiplier, high)
    external = (digit * multiplier) & TREE_MASK
    square_sum, square_carry = csa3(
        (state["sum"] << 3) & TREE_MASK,
        (state["carry"] << 3) & TREE_MASK,
        external,
    )
    square = multiplier * multiplier
    if ((square_sum + square_carry) & TREE_MASK) != square:
        raise AssertionError("signed-low Booth square changed exact product")
    return digit, carry_digit, state, square_sum, square_carry


def vector_features(values: dict[str, int], prefix: str,
                    sum_vector: int, carry_vector: int, cut: int) -> None:
    carries = [0]
    for position in range(cut + 18):
        a = bit(sum_vector, position)
        b = bit(carry_vector, position)
        carries.append((a & b) | ((a ^ b) & carries[-1]))
    for offset in OFFSETS:
        position = cut + offset
        a = bit(sum_vector, position)
        b = bit(carry_vector, position)
        values[f"{prefix}.sum.{offset:+d}"] = a
        values[f"{prefix}.carry.{offset:+d}"] = b
        values[f"{prefix}.propagate.{offset:+d}"] = a ^ b
        values[f"{prefix}.generate.{offset:+d}"] = a & b
        values[f"{prefix}.kill.{offset:+d}"] = 1 ^ (a | b)
        values[f"{prefix}.cin.{offset:+d}"] = (
            carries[position] if 0 <= position < len(carries) else 0)

    cpa: dict[str, int] = {}
    add_cpa_features(cpa, prefix, sum_vector, carry_vector, cut)
    values.update(cpa)


def comparator_predictions(
    linear_rows: list[int],
    square_rows: list[int],
    overflow: int,
    threshold: int,
    tag: str,
) -> dict[str, int]:
    predictions: dict[str, int] = {}
    raw_rows = list(linear_rows)
    raw_rows.extend(negate_rows(square_rows))
    raw_rows.append((-threshold) & MASK)
    corrected_rows = list(raw_rows)
    if overflow:
        corrected_rows.append(overflow << 67)

    for form, rows in (("raw", raw_rows), ("mod", corrected_rows)):
        sum_vector, carry_vector = reduce_balanced(rows)
        exact_carry = carry_between(sum_vector, carry_vector, 0, 66, 0)
        predictions[f"{tag}.{form}.exact"] = 1 - less_with_carry(
            sum_vector, carry_vector, exact_carry)
        for width in range(1, 33):
            start = 66 - width
            for assumed in (0, 1):
                local = carry_between(
                    sum_vector, carry_vector, start, 66, assumed)
                predictions[
                    f"{tag}.{form}.rel{width:02d}.c{assumed}"
                ] = 1 - less_with_carry(sum_vector, carry_vector, local)
        for width in (2, 4, 8, 16, 32, 64):
            start = 66 - (66 % width)
            for assumed in (0, 1):
                local = carry_between(
                    sum_vector, carry_vector, start, 66, assumed)
                predictions[
                    f"{tag}.{form}.abs{width:02d}.c{assumed}"
                ] = 1 - less_with_carry(sum_vector, carry_vector, local)
    return predictions


def row_state(row: dict[str, str], detailed: bool
              ) -> tuple[dict[str, int], dict[str, int]]:
    multiplier = int(row["tc_mul_sig"], 16)
    low3 = multiplier & 7
    if low3 != int(row["low3"]):
        raise AssertionError("low3 mismatch")
    digit, carry_digit, high_state, square_sum, square_carry = (
        signed_square(multiplier))
    square = multiplier * multiplier
    square_cut = square.bit_length() - 67
    values: dict[str, int] = {
        "signed_low.digit_negative": int(digit < 0),
        "signed_low.digit_abs3": int(abs(digit) == 3),
        "signed_low.carry": carry_digit,
    }
    high_cut = (multiplier * ((multiplier >> 3) + carry_digit)).bit_length() - 67
    if detailed:
        vector_features(
            values, "signed_square.final", square_sum, square_carry,
            square_cut)
        vector_features(
            values, "signed_square.high", high_state["sum"],
            high_state["carry"], high_cut)

        for node_name, node in high_state["nodes"].items():
            for vector_name in ("sum", "carry", "first_sum", "first_carry"):
                for offset in range(-8, 5):
                    values[
                        f"signed_square.high.{node_name}.{vector_name}."
                        f"{offset:+d}"
                    ] = bit(node[vector_name], high_cut + offset)

    residue_mask = (1 << 67) - 1
    sum_residue = square_sum & residue_mask
    carry_residue = square_carry & residue_mask
    residue_total = sum_residue + carry_residue
    if (residue_total & residue_mask) != int(row["t4"], 16):
        raise AssertionError("signed-low residue disagrees with exact t4")
    overflow = residue_total >> 67
    values["signed_square.residue_overflow"] = overflow
    if detailed:
        for position in range(48, 69):
            values[f"signed_square.sum_residue.abs{position}"] = bit(
                sum_residue, position)
            values[f"signed_square.carry_residue.abs{position}"] = bit(
                carry_residue, position)

    sqlow = multiplier - (1 << 66)
    scalar_linear = [low3 * sqlow]
    booth_linear = [digit * sqlow, carry_digit * (8 * sqlow)]
    current_low3 = int(row["low3"])
    base0 = (2 * current_low3 + 2 * int(row["b1"])
             + 3 * int(row["b2"]) - 3 * (current_low3 & 1) - 6)
    u0 = 2 * (base0 // 8) + (current_low3 & 1)
    threshold = u0 << 66
    predictions = {}
    predictions.update(comparator_predictions(
        scalar_linear, [sum_residue, carry_residue], overflow,
        threshold, "scalar_linear"))
    predictions.update(comparator_predictions(
        booth_linear, [sum_residue, carry_residue], overflow,
        threshold, "booth_linear"))

    # Expose whether block-local carry in the signed square differs from the
    # exact carry.  These are structural localization signals, not direct
    # predictions; threshold-plus-one scoring below tests their natural role.
    if detailed:
        for end in (66, 67, 68):
            exact = tree_carry_between(square_sum, square_carry, 0, end, 0)
            for width in range(1, 33):
                start = end - width
                for assumed in (0, 1):
                    local = tree_carry_between(
                        square_sum, square_carry, start, end, assumed)
                    values[
                        f"signed_square.local.end{end}.rel{width:02d}."
                        f"c{assumed}.carry"
                    ] = local
                    values[
                        f"signed_square.local.end{end}.rel{width:02d}."
                        f"c{assumed}.mismatch"
                    ] = local ^ exact
    return values, predictions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("labels", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--detailed", action="store_true")
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    with args.labels.open(newline="") as source:
        labels = {(row["corpus"], row["index"]): row
                  for row in csv.DictReader(source, delimiter="\t")}
    feature_scores: dict[str, Counter] = {}
    prediction_scores: dict[str, Counter] = {}
    target_diagnostics = None
    rows = 0
    with gzip.open(args.features, "rt", newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            if not all(row[name] == value for name, value in SCOPE.items()):
                continue
            label = labels[(row["corpus"], row["index"])]
            if label["selector_status"] != "constraining":
                continue
            rows += 1
            desired = int(label["allowed_carry"])
            current = int(label["current_carry"])
            target = row["op"] == TARGET
            values, predictions = row_state(row, args.detailed)
            low3 = int(row["low3"])
            base0 = (2 * low3 + 2 * int(row["b1"])
                     + 3 * int(row["b2"]) - 3 * (low3 & 1) - 6)
            u0 = 2 * (base0 // 8) + (low3 & 1)
            mreg = signed128(row["Mreg"])

            if not feature_scores:
                feature_scores = {name: Counter() for name in values}
                prediction_scores = {name: Counter() for name in predictions}
            elif set(values) != set(feature_scores) or set(predictions) != set(
                    prediction_scores):
                raise RuntimeError("signed-low feature schema changed")

            for name, predicate in values.items():
                predicted = int(not (
                    mreg < (u0 + int(bool(predicate))) * (1 << 66)))
                changed = predicted != current
                score = feature_scores[name]
                score["errors"] += predicted != desired
                score["target_miss"] += target and not changed
                score["control_fire"] += changed and not target
                score["fires"] += changed
            for name, predicted in predictions.items():
                changed = predicted != current
                score = prediction_scores[name]
                score["errors"] += predicted != desired
                score["target_miss"] += target and not changed
                score["control_fire"] += changed and not target
                score["fires"] += changed
            if target:
                target_diagnostics = (values, predictions, desired, current)
            if rows % 10000 == 0:
                print(f"features {rows}", flush=True)

    feature_ranking = sorted(
        (score["errors"], score["target_miss"], score["control_fire"],
         score["fires"], name)
        for name, score in feature_scores.items())
    prediction_ranking = sorted(
        (score["errors"], score["target_miss"], score["control_fire"],
         score["fires"], name)
        for name, score in prediction_scores.items())
    if target_diagnostics is None:
        raise RuntimeError("target absent from dense cell")

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"features_sha256\t{digest(args.features)}\n")
        target.write(f"labels_sha256\t{digest(args.labels)}\n")
        target.write(f"rows\t{rows}\n")
        target.write("hardware_policy\tcached_labels_only_no_x87_execution\n")
        target.write("representation\tlow3=digit+8*carry digit_in_-4_to_3\n")
        target.write(f"detailed_features\t{int(args.detailed)}\n")
        target.write("\n[direct signed-comparator ranking]\n")
        target.write("errors\ttarget_miss\tcontrol_fire\tfires\tpredictor\n")
        for score in prediction_ranking:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[one-cell threshold-extension ranking]\n")
        target.write("errors\ttarget_miss\tcontrol_fire\tfires\tfeature\n")
        for score in feature_ranking[:2000]:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[target active signals]\n")
        values, predictions, desired, current = target_diagnostics
        target.write(f"desired\t{desired}\ncurrent\t{current}\n")
        for name in sorted(name for name, value in values.items() if value):
            target.write(f"feature\t{name}\n")
        for name in sorted(
                name for name, value in predictions.items() if value != current):
            target.write(f"changing_predictor\t{name}\t{predictions[name]}\n")

    print(
        f"wrote {args.report} rows={rows} "
        f"best_direct={prediction_ranking[0]} "
        f"best_extension={feature_ranking[0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
