#!/usr/bin/env python3
"""Test bounded dependency-depth meanings of attached precision history.

One-hop history ignores the rounding histories of the final multiply's two
inputs; fully recursive exact evaluation over-propagates them.  Between those
extremes are fixed local recurrences: replace a stored producer by the exact
operation one dependency level back, two levels back, and so on, while older
nodes remain materialized.  This script tests every such depth uniformly on
the causal R1200 boundary set.

The recurrence depth is global, not selected per operand or per label.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from pathlib import Path

from h1184_upstream_halfway_audit import CONSTANTS, Value, quantize, row_value, schedule
from h1191_grs_history_isomorphism import magnitude_delta
from h1192_precision_difference_recurrence import (
    Dyad, dyad_add, dyad_mul, dyad_quantize, dyad_value,
)
from h1210_stagea_residual_reframe import parse_dump, run
from h1222_r1200_enable_state import scalar_schedule


TARGETS = {
    "3ffc d180000005ada2ba",
    "3ffc dfc00000079c9cb7",
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def read_classifications(path: Path) -> dict[str, str]:
    values = {}
    with path.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            operand = row["op"].lower()
            classification = row["classification"]
            previous = values.setdefault(operand, classification)
            if previous != classification:
                raise RuntimeError(f"classification conflict for {operand}")
    return values


def stored_graph(row: dict[str, str], chain: str) -> dict[str, Dyad]:
    operations = schedule(row)
    stored = {
        "mag": dyad_value(row_value(row, "mag")),
        "square": dyad_value(row_value(row, "mul")),
        "fourth": dyad_value(row_value(row, "f4")),
    }
    for stage in (f"{chain}.mul1", f"{chain}.add1", f"{chain}.mul2"):
        bits = 64 if stage.endswith("add1") else 67
        nearest = stage.endswith("add1")
        stored[stage] = dyad_value(quantize(operations[stage], bits, nearest))
    return stored


def exact_at_depth(stage: str, depth: int, chain: str,
                   stored: dict[str, Dyad]) -> Dyad:
    if depth <= 0 or stage == "mag":
        return stored[stage]
    inner = 5 if chain == "negative" else 6
    outer = 3 if chain == "negative" else 4
    constants = {index: dyad_value(Value(*value))
                 for index, value in CONSTANTS.items()}
    if stage == "square":
        value = exact_at_depth("mag", depth - 1, chain, stored)
        return dyad_mul(value, value)
    if stage == "fourth":
        value = exact_at_depth("square", depth - 1, chain, stored)
        return dyad_mul(value, value)
    if stage == f"{chain}.mul1":
        return dyad_mul(
            exact_at_depth("fourth", depth - 1, chain, stored),
            constants[inner])
    if stage == f"{chain}.add1":
        return dyad_add(
            constants[outer],
            exact_at_depth(f"{chain}.mul1", depth - 1, chain, stored))
    if stage == f"{chain}.mul2":
        return dyad_mul(
            exact_at_depth("fourth", depth - 1, chain, stored),
            exact_at_depth(f"{chain}.add1", depth - 1, chain, stored))
    raise ValueError(stage)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("changes", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    classifications = read_classifications(args.changes)
    operands = sorted(classifications)
    _, stderr = run(args.model, "rn", operands, dump=True)
    rows = parse_dump(stderr, operands)

    diagnostics = []
    scores = Counter()
    for row in rows:
        operand = row["op"]
        wanted = classifications[operand] == "fix"
        _, adds = scalar_schedule(row, True)
        firing = [stage for stage, fields in adds.items() if fields["fires"]]
        if len(firing) != 1:
            raise RuntimeError(f"expected one firing add for {operand}: {firing}")
        chain = firing[0].split(".", 1)[0]
        final_constant = 1 if chain == "negative" else 2
        baseline = row_value(row, "lf" if chain == "negative" else "rf")
        stored = stored_graph(row, chain)
        deltas = []
        for depth in range(0, 9):
            shadow_source = exact_at_depth(
                f"{chain}.mul2", depth, chain, stored)
            shadow_add = dyad_add(
                dyad_value(Value(*CONSTANTS[final_constant])), shadow_source)
            candidate = dyad_quantize(shadow_add, 64, True)
            delta = magnitude_delta(candidate, baseline)
            prediction = delta == -1
            deltas.append(delta)
            scores[depth, "errors"] += prediction != wanted
            scores[depth, "target_errors"] += (
                operand in TARGETS and prediction != wanted)
            scores[depth, "fix_errors"] += wanted and not prediction
            scores[depth, "regression_errors"] += not wanted and prediction
        diagnostics.append((
            operand, "fix" if wanted else "regression", firing[0], *deltas))

    ranking = sorted(
        (scores[depth, "errors"], scores[depth, "target_errors"],
         scores[depth, "regression_errors"], scores[depth, "fix_errors"],
         depth)
        for depth in range(0, 9))

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"model_sha256\t{digest(args.model)}\n")
        target.write(f"changes_sha256\t{digest(args.changes)}\n")
        target.write("hardware_policy\tcached_causal_labels_no_x87_execution\n")
        target.write(f"operands\t{len(diagnostics)}\n")
        target.write("\n[depth ranking]\n")
        target.write(
            "errors\ttarget_errors\tregression_errors\tfix_errors\tdepth\n")
        for score in ranking:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[diagnostics]\n")
        target.write(
            "op\tclassification\tstage\t" +
            "\t".join(f"depth{depth}" for depth in range(0, 9)) + "\n")
        for diagnostic in diagnostics:
            target.write("\t".join(map(str, diagnostic)) + "\n")

    print(
        f"wrote {args.report} operands={len(diagnostics)} best={ranking[0]}",
        flush=True)


if __name__ == "__main__":
    main()
