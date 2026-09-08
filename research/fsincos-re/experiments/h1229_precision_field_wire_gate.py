#!/usr/bin/env python3
"""Test one precision-field bit plus one named arithmetic wire.

The causal boundary cases expose a three-bit final-add precision difference
q=1..4.  A single FADD/FMUL wire is insufficient (h1224), but the documented
round-control architecture may combine a bit of that precision field with a
datapath condition.  This audit enumerates every two-input Boolean gate
between one fixed q bit and one already-defined named wire.  It also reports
the particularly simple ``q <= 2 OR wire`` family.

This is hypothesis generation, not promotion: any survivor must be frozen
and validated on independent cached controls before it can become a rule.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path

from h1123_horner_fadd_carry_mine import row_features as fadd_features
from h1124_horner_multiplier_tree_mine import row_features as fmul_features
from h1210_stagea_residual_reframe import parse_dump, run
from h1222_r1200_enable_state import scalar_schedule
from h1224_r1200_named_wire_audit import (
    TARGETS, read_classifications, select_stage,
)


GATE_NAMES = (
    "false", "nor", "wire_and_not_q", "not_q", "q_and_not_wire",
    "not_wire", "xor", "nand", "and", "xnor", "wire", "q_implies_wire",
    "q", "wire_implies_q", "or", "true",
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def gate_value(mask: int, qbit: int, wire: int) -> int:
    return (mask >> (2 * qbit + wire)) & 1


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
    records = []
    schema = None
    for row in rows:
        _, adds = scalar_schedule(row, True)
        firing = [stage for stage, fields in adds.items() if fields["fires"]]
        if len(firing) != 1:
            raise RuntimeError(f"expected one firing add for {row['op']}: {firing}")
        add_stage = firing[0]
        producer_stage = add_stage.replace("add", "mul")
        values = select_stage(fadd_features(row), add_stage, "fadd")
        values.update(select_stage(fmul_features(row), producer_stage, "fmul"))
        if schema is None:
            schema = tuple(sorted(values))
        elif tuple(sorted(values)) != schema:
            raise RuntimeError("normalized wire schema changed")
        records.append({
            "op": row["op"],
            "wanted": int(classifications[row["op"]] == "fix"),
            "stage": add_stage,
            "q": int(adds[add_stage]["half_delta"]),
            "values": values,
        })
    if schema is None:
        raise SystemExit("empty input")

    scores = []
    for qbit_index in range(3):
        for name in schema:
            for mask in range(16):
                errors = target_errors = fix_errors = regression_errors = 0
                for record in records:
                    prediction = gate_value(
                        mask, (record["q"] >> qbit_index) & 1,
                        record["values"][name])
                    wrong = prediction != record["wanted"]
                    errors += wrong
                    target_errors += wrong and record["op"] in TARGETS
                    fix_errors += wrong and record["wanted"]
                    regression_errors += prediction and not record["wanted"]
                scores.append((
                    errors, target_errors, regression_errors, fix_errors,
                    qbit_index, GATE_NAMES[mask], mask, name,
                ))
    scores.sort()
    exact = [score for score in scores if score[0] == 0]

    threshold_scores = []
    for name in schema:
        for invert in (0, 1):
            errors = target_errors = fix_errors = regression_errors = 0
            for record in records:
                prediction = int(
                    record["q"] <= 2
                    or (record["values"][name] ^ invert))
                wrong = prediction != record["wanted"]
                errors += wrong
                target_errors += wrong and record["op"] in TARGETS
                fix_errors += wrong and record["wanted"]
                regression_errors += prediction and not record["wanted"]
            threshold_scores.append((
                errors, target_errors, regression_errors, fix_errors,
                invert, name,
            ))
    threshold_scores.sort()
    exact_threshold = [score for score in threshold_scores if score[0] == 0]

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"model_sha256\t{digest(args.model)}\n")
        target.write(f"changes_sha256\t{digest(args.changes)}\n")
        target.write("hardware_policy\tcached_causal_labels_no_x87_execution\n")
        target.write(f"operands\t{len(records)}\n")
        target.write(f"named_wires\t{len(schema)}\n")
        target.write(f"exact_qbit_wire_gates\t{len(exact)}\n")
        target.write(f"exact_qle2_or_wire\t{len(exact_threshold)}\n")
        target.write("\n[q-bit plus named-wire ranking]\n")
        target.write(
            "errors\ttarget_errors\tregression_errors\tfix_errors\t"
            "qbit\tgate\tmask\twire\n")
        for score in scores[:2000]:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[exact q-bit plus named-wire gates]\n")
        for score in exact[:5000]:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[q<=2 OR named-wire ranking]\n")
        target.write(
            "errors\ttarget_errors\tregression_errors\tfix_errors\t"
            "invert\twire\n")
        for score in threshold_scores[:2000]:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[exact q<=2 OR named wire]\n")
        for score in exact_threshold:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[best diagnostics]\n")
        best = scores[0]
        target.write(
            "op\tclassification\tstage\tq\tqbit_value\twire_value\t"
            "prediction\n")
        for record in records:
            qbit = (record["q"] >> best[4]) & 1
            wire = record["values"][best[7]]
            prediction = gate_value(best[6], qbit, wire)
            target.write("\t".join(map(str, (
                record["op"], "fix" if record["wanted"] else "regression",
                record["stage"], record["q"], qbit, wire, prediction,
            ))) + "\n")

    print(
        f"wrote {args.report} operands={len(records)} wires={len(schema)} "
        f"exact={len(exact)} exact_threshold={len(exact_threshold)} "
        f"best={scores[0]}", flush=True)


if __name__ == "__main__":
    main()
