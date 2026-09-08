#!/usr/bin/env python3
"""Test the literal P5 FADD/FAMUBUS primitive at the R59 terminal.

The six post-R1237 misses are isolated reversals of the scalar R60 ordering.
Before inventing a richer selector, replay the bounded patent-level FADD
representations on the actual terminal products.  Variants differ only in
the documented sticky interpretation, normalization, output materialization,
and whether the known low-digit payload is folded into the negative operand
at a standard 67-bit materialization.

Hardware labels are used only to score the already-frozen 228 endpoint
constraints.  No instruction is executed and no operand predicate is fit.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path

import h110_fsin_standalone as h110
import h200_p5_fadd_bitvector as h200
import h206_p5_fadd_complete as h206


INPUT_ACTIONS = ("direct", "payload-chop67", "payload-rn67",
                 "payload-away67", "payload-odd67")
OUTPUT_ACTIONS = ("retain", "rn64", "chop64", "away64", "odd64", "odd67")


@dataclass(frozen=True)
class Candidate:
    input_action: str
    fadd_mode: str
    normalize: bool
    output_action: str

    def name(self) -> str:
        return (f"{self.input_action}/{self.fadd_mode}/"
                f"{'norm' if self.normalize else 'raw'}/"
                f"{self.output_action}")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def row_value(row: dict[str, str], name: str):
    return (
        int(row[f"tc_{name}_sign"]),
        int(row[f"tc_{name}_sig"], 16),
        int(row[f"tc_{name}_exp"]),
    )


def input_buses(row: dict[str, str], action: str):
    left = row_value(row, "left")
    right = row_value(row, "right")
    if action != "direct":
        rounding = action.split("-", 1)[1].removesuffix("67")
        exact_left = (
            left[0],
            (left[1] << 8) + int(row["payload"]),
            left[2] - 8,
        )
        left = h110.quantize(exact_left, h110.Quant(67, rounding))
    return h200.normalized_bus(left), h200.normalized_bus(right)


def desired_delta(row: dict[str, str]) -> int:
    cut = int(row["k"])
    mask = (1 << cut) - 1
    borrow = int((int(row["S"], 16) & mask)
                 < (int(row["B"], 16) & mask))
    return borrow - 1 + int(row["physical_label"])


def project_delta(row: dict[str, str], value) -> int:
    materialized = h110.quantize(value, h110.Quant(67, "chop"))
    sign, significand, exponent = materialized
    if sign != 1:
        return 999
    retained_exponent = int(row["rscale"]) + int(row["k"])
    baseline = int(row["umag"], 16) >> int(row["k"])
    common = min(exponent, retained_exponent)
    candidate_integer = significand << (exponent - common)
    baseline_integer = baseline << (retained_exponent - common)
    unit = 1 << (retained_exponent - common)
    difference = candidate_integer - baseline_integer
    return difference // unit if difference % unit == 0 else 998


def evaluate(row: dict[str, str], candidate: Candidate) -> int:
    left, right = input_buses(row, candidate.input_action)
    result, _ = h206.fadd(
        left, right, candidate.fadd_mode, normalize=candidate.normalize)
    result = h206.materialize(result, candidate.output_action)
    return project_delta(row, result.value())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rows", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    with args.rows.open(newline="") as source:
        rows = [row for row in csv.DictReader(source, delimiter="\t")
                if row["physical_status"] == "constraining"]
    candidates = [
        Candidate(input_action, fadd_mode, normalize, output_action)
        for input_action in INPUT_ACTIONS
        for fadd_mode in h206.MODES
        for normalize in (False, True)
        for output_action in OUTPUT_ACTIONS
    ]
    ranking = []
    predictions = {}
    for candidate in candidates:
        values = []
        invalid = 0
        for row in rows:
            try:
                values.append(evaluate(row, candidate))
            except ValueError:
                values.append(997)
                invalid += 1
        target_miss = sum(
            value != desired_delta(row) and row["label"] == "POS"
            for row, value in zip(rows, values))
        control_miss = sum(
            value != desired_delta(row) and row["label"] != "POS"
            for row, value in zip(rows, values))
        ranking.append((
            target_miss + control_miss, target_miss, control_miss,
            invalid, candidate.name(), candidate,
        ))
        predictions[candidate] = values
    ranking.sort()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"rows_sha256\t{digest(args.rows)}\n")
        target.write(f"rows\t{len(rows)}\n")
        target.write(f"targets\t{sum(row['label'] == 'POS' for row in rows)}\n")
        target.write(f"candidates\t{len(candidates)}\n")
        target.write("hardware_policy\tcached_labels_only_no_x87_execution\n")
        target.write("\n[ranking]\n")
        target.write(
            "total_miss\ttarget_miss\tcontrol_miss\tinvalid\tcandidate\n")
        for score in ranking:
            target.write("\t".join(map(str, score[:5])) + "\n")

        target.write("\n[best target diagnostics]\n")
        target.write("op\tdesired_delta\tpredicted_delta\tmatch\n")
        best = ranking[0][5]
        for row, value in zip(rows, predictions[best]):
            if row["label"] == "POS":
                expected = desired_delta(row)
                target.write(
                    f"{row['op']}\t{expected}\t{value}\t"
                    f"{int(expected == value)}\n")

    print(
        f"wrote {args.report} rows={len(rows)} candidates={len(candidates)} "
        f"best={ranking[0][:5]}", flush=True)


if __name__ == "__main__":
    main()
