#!/usr/bin/env python3
"""Find fixed X67/Y64 edge placements isomorphic to the high-q factor.

h1357 found that replacing the shared fourth power by
``chop67(square * chop64(square))`` reproduces every direct factor label.
Changing the shared value in the full C graph is not equivalent: it also
perturbs the positive Horner chain.  This audit asks whether the same factor
response is produced by a narrower physical placement of the asymmetric
port at one of the negative-chain FMUL edges.

At square and fourth, the common operand may be routed to a full input or
materialized to Y64 with chop/RN/away/odd.  At each Horner multiply, either
operand may occupy such a Y64 input, or both remain full as a control.  FMUL
outputs retain the recovered chop67 rule and FADD retains RN64.  All choices
are global edge programs; no operand predicate or learned table is used.

Hardware labels are immutable one-shot inputs and this program executes no
x87 instruction.  Any exact local survivor must next be replayed through the
complete C datapath and challenged on a separately frozen bank.
"""

from __future__ import annotations

import argparse
import csv
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


MODES = ("chop", "rn", "away", "odd")
SAME_OPTIONS = ("full", *MODES)
MIXED_OPTIONS = ("full", *(f"left.{mode}" for mode in MODES), *(f"right.{mode}" for mode in MODES))


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def load_labels(paths: list[Path]) -> tuple[dict[str, int], dict[str, int]]:
    labels: dict[str, int] = {}
    sources: dict[str, int] = {}
    for bank, path in enumerate(paths):
        with path.open(newline="") as source:
            for row in csv.DictReader(source, delimiter="\t"):
                verdict = row.get("verdict", row.get("actual_verdict"))
                if verdict not in ("wide", "predecessor"):
                    raise ValueError(f"bad verdict in {path}: {verdict!r}")
                operand = row["op"].lower()
                label = int(verdict == "wide")
                previous = labels.setdefault(operand, label)
                if previous != label:
                    raise RuntimeError(f"inconsistent label for {operand}")
                previous_bank = sources.setdefault(operand, bank)
                if previous_bank != bank:
                    raise RuntimeError(f"operand occurs in two banks: {operand}")
    return labels, sources


def as_operation(value: Value) -> ExactOperation:
    return ExactOperation(value.sign, value.exponent, value.significand)


def to_y64(value: Value, mode: str) -> Value:
    return quantize_mode(as_operation(value), 64, mode)


def same_product(value: Value, option: str) -> Value:
    y = value if option == "full" else to_y64(value, option)
    return quantize_mode(multiply(value, y), 67, "chop")


def mixed_product(left: Value, right: Value, option: str) -> Value:
    if option == "full":
        pass
    else:
        side, mode = option.split(".")
        if side == "left":
            left = to_y64(left, mode)
        elif side == "right":
            right = to_y64(right, mode)
        else:
            raise ValueError(option)
    return quantize_mode(multiply(left, right), 67, "chop")


def factor(
    magnitude: Value,
    square_option: str,
    fourth_option: str,
    mul1_option: str,
    mul2_option: str,
) -> Value:
    square = same_product(magnitude, square_option)
    fourth = same_product(square, fourth_option)
    mul1 = mixed_product(fourth, Value(*CONSTANTS[5]), mul1_option)
    add1 = quantize(add_same_sign(Value(*CONSTANTS[3]), mul1), 64, True)
    mul2 = mixed_product(fourth, add1, mul2_option)
    return quantize(add_same_sign(Value(*CONSTANTS[1]), mul2), 64, True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--direct-label", action="append", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")
    if len(args.direct_label) < 2:
        raise SystemExit("supply at least two disjoint direct-label banks")

    labels, sources = load_labels(args.direct_label)
    operands = sorted(labels)
    _, stderr = run(args.model, "rn", operands, dump=True)
    rows = parse_dump(stderr, operands)
    prepared = [
        (
            row["op"],
            row_value(row, "mag"),
            row_value(row, "lf"),
            labels[row["op"]],
            sources[row["op"]],
        )
        for row in rows
    ]

    scores = []
    exact = []
    best_diagnostics = None
    candidate_count = 0
    for square_option in SAME_OPTIONS:
        for fourth_option in SAME_OPTIONS:
            for mul1_option in MIXED_OPTIONS:
                for mul2_option in MIXED_OPTIONS:
                    counts = Counter()
                    diagnostics = []
                    for operand, magnitude, baseline, wanted, bank in prepared:
                        candidate = factor(
                            magnitude,
                            square_option,
                            fourth_option,
                            mul1_option,
                            mul2_option,
                        )
                        delta = magnitude_delta(candidate, baseline)
                        predicted = int(delta == -1)
                        wrong = predicted != wanted
                        counts["errors"] += wrong
                        counts["positive_errors"] += wrong and wanted
                        counts["negative_errors"] += wrong and not wanted
                        counts["predicted_positives"] += predicted
                        counts[f"bank{bank}.errors"] += wrong
                        counts[f"delta.{delta}"] += 1
                        diagnostics.append((operand, wanted, predicted, delta, bank))
                    item = (
                        counts["errors"],
                        counts["positive_errors"],
                        counts["negative_errors"],
                        counts["predicted_positives"],
                        *(counts[f"bank{bank}.errors"] for bank in range(len(args.direct_label))),
                        counts["delta.-1"],
                        counts["delta.0"],
                        len(prepared) - counts["delta.-1"] - counts["delta.0"],
                        square_option,
                        fourth_option,
                        mul1_option,
                        mul2_option,
                    )
                    scores.append(item)
                    if item[0] == 0:
                        exact.append(item)
                    if best_diagnostics is None or item < best_diagnostics[0]:
                        best_diagnostics = (item, diagnostics)
                    candidate_count += 1
    scores.sort()
    if best_diagnostics is None:
        raise AssertionError("empty edge-program search")

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write(f"model_sha256\t{digest(args.model)}\n")
        for index, path in enumerate(args.direct_label):
            output.write(f"direct_labels_sha256.{index}\t{digest(path)}\n")
        output.write("hardware_policy\tfrozen_one_shot_labels_no_x87_execution\n")
        output.write("candidate_policy\tfixed_X67_Y64_negative_edge_placements\n")
        output.write(f"operands\t{len(prepared)}\n")
        output.write(f"positive_operands\t{sum(labels.values())}\n")
        output.write(f"candidates\t{candidate_count}\n")
        output.write(f"exact_candidates\t{len(exact)}\n")
        output.write("\n[ranking]\n")
        bank_columns = "\t".join(
            f"bank{bank}_errors" for bank in range(len(args.direct_label))
        )
        output.write(
            "errors\tpositive_errors\tnegative_errors\tpredicted_positives\t"
            f"{bank_columns}\tdelta_minus1\tdelta_zero\tdelta_other\t"
            "square_Y\tfourth_Y\tmul1_Y\tmul2_Y\n"
        )
        for item in scores[:2048]:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[exact programs]\n")
        for item in exact:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[best diagnostics]\n")
        output.write("op\twanted_wide\tpredicted_wide\tfactor_delta\tbank\n")
        for item in best_diagnostics[1]:
            output.write("\t".join(map(str, item)) + "\n")

    print(
        f"wrote {args.report}: operands={len(prepared)} candidates={candidate_count} "
        f"exact={len(exact)} best={scores[0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
