#!/usr/bin/env python3
"""Test the patented P5 multiplier CPA state on the causal FADD split.

h1124 exposes the Horner multiplier's Booth/CSA tree and ripple carry, but
not the documented 129-bit product adder's four-bit carry-select layer.  This
audit applies h1172's fixed P5-aligned 4/8/16-bit group grammar directly to
the second Horner multiply (67-bit fourth power by 64-bit first-add factor),
then tests single wires and one precision-field-bit/two-input gates.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from h1172_p5_cpa_predictor_mine import add_cpa_features, product_state
from h1184_upstream_halfway_audit import quantize, schedule
from h1210_stagea_residual_reframe import parse_dump, run
from h1222_r1200_enable_state import scalar_schedule
from h1224_r1200_named_wire_audit import TARGETS, read_classifications
from h1229_precision_field_wire_gate import GATE_NAMES, gate_value


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


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
        operations = schedule(row)
        _, adds = scalar_schedule(row, True)
        firing = [stage for stage, fields in adds.items() if fields["fires"]]
        if len(firing) != 1:
            raise RuntimeError(f"expected one firing add for {row['op']}: {firing}")
        add_stage = firing[0]
        chain = add_stage.split(".", 1)[0]
        fourth = quantize(operations["fourth"], 67, False)
        first_add = quantize(operations[f"{chain}.add1"], 64, True)
        sum_vector, carry_vector, cut = product_state(
            fourth.significand, first_add.significand)
        values = {}
        add_cpa_features(values, "P", sum_vector, carry_vector, cut)
        values = {name[2:]: int(value) for name, value in values.items()}
        if schema is None:
            schema = tuple(sorted(values))
        elif tuple(sorted(values)) != schema:
            raise RuntimeError("CPA feature schema changed")
        records.append({
            "op": row["op"],
            "wanted": int(classifications[row["op"]] == "fix"),
            "stage": add_stage,
            "q": int(adds[add_stage]["half_delta"]),
            "values": values,
        })
    if schema is None:
        raise SystemExit("empty input")

    single_scores = []
    for name in schema:
        for invert in (0, 1):
            errors = target_errors = fix_errors = regression_errors = 0
            for record in records:
                prediction = record["values"][name] ^ invert
                wrong = prediction != record["wanted"]
                errors += wrong
                target_errors += wrong and record["op"] in TARGETS
                fix_errors += wrong and record["wanted"]
                regression_errors += prediction and not record["wanted"]
            single_scores.append((
                errors, target_errors, regression_errors, fix_errors,
                invert, name,
            ))
    single_scores.sort()
    exact_single = [score for score in single_scores if score[0] == 0]

    gate_scores = []
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
                gate_scores.append((
                    errors, target_errors, regression_errors, fix_errors,
                    qbit_index, GATE_NAMES[mask], mask, name,
                ))
    gate_scores.sort()
    exact_gates = [score for score in gate_scores if score[0] == 0]

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"model_sha256\t{digest(args.model)}\n")
        target.write(f"changes_sha256\t{digest(args.changes)}\n")
        target.write("hardware_policy\tcached_causal_labels_no_x87_execution\n")
        target.write(f"operands\t{len(records)}\n")
        target.write(f"cpa_wires\t{len(schema)}\n")
        target.write(f"exact_single_wires\t{len(exact_single)}\n")
        target.write(f"exact_qbit_wire_gates\t{len(exact_gates)}\n")
        target.write("\n[single-wire ranking]\n")
        target.write(
            "errors\ttarget_errors\tregression_errors\tfix_errors\t"
            "invert\twire\n")
        for score in single_scores[:2000]:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[exact single wires]\n")
        for score in exact_single:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[q-bit plus CPA-wire ranking]\n")
        target.write(
            "errors\ttarget_errors\tregression_errors\tfix_errors\t"
            "qbit\tgate\tmask\twire\n")
        for score in gate_scores[:3000]:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[exact q-bit plus CPA-wire gates]\n")
        for score in exact_gates[:5000]:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[best diagnostics]\n")
        best = gate_scores[0]
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
        f"exact_single={len(exact_single)} exact_gate={len(exact_gates)} "
        f"best={gate_scores[0]}", flush=True)


if __name__ == "__main__":
    main()
