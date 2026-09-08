#!/usr/bin/env python3
"""Audit fixed rounding-mode representations of the negative Horner graph.

The high-q captures select one of two adjacent final factor values.  This
pass asks whether that selection is merely the projection of a different,
fixed arithmetic schedule: each of the four multiplies and two additions is
materialized with one of chop, RN, away, or round-to-odd at its already
recovered width.  All 4^6 schedules are global recurrences; no operand field,
threshold, or hardware label selects a per-row mode.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
from collections import Counter, defaultdict
from pathlib import Path

from h1184_upstream_halfway_audit import (
    CONSTANTS,
    Value,
    add_same_sign,
    multiply,
    row_value,
)
from h1191_grs_history_isomorphism import magnitude_delta, quantize_mode
from h1210_stagea_residual_reframe import parse_dump, run


MODES = ("chop", "rn", "away", "odd")
STAGES = ("square", "fourth", "mul1", "add1", "mul2", "add2")
BASELINE = ("chop", "chop", "chop", "rn", "chop", "rn")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def set_label(labels: dict[str, int], operand: str, value: int) -> None:
    operand = operand.lower()
    previous = labels.setdefault(operand, value)
    if previous != value:
        raise RuntimeError(f"factor-label conflict for {operand}")


def load_causal(path: Path, labels: dict[str, int]) -> None:
    by_operand: dict[str, list[dict[str, str]]] = defaultdict(list)
    with path.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            by_operand[row["op"].lower()].append(row)
    for operand, rows in by_operand.items():
        if any(row["causal_class"] == "wide_factor_required" for row in rows):
            set_label(labels, operand, 1)
        elif any(row["wide_allowed_carries"] == "-" for row in rows):
            set_label(labels, operand, 0)


def load_siblings(path: Path, labels: dict[str, int]) -> None:
    with path.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            if row["verdict"] not in ("wide", "predecessor"):
                raise RuntimeError(f"non-binary sibling label: {row}")
            operand = f"3ffc {row['residual66'].lower()}"
            set_label(labels, operand, int(row["verdict"] == "wide"))


def load_direct(path: Path, labels: dict[str, int]) -> None:
    with path.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            if row["verdict"] not in ("wide", "predecessor"):
                raise RuntimeError(f"non-binary direct label: {row}")
            set_label(
                labels, row["op"], int(row["verdict"] == "wide"))


def recurrence(magnitude: Value, modes: tuple[str, ...]) -> Value:
    square = quantize_mode(multiply(magnitude, magnitude), 67, modes[0])
    fourth = quantize_mode(multiply(square, square), 67, modes[1])
    factor = quantize_mode(
        multiply(fourth, Value(*CONSTANTS[5])), 67, modes[2])
    factor = quantize_mode(
        add_same_sign(Value(*CONSTANTS[3]), factor), 64, modes[3])
    factor = quantize_mode(multiply(fourth, factor), 67, modes[4])
    return quantize_mode(
        add_same_sign(Value(*CONSTANTS[1]), factor), 64, modes[5])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("causal_legs", type=Path)
    parser.add_argument("sibling_labels", type=Path)
    parser.add_argument("direct_labels", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    labels: dict[str, int] = {}
    load_causal(args.causal_legs, labels)
    load_siblings(args.sibling_labels, labels)
    load_direct(args.direct_labels, labels)
    operands = sorted(labels)
    _, stderr = run(args.model, "rn", operands, dump=True)
    rows = parse_dump(stderr, operands)

    records = []
    for row in rows:
        magnitude = row_value(row, "mag")
        baseline = recurrence(magnitude, BASELINE)
        if baseline != row_value(row, "lf"):
            raise RuntimeError(f"baseline factor mismatch for {row['op']}")
        records.append((row["op"], magnitude, baseline, labels[row["op"]]))

    scores = []
    deltas_by_schedule: dict[tuple[str, ...], list[int | None]] = {}
    for modes in itertools.product(MODES, repeat=len(STAGES)):
        errors = positive_errors = negative_errors = 0
        changes = Counter()
        deltas = []
        for _, magnitude, baseline, wanted in records:
            delta = magnitude_delta(recurrence(magnitude, modes), baseline)
            deltas.append(delta)
            predicted = int(delta == -1)
            wrong = predicted != wanted
            errors += wrong
            positive_errors += wrong and wanted == 1
            negative_errors += wrong and wanted == 0
            changes[str(delta)] += 1
        scores.append((
            errors, positive_errors, negative_errors,
            changes.get("-1", 0), changes.get("0", 0),
            len(records) - changes.get("-1", 0) - changes.get("0", 0),
            ".".join(modes),
        ))
        deltas_by_schedule[modes] = deltas
    scores.sort()
    exact = [score for score in scores if score[0] == 0]

    best_modes = tuple(scores[0][-1].split("."))
    best_deltas = deltas_by_schedule[best_modes]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        for name, path in (
            ("model", args.model),
            ("causal_legs", args.causal_legs),
            ("sibling_labels", args.sibling_labels),
            ("direct_labels", args.direct_labels),
        ):
            target.write(f"{name}_sha256\t{digest(path)}\n")
        target.write("hardware_policy\tfrozen_factor_labels_no_x87_execution\n")
        target.write("candidate_policy\tall_global_fixed_mode_schedules_at_recovered_widths\n")
        target.write(f"operands\t{len(records)}\n")
        target.write(f"positive_operands\t{sum(labels.values())}\n")
        target.write(f"fixed_schedules\t{len(scores)}\n")
        target.write(f"exact_schedules\t{len(exact)}\n")
        target.write("stage_order\t" + ",".join(STAGES) + "\n")
        target.write("\n[ranking]\n")
        target.write(
            "errors\tpositive_errors\tnegative_errors\tdelta_minus1\t"
            "delta_zero\tdelta_other\tschedule\n")
        for score in scores[:256]:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[exact schedules]\n")
        for score in exact:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[best diagnostics]\n")
        target.write("op\twanted_wide\tpredicted_delta\n")
        for record, delta in zip(records, best_deltas):
            target.write(f"{record[0]}\t{record[3]}\t{delta}\n")

    print(
        f"wrote {args.report}: operands={len(records)} "
        f"positive={sum(labels.values())} schedules={len(scores)} "
        f"exact={len(exact)} best={scores[0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
