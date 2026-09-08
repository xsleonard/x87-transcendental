#!/usr/bin/env python3
"""Audit fixed-width and double-round arithmetic explanations of high-q.

The fixed-mode audit h1316 keeps every recovered stage width unchanged.
This pass tests the complementary closed arithmetic grammar: uniform product
and add widths, one-stage width/mode substitutions, two-stage rerounding at
each recovered operation, and a genuinely fused final multiply-add.  Every
candidate is one global schedule; no operand field or label selects a route.

All candidate factors are finally projected to RN64 before comparison with
the recovered factor, so ``delta=-1`` denotes the causally established wider
endpoint.  Hardware labels are immutable inputs and this program executes no
x87 instruction.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from h1184_upstream_halfway_audit import (
    CONSTANTS,
    ExactOperation,
    Value,
    add_same_sign,
    multiply,
    row_value,
)
from h1191_grs_history_isomorphism import magnitude_delta, quantize_mode
from h1210_stagea_residual_reframe import parse_dump, run
from h1316_highq_fixed_schedule_representations import load_direct


STAGES = ("square", "fourth", "mul1", "add1", "mul2", "add2")
BASE_WIDTHS = (67, 67, 67, 64, 67, 64)
BASE_MODES = ("chop", "chop", "chop", "rn", "chop", "rn")
MODES = ("chop", "rn", "away", "odd")


@dataclass(frozen=True)
class Candidate:
    family: str
    name: str
    widths: tuple[int, ...] = BASE_WIDTHS
    modes: tuple[str, ...] = BASE_MODES
    reround_stage: int | None = None
    fused_final: bool = False


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def as_operation(value: Value) -> ExactOperation:
    return ExactOperation(value.sign, value.exponent, value.significand)


def materialize(operation: ExactOperation, bits: int, mode: str,
                native_bits: int, native_mode: str,
                reround: bool) -> Value:
    first = quantize_mode(operation, bits, mode)
    return (
        quantize_mode(as_operation(first), native_bits, native_mode)
        if reround else first
    )


def fused_add(constant: Value, product: ExactOperation) -> ExactOperation:
    return add_same_sign(
        constant,
        Value(product.sign, product.exponent, product.magnitude),
    )


def recurrence(magnitude: Value, candidate: Candidate) -> Value:
    values: list[Value] = []

    square_op = multiply(magnitude, magnitude)
    values.append(materialize(
        square_op, candidate.widths[0], candidate.modes[0],
        BASE_WIDTHS[0], BASE_MODES[0], candidate.reround_stage == 0))

    fourth_op = multiply(values[0], values[0])
    values.append(materialize(
        fourth_op, candidate.widths[1], candidate.modes[1],
        BASE_WIDTHS[1], BASE_MODES[1], candidate.reround_stage == 1))

    mul1_op = multiply(values[1], Value(*CONSTANTS[5]))
    values.append(materialize(
        mul1_op, candidate.widths[2], candidate.modes[2],
        BASE_WIDTHS[2], BASE_MODES[2], candidate.reround_stage == 2))

    add1_op = add_same_sign(Value(*CONSTANTS[3]), values[2])
    values.append(materialize(
        add1_op, candidate.widths[3], candidate.modes[3],
        BASE_WIDTHS[3], BASE_MODES[3], candidate.reround_stage == 3))

    mul2_op = multiply(values[1], values[3])
    if candidate.fused_final:
        add2_op = fused_add(Value(*CONSTANTS[1]), mul2_op)
    else:
        values.append(materialize(
            mul2_op, candidate.widths[4], candidate.modes[4],
            BASE_WIDTHS[4], BASE_MODES[4], candidate.reround_stage == 4))
        add2_op = add_same_sign(Value(*CONSTANTS[1]), values[4])
    result = materialize(
        add2_op, candidate.widths[5], candidate.modes[5],
        BASE_WIDTHS[5], BASE_MODES[5], candidate.reround_stage == 5)
    return quantize_mode(as_operation(result), 64, "rn")


def candidates() -> list[Candidate]:
    result = [Candidate("baseline", "baseline")]

    # One global width/mode substitution at one recovered operation.
    for stage, stage_name in enumerate(STAGES):
        for width in range(60, 81):
            for mode in MODES:
                widths = list(BASE_WIDTHS)
                modes = list(BASE_MODES)
                widths[stage] = width
                modes[stage] = mode
                result.append(Candidate(
                    "single_stage",
                    f"{stage_name}.{mode}{width}",
                    tuple(widths), tuple(modes),
                ))

    # One wider first rounding followed by the recovered native rounding.
    for stage, stage_name in enumerate(STAGES):
        for width in range(BASE_WIDTHS[stage] + 1, 81):
            for mode in MODES:
                widths = list(BASE_WIDTHS)
                modes = list(BASE_MODES)
                widths[stage] = width
                modes[stage] = mode
                result.append(Candidate(
                    "reround",
                    f"{stage_name}.{mode}{width}.then_"
                    f"{BASE_MODES[stage]}{BASE_WIDTHS[stage]}",
                    tuple(widths), tuple(modes), stage,
                ))

    # Uniform physical precision classes, with the square/fourth included.
    for product_width, add_width, product_mode, add_mode in itertools.product(
            range(64, 73), range(60, 73), MODES, MODES):
        result.append(Candidate(
            "uniform",
            f"products.{product_mode}{product_width}."
            f"adds.{add_mode}{add_width}",
            (product_width, product_width, product_width, add_width,
             product_width, add_width),
            (product_mode, product_mode, product_mode, add_mode,
             product_mode, add_mode),
        ))

    for width in range(60, 81):
        for mode in MODES:
            widths = list(BASE_WIDTHS)
            modes = list(BASE_MODES)
            widths[5] = width
            modes[5] = mode
            result.append(Candidate(
                "fused_final", f"fused_final.{mode}{width}",
                tuple(widths), tuple(modes), fused_final=True,
            ))
    return list(dict.fromkeys(result))


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

    candidate_list = candidates()
    scores = []
    exact = []
    for candidate in candidate_list:
        counts = Counter()
        for _, magnitude, baseline, wanted, bank in prepared:
            delta = magnitude_delta(recurrence(magnitude, candidate), baseline)
            predicted = int(delta == -1)
            wrong = predicted != wanted
            counts["errors"] += wrong
            counts[f"bank{bank}.errors"] += wrong
            counts["positive_errors"] += wrong and wanted
            counts["negative_errors"] += wrong and not wanted
            counts["predicted_positives"] += predicted
            counts[f"delta.{delta}"] += 1
        item = (
            counts["errors"], counts["bank1.errors"],
            counts["bank0.errors"], counts["positive_errors"],
            counts["negative_errors"], counts["predicted_positives"],
            counts["delta.-1"], counts["delta.0"],
            len(prepared) - counts["delta.-1"] - counts["delta.0"],
            candidate.family, candidate.name,
        )
        scores.append(item)
        if not item[0]:
            exact.append(item)
    scores.sort()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write(f"model_sha256\t{digest(args.model)}\n")
        for index, path in enumerate(args.direct_label):
            output.write(
                f"direct_labels_sha256.{index}\t{digest(path)}\n")
        output.write("hardware_policy\tfrozen_one_shot_labels_no_x87_execution\n")
        output.write(
            "candidate_policy\tfixed_width_reround_and_fused_arithmetic\n")
        output.write(f"operands\t{len(prepared)}\n")
        output.write(f"positive_operands\t{sum(labels.values())}\n")
        output.write(f"candidates\t{len(candidate_list)}\n")
        output.write(f"exact_candidates\t{len(exact)}\n")
        output.write("\n[ranking]\n")
        output.write(
            "errors\textension_errors\tolder_errors\tpositive_errors\t"
            "negative_errors\tpredicted_positives\tdelta_minus1\t"
            "delta_zero\tdelta_other\tfamily\tcandidate\n")
        for item in scores[:1024]:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[exact candidates]\n")
        for item in exact:
            output.write("\t".join(map(str, item)) + "\n")

    print(
        f"wrote {args.report}: operands={len(prepared)} "
        f"candidates={len(candidate_list)} exact={len(exact)} "
        f"best={scores[0][:6]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
