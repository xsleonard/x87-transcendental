#!/usr/bin/env python3
"""Test named FADD/FMUL circuit wires on the causal R1200 split.

h1223 proves that the 15 repaired operands are compatible with the Horner
factor decrement under either terminal carry, while the nine regressions are
incompatible with it under both.  This script therefore treats that split as
an internal-state constraint and tests the already-defined, label-independent
wire grammars from h1123 and h1124.  Stage prefixes are removed so one wire
has to mean the same thing in the negative and positive Horner chains.

Only single named wires (and complements) are ranked here.  This avoids
turning a small causal set into an unconstrained Boolean synthesis problem.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from pathlib import Path

from h1123_horner_fadd_carry_mine import row_features as fadd_features
from h1124_horner_multiplier_tree_mine import row_features as fmul_features
from h1184_upstream_halfway_audit import schedule
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


def select_stage(values: dict[str, object], stage: str,
                 family: str) -> dict[str, int]:
    prefix = stage + "."
    selected = {
        f"{family}.{name[len(prefix):]}": int(value)
        for name, value in values.items() if name.startswith(prefix)
    }
    if not selected:
        raise RuntimeError(f"no {family} features for {stage}")
    return selected


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
        schedule(row)
        _, adds = scalar_schedule(row, True)
        firing = [stage for stage, fields in adds.items() if fields["fires"]]
        if len(firing) != 1:
            raise RuntimeError(f"expected one firing add for {row['op']}: {firing}")
        add_stage = firing[0]
        producer_stage = add_stage.replace("add", "mul")
        values = select_stage(fadd_features(row), add_stage, "fadd")
        values.update(select_stage(
            fmul_features(row), producer_stage, "fmul"))
        if schema is None:
            schema = tuple(sorted(values))
        elif tuple(sorted(values)) != schema:
            raise RuntimeError("normalized wire schema changed")
        records.append((
            row["op"], classifications[row["op"]] == "fix",
            add_stage, values,
        ))
    if schema is None:
        raise SystemExit("empty input")

    scores = []
    signatures = {}
    for name in schema:
        signature = tuple(record[3][name] for record in records)
        signatures.setdefault(signature, []).append(name)
        for invert in (0, 1):
            errors = sum(
                (record[3][name] ^ invert) != record[1]
                for record in records)
            target_errors = sum(
                record[0] in TARGETS
                and (record[3][name] ^ invert) != record[1]
                for record in records)
            fix_errors = sum(
                record[1] and (record[3][name] ^ invert) != record[1]
                for record in records)
            regression_errors = sum(
                not record[1] and (record[3][name] ^ invert) != record[1]
                for record in records)
            scores.append((
                errors, target_errors, regression_errors, fix_errors,
                invert, name,
            ))
    scores.sort()
    exact = [score for score in scores if score[0] == 0]
    target_safe = [score for score in scores if score[1] == 0]

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"model_sha256\t{digest(args.model)}\n")
        target.write(f"changes_sha256\t{digest(args.changes)}\n")
        target.write("hardware_policy\tcached_causal_labels_no_x87_execution\n")
        target.write(f"operands\t{len(records)}\n")
        target.write(f"features\t{len(schema)}\n")
        target.write(f"distinct_signatures\t{len(signatures)}\n")
        target.write(f"exact_single_wires\t{len(exact)}\n")
        target.write("\n[ranking]\n")
        target.write(
            "errors\ttarget_errors\tregression_errors\tfix_errors\t"
            "invert\tfeature\n"
        )
        for score in scores[:1000]:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[exact single wires]\n")
        for score in exact:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[target-safe ranking]\n")
        for score in target_safe[:1000]:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[best-wire diagnostics]\n")
        best_names = []
        for score in scores:
            if score[5] not in best_names:
                best_names.append(score[5])
            if len(best_names) == 20:
                break
        target.write(
            "op\tclassification\tstage\t" + "\t".join(best_names) + "\n")
        for operand, positive, stage, values in records:
            target.write("\t".join(map(str, (
                operand, "fix" if positive else "regression", stage,
                *(values[name] for name in best_names),
            ))) + "\n")
        target.write("\n[counts]\n")
        counts = Counter(
            ("fix" if positive else "regression", stage)
            for _, positive, stage, _ in records)
        for key, count in sorted(counts.items()):
            target.write(f"{key[0]}.{key[1]}\t{count}\n")

    print(
        f"wrote {args.report} operands={len(records)} features={len(schema)} "
        f"signatures={len(signatures)} exact={len(exact)} best={scores[0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
