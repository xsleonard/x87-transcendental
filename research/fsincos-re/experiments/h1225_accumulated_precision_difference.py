#!/usr/bin/env python3
"""Test accumulated precision difference at the final Horner FADD.

The last-operation FMUL tail and every tested FADD/FMUL wire fail to explain
the causal 15-vs-9 R1200 split.  A richer interpretation of Intel's attached
"precision difference" is the error propagated through the dependency graph,
not merely the remainder discarded by the immediately preceding operation.

For each changed operand this experiment compares the ordinary final Horner
add (constant plus the materialized 67-bit product) with the exact recursive
polynomial graph in which no earlier intermediate is materialized.  It asks
whether the recursively exact value crosses the same 64-bit midpoint.  This
is a fixed arithmetic recurrence; hardware labels only score it.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

from h1184_upstream_halfway_audit import quantize, row_value, schedule
from h1191_grs_history_isomorphism import magnitude_delta
from h1192_precision_difference_recurrence import (
    Dyad,
    difference,
    dyad_operation,
    dyad_quantize,
    dyad_scaled_numerator,
    dyad_value,
    recurrence,
)
from h1210_stagea_residual_reframe import parse_dump, run
from h1222_r1200_enable_state import cut_fields, scalar_schedule


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


def dyad_compare(left: Dyad, right: Dyad) -> int:
    delta = difference(left, right)
    return (delta.numerator > 0) - (delta.numerator < 0)


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
    scores: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        operand = row["op"]
        positive = classifications[operand] == "fix"
        operations = schedule(row)
        graph = recurrence(row)
        _, history_adds = scalar_schedule(row, True)
        firing = [stage for stage, fields in history_adds.items()
                  if fields["fires"]]
        if len(firing) != 1:
            raise RuntimeError(f"expected one firing add for {operand}: {firing}")
        add_stage = firing[0]
        chain = add_stage.split(".", 1)[0]
        producer_stage = f"{chain}.mul2"
        baseline_factor = row_value(
            row, "lf" if chain == "negative" else "rf")

        local_add = dyad_operation(operations[add_stage])
        recursive_add = graph[f"recursive.{add_stage}"]
        # The producer stored value is the input actually consumed by the
        # ordinary final add.
        local_source = dyad_value(
            quantize(operations[producer_stage], 67, False))
        recursive_source = graph[f"recursive.{producer_stage}"]
        recursive_factor = dyad_quantize(recursive_add, 64, True)
        recursive_delta = magnitude_delta(recursive_factor, baseline_factor)

        fine = min(
            local_add.exponent, recursive_add.exponent,
            local_source.exponent, recursive_source.exponent,
        )
        add_error = dyad_scaled_numerator(
            difference(recursive_add, local_add), fine)
        source_error = dyad_scaled_numerator(
            difference(recursive_source, local_source), fine)
        add_error_sign = (add_error > 0) - (add_error < 0)
        source_error_sign = (source_error > 0) - (source_error < 0)

        local_cut = cut_fields(operations[add_stage], 64)
        recursive_lower = dyad_quantize(recursive_add, 64, False)
        recursive_rn = dyad_quantize(recursive_add, 64, True)
        recursive_increment = int(
            recursive_rn.significand != recursive_lower.significand
            or recursive_rn.exponent != recursive_lower.exponent)
        local_increment = int(
            baseline_factor.significand
            != (operations[add_stage].magnitude >> local_cut["shift"])
        )
        crossed_to_lower = int(recursive_delta == -1)
        exact_recursive_match = int(crossed_to_lower == positive)

        predicates = {
            "recursive_delta_is_minus1": crossed_to_lower,
            "recursive_does_not_increment": 1 - recursive_increment,
            "recursive_increment_differs": recursive_increment ^ local_increment,
            "recursive_add_error_negative": int(add_error < 0),
            "recursive_source_error_negative": int(source_error < 0),
            "recursive_add_below_local": int(
                dyad_compare(recursive_add, local_add) < 0),
            "recursive_source_below_local": int(
                dyad_compare(recursive_source, local_source) < 0),
        }
        for name, prediction in predicates.items():
            scores[name]["errors"] += prediction != positive
            scores[name]["fix_errors"] += positive and not prediction
            scores[name]["regression_errors"] += not positive and prediction
            scores[name]["target_errors"] += (
                operand in TARGETS and prediction != positive)

        diagnostics.append((
            operand, "fix" if positive else "regression", add_stage,
            local_cut["half_delta"], recursive_delta,
            local_increment, recursive_increment, fine,
            add_error, source_error, add_error_sign, source_error_sign,
            exact_recursive_match,
        ))

    ranking = sorted(
        (values["errors"], values["target_errors"],
         values["regression_errors"], values["fix_errors"], name)
        for name, values in scores.items())

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"model_sha256\t{digest(args.model)}\n")
        target.write(f"changes_sha256\t{digest(args.changes)}\n")
        target.write("hardware_policy\tcached_causal_labels_no_x87_execution\n")
        target.write(f"operands\t{len(diagnostics)}\n")
        target.write("\n[fixed recurrence ranking]\n")
        target.write(
            "errors\ttarget_errors\tregression_errors\tfix_errors\tpredicate\n")
        for score in ranking:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[diagnostics]\n")
        target.write(
            "op\tclassification\tstage\tlocal_half_delta\t"
            "recursive_factor_delta\tlocal_increment\trecursive_increment\t"
            "error_scale\trecursive_minus_local_add\t"
            "recursive_minus_local_source\tadd_error_sign\t"
            "source_error_sign\trecursive_rule_matches\n"
        )
        for diagnostic in diagnostics:
            target.write("\t".join(map(str, diagnostic)) + "\n")

    print(
        f"wrote {args.report} operands={len(diagnostics)} best={ranking[0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
