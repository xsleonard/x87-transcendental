#!/usr/bin/env python3
"""Resolve the final-multiply precision history into operand components.

The uniform depth recurrence expands both inputs of the second Horner
multiply together.  An attached hardware tag may instead describe one input
port's prior rounding.  This experiment tests the four fixed one-level
interpretations: neither input expanded, only the fourth-power input, only
the first-Horner-add input, or both.  Each shadow product is fed to the final
RN64 add and scored on the causal 15-vs-9 split.
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
    Dyad, dyad_add, dyad_mul, dyad_operation, dyad_quantize, dyad_value,
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

    names = ("stored", "local_product", "fourth_history", "a1_history", "both_histories")
    scores = Counter()
    diagnostics = []
    for row in rows:
        operand = row["op"]
        wanted = classifications[operand] == "fix"
        operations = schedule(row)
        _, adds = scalar_schedule(row, True)
        firing = [stage for stage, fields in adds.items() if fields["fires"]]
        if len(firing) != 1:
            raise RuntimeError(f"expected one firing add for {operand}: {firing}")
        chain = firing[0].split(".", 1)[0]
        p2 = f"{chain}.mul2"
        a1 = f"{chain}.add1"
        factor_name = "lf" if chain == "negative" else "rf"
        factor_constant = 1 if chain == "negative" else 2

        fourth_stored = dyad_value(row_value(row, "f4"))
        a1_stored = dyad_value(quantize(operations[a1], 64, True))
        source_stored = dyad_value(quantize(operations[p2], 67, False))
        fourth_exact = dyad_operation(operations["fourth"])
        a1_exact = dyad_operation(operations[a1])
        shadows = {
            "stored": source_stored,
            "local_product": dyad_mul(fourth_stored, a1_stored),
            "fourth_history": dyad_mul(fourth_exact, a1_stored),
            "a1_history": dyad_mul(fourth_stored, a1_exact),
            "both_histories": dyad_mul(fourth_exact, a1_exact),
        }
        baseline = row_value(row, factor_name)
        constant = dyad_value(Value(*CONSTANTS[factor_constant]))
        deltas = {}
        for name, shadow in shadows.items():
            candidate = dyad_quantize(dyad_add(constant, shadow), 64, True)
            delta = magnitude_delta(candidate, baseline)
            deltas[name] = delta
            prediction = delta == -1
            scores[name, "errors"] += prediction != wanted
            scores[name, "target_errors"] += (
                operand in TARGETS and prediction != wanted)
            scores[name, "fix_errors"] += wanted and not prediction
            scores[name, "regression_errors"] += not wanted and prediction
        diagnostics.append((
            operand, "fix" if wanted else "regression", firing[0],
            *(deltas[name] for name in names),
        ))

    ranking = sorted(
        (scores[name, "errors"], scores[name, "target_errors"],
         scores[name, "regression_errors"], scores[name, "fix_errors"], name)
        for name in names)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"model_sha256\t{digest(args.model)}\n")
        target.write(f"changes_sha256\t{digest(args.changes)}\n")
        target.write("hardware_policy\tcached_causal_labels_no_x87_execution\n")
        target.write(f"operands\t{len(diagnostics)}\n")
        target.write("\n[component ranking]\n")
        target.write(
            "errors\ttarget_errors\tregression_errors\tfix_errors\tcomponent\n")
        for score in ranking:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[diagnostics]\n")
        target.write(
            "op\tclassification\tstage\t" + "\t".join(names) + "\n")
        for diagnostic in diagnostics:
            target.write("\t".join(map(str, diagnostic)) + "\n")
    print(
        f"wrote {args.report} operands={len(diagnostics)} best={ranking[0]}",
        flush=True)


if __name__ == "__main__":
    main()
