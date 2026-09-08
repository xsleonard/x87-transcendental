#!/usr/bin/env python3
"""Exhaust fixed 65-bit LSB/guard/sticky rounding laws at both powers.

h1334's odd65-square/chop65-fourth schedule is the strongest scalar
representation so far, but round-to-odd may only be an alias for an unknown
jam/round controller.  A conventional fixed round decision is a Boolean
function of the retained LSB, guard, and sticky.  This audit exhausts all 256
such truth tables, with exact results always preserved, first at the square
while fourth remains chop65 and then at the fourth while square remains
odd65.  Chop, away, RN-even, and round-to-odd are strict members of the tested
grammar.

The truth table is operation-level and global; it never reads an operand
identity or hardware label.  Hardware labels are immutable inputs and this
program executes no x87 instruction.
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


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def quantize_law(operation: ExactOperation, bits: int, law: int) -> Value:
    shift = max(0, operation.magnitude.bit_length() - bits)
    retained = operation.magnitude >> shift
    remainder = operation.magnitude & ((1 << shift) - 1) if shift else 0
    if remainder:
        guard = (remainder >> (shift - 1)) & 1
        sticky = int(bool(remainder & ((1 << (shift - 1)) - 1)))
        index = (retained & 1) | (guard << 1) | (sticky << 2)
        retained += (law >> index) & 1
    if retained == 1 << bits:
        retained >>= 1
        shift += 1
    return Value(operation.sign, operation.exponent + shift, retained)


def factor_from_fourth(fourth: Value) -> Value:
    negative = quantize_mode(
        multiply(fourth, Value(*CONSTANTS[5])), 67, "chop")
    negative = quantize(
        add_same_sign(Value(*CONSTANTS[3]), negative), 64, True)
    negative = quantize_mode(multiply(fourth, negative), 67, "chop")
    return quantize(
        add_same_sign(Value(*CONSTANTS[1]), negative), 64, True)


def score_candidate(prepared, family: str, law: int):
    counts = Counter()
    diagnostics = []
    for operand, magnitude, baseline, wanted, bank in prepared:
        square_op = multiply(magnitude, magnitude)
        if family == "square_law_fourth_chop":
            square = quantize_law(square_op, 65, law)
            fourth = quantize_mode(multiply(square, square), 65, "chop")
        elif family == "square_odd_fourth_law":
            square = quantize_mode(square_op, 65, "odd")
            fourth = quantize_law(multiply(square, square), 65, law)
        else:
            raise ValueError(family)
        delta = magnitude_delta(factor_from_fourth(fourth), baseline)
        predicted = int(delta == -1)
        wrong = predicted != wanted
        counts["errors"] += wrong
        counts[f"bank{bank}.errors"] += wrong
        counts["positive_errors"] += wrong and wanted
        counts["negative_errors"] += wrong and not wanted
        counts["predicted_positives"] += predicted
        counts[f"delta.{delta}"] += 1
        diagnostics.append((operand, wanted, predicted, delta, bank))
    item = (
        counts["errors"], counts["bank1.errors"], counts["bank0.errors"],
        counts["positive_errors"], counts["negative_errors"],
        counts["predicted_positives"], counts["delta.-1"],
        counts["delta.0"],
        len(prepared) - counts["delta.-1"] - counts["delta.0"],
        family, law,
    )
    return item, diagnostics


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
    diagnostics = {}
    for family in ("square_law_fourth_chop", "square_odd_fourth_law"):
        for law in range(256):
            item, rows_out = score_candidate(prepared, family, law)
            scores.append(item)
            diagnostics[(family, law)] = rows_out
    scores.sort()
    best = scores[0]

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write(f"model_sha256\t{digest(args.model)}\n")
        for index, path in enumerate(args.direct_label):
            output.write(f"direct_labels_sha256.{index}\t{digest(path)}\n")
        output.write("hardware_policy\tfrozen_one_shot_labels_no_x87_execution\n")
        output.write("candidate_policy\tfixed_65bit_lsb_guard_sticky_round_laws\n")
        output.write(f"operands\t{len(prepared)}\n")
        output.write(f"positive_operands\t{sum(labels.values())}\n")
        output.write(f"candidates\t{len(scores)}\n")
        output.write(f"exact_candidates\t{sum(not item[0] for item in scores)}\n")
        output.write("law_index\tretained_lsb|(guard<<1)|(sticky<<2)\n")
        output.write("known_law.chop\t00\n")
        output.write("known_law.away\tff\n")
        output.write("known_law.odd\t55\n")
        output.write("\n[ranking]\n")
        output.write(
            "errors\textension_errors\tolder_errors\tpositive_errors\t"
            "negative_errors\tpredicted_positives\tdelta_minus1\t"
            "delta_zero\tdelta_other\tfamily\tlaw_hex\n")
        for item in scores:
            rendered = (*item[:-1], f"{item[-1]:02x}")
            output.write("\t".join(map(str, rendered)) + "\n")
        output.write("\n[best diagnostics]\n")
        output.write("op\twanted_wide\tpredicted_wide\tfactor_delta\tbank\n")
        for item in diagnostics[(best[9], best[10])]:
            output.write("\t".join(map(str, item)) + "\n")

    print(
        f"wrote {args.report}: operands={len(prepared)} "
        f"candidates={len(scores)} exact={sum(not item[0] for item in scores)} "
        f"best={best}",
        flush=True,
    )


if __name__ == "__main__":
    main()
