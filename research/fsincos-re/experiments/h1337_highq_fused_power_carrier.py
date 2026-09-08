#!/usr/bin/env python3
"""Test exact and one-sided fused fourth-power representations.

The odd65/chop65 lead from h1334 behaves like a jammed low bit carried from
the first square into the second.  A scalar round-to-odd value is only one
possible representation of that information.  This audit tests the more
literal alternatives in which the discarded first-square tail remains
attached when the square is consumed again: both fourth-product operands are
exact (the direct m**4 product), or one is exact while the other is the
recovered chopped-67 square.  The resulting fourth product is quantized at
each fixed 60--80-bit chop/RN/away/odd format, then passed through the
recovered Horner chain.

Every candidate is a global arithmetic schedule.  Hardware labels are
immutable inputs and this program executes no x87 instruction.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from pathlib import Path

from h1184_upstream_halfway_audit import (
    CONSTANTS,
    ExactOperation,
    Value,
    add_same_sign,
    multiply,
    quantize,
    row_value,
)
from h1191_grs_history_isomorphism import magnitude_delta, quantize_mode
from h1210_stagea_residual_reframe import parse_dump, run
from h1316_highq_fixed_schedule_representations import load_direct
from h1332_highq_width_double_round_audit import MODES


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def factor_from_fourth(fourth: Value) -> Value:
    negative = quantize_mode(
        multiply(fourth, Value(*CONSTANTS[5])), 67, "chop")
    negative = quantize(
        add_same_sign(Value(*CONSTANTS[3]), negative), 64, True)
    negative = quantize_mode(multiply(fourth, negative), 67, "chop")
    return quantize(
        add_same_sign(Value(*CONSTANTS[1]), negative), 64, True)


def fourth_operation(magnitude: Value, family: str) -> ExactOperation:
    square_exact = multiply(magnitude, magnitude)
    square_chop67 = quantize_mode(square_exact, 67, "chop")
    if family == "exact_exact":
        return ExactOperation(
            0, 4 * magnitude.exponent, magnitude.significand ** 4)
    if family == "exact_chop67":
        return ExactOperation(
            0,
            square_exact.exponent + square_chop67.exponent,
            square_exact.magnitude * square_chop67.significand,
        )
    raise ValueError(family)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument(
        "--direct-label", action="append", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")
    if len(args.direct_label) != 2:
        raise SystemExit("supply the older bank and extension bank in order")

    labels: dict[str, int] = {}
    source_bank: dict[str, int] = {}
    for bank, path in enumerate(args.direct_label):
        bank_labels: dict[str, int] = {}
        load_direct(path, bank_labels)
        overlap = set(labels) & set(bank_labels)
        if overlap:
            raise RuntimeError(f"direct-label banks overlap: {sorted(overlap)}")
        labels.update(bank_labels)
        for operand in bank_labels:
            source_bank[operand] = bank
    operands = sorted(labels)
    _, stderr = run(args.model, "rn", operands, dump=True)
    rows = parse_dump(stderr, operands)
    prepared = [(
        row["op"], row_value(row, "mag"), row_value(row, "lf"),
        labels[row["op"]], source_bank[row["op"]],
    ) for row in rows]

    scores = []
    diagnostics: dict[tuple[str, int, str], list[tuple[object, ...]]] = {}
    for family in ("exact_exact", "exact_chop67"):
        for width in range(60, 81):
            for mode in MODES:
                counts = Counter()
                rows_out = []
                for operand, magnitude, baseline, wanted, bank in prepared:
                    fourth = quantize_mode(
                        fourth_operation(magnitude, family), width, mode)
                    delta = magnitude_delta(factor_from_fourth(fourth), baseline)
                    predicted = int(delta == -1)
                    wrong = predicted != wanted
                    counts["errors"] += wrong
                    counts[f"bank{bank}.errors"] += wrong
                    counts["positive_errors"] += wrong and wanted
                    counts["negative_errors"] += wrong and not wanted
                    counts["predicted_positives"] += predicted
                    counts[f"delta.{delta}"] += 1
                    rows_out.append((operand, wanted, predicted, delta, bank))
                item = (
                    counts["errors"], counts["bank1.errors"],
                    counts["bank0.errors"], counts["positive_errors"],
                    counts["negative_errors"], counts["predicted_positives"],
                    counts["delta.-1"], counts["delta.0"],
                    len(prepared) - counts["delta.-1"] - counts["delta.0"],
                    family, width, mode,
                )
                scores.append(item)
                diagnostics[(family, width, mode)] = rows_out
    scores.sort()
    best = scores[0]
    best_key = (best[9], best[10], best[11])

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write(f"model_sha256\t{digest(args.model)}\n")
        for index, path in enumerate(args.direct_label):
            output.write(f"direct_labels_sha256.{index}\t{digest(path)}\n")
        output.write("hardware_policy\tfrozen_one_shot_labels_no_x87_execution\n")
        output.write("candidate_policy\tfixed_fused_fourth_power_representation\n")
        output.write(f"operands\t{len(prepared)}\n")
        output.write(f"positive_operands\t{sum(labels.values())}\n")
        output.write(f"candidates\t{len(scores)}\n")
        output.write(f"exact_candidates\t{sum(not item[0] for item in scores)}\n")
        output.write("\n[ranking]\n")
        output.write(
            "errors\textension_errors\tolder_errors\tpositive_errors\t"
            "negative_errors\tpredicted_positives\tdelta_minus1\t"
            "delta_zero\tdelta_other\tfamily\tfourth_width\tfourth_mode\n")
        for item in scores:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[best diagnostics]\n")
        output.write("op\twanted_wide\tpredicted_wide\tfactor_delta\tbank\n")
        for item in diagnostics[best_key]:
            output.write("\t".join(map(str, item)) + "\n")

    print(
        f"wrote {args.report}: operands={len(prepared)} "
        f"candidates={len(scores)} exact={sum(not item[0] for item in scores)} "
        f"best={best}",
        flush=True,
    )


if __name__ == "__main__":
    main()
