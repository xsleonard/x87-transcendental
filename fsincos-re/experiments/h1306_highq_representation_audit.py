#!/usr/bin/env python3
"""Test fixed producer/FADD representations on the causally labelled q=5/6 set.

h1304 identifies operands whose architectural truth requires the perturbed
negative.add2 factor, rejects it at either terminal endpoint, or remains
ambiguous between factor and terminal carry.  This pass tests the pre-existing
h1191 closed arithmetic representations against only the forced factor labels.
It does not synthesize a predicate or inspect operand identities.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

from h1184_upstream_halfway_audit import CONSTANTS, Value, schedule
from h1191_grs_history_isomorphism import (
    candidates,
    history_direction,
    magnitude_delta,
    quantize_mode,
)
from h1210_stagea_residual_reframe import parse_dump, run
from h1222_r1200_enable_state import cut_fields


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def factor_labels(path: Path) -> dict[str, int | None]:
    by_operand: dict[str, list[dict[str, str]]] = defaultdict(list)
    with path.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            by_operand[row["op"]].append(row)
    result = {}
    for operand, rows in by_operand.items():
        if any(row["causal_class"] == "wide_factor_required" for row in rows):
            result[operand] = -1
        elif any(row["wide_allowed_carries"] == "-" for row in rows):
            result[operand] = 0
        else:
            result[operand] = None
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("causal_legs", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    labels = factor_labels(args.causal_legs)
    operands = sorted(labels)
    _, stderr = run(args.model, "rn", operands, dump=True)
    rows = parse_dump(stderr, operands)
    records = []
    schema = None
    for row in rows:
        operations = schedule(row)
        product = operations["negative.mul2"]
        source = quantize_mode(product, 67, "chop")
        values = candidates(Value(*CONSTANTS[1]), product)
        baseline = values["baseline"]
        deltas = {
            name: magnitude_delta(value, baseline)
            for name, value in values.items()
        }
        if schema is None:
            schema = tuple(sorted(deltas))
        elif tuple(sorted(deltas)) != schema:
            raise RuntimeError("candidate schema changed")
        add_fields = cut_fields(operations["negative.add2"], 64)
        product_fields = cut_fields(product, 67)
        records.append({
            "op": row["op"],
            "wanted_delta": labels[row["op"]],
            "q": int(add_fields["half_delta"]),
            "product_shift": int(product_fields["shift"]),
            "product_remainder": int(product_fields["remainder"]),
            "product_denominator": int(product_fields["denominator"]),
            "source_low3": source.significand & 7,
            "producer_history": history_direction(product, source),
            "deltas": deltas,
        })
    if schema is None:
        raise SystemExit("empty causal set")

    forced = [row for row in records if row["wanted_delta"] is not None]
    scores = []
    for name in schema:
        errors = positive_errors = negative_errors = 0
        changes = Counter()
        for row in forced:
            delta = row["deltas"][name]
            wanted = row["wanted_delta"]
            wrong = delta != wanted
            errors += wrong
            positive_errors += wrong and wanted == -1
            negative_errors += wrong and wanted == 0
            changes[str(delta)] += 1
        scores.append((
            errors, positive_errors, negative_errors,
            changes.get("-1", 0), changes.get("0", 0), name,
        ))
    scores.sort()
    exact = [score for score in scores if score[0] == 0]

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"model_sha256\t{digest(args.model)}\n")
        target.write(
            f"causal_legs_sha256\t{digest(args.causal_legs)}\n")
        target.write("hardware_policy\tfrozen_causal_labels_no_x87_execution\n")
        target.write(f"operands\t{len(records)}\n")
        target.write(f"forced_factor_labels\t{len(forced)}\n")
        target.write(
            f"ambiguous_factor_terminal_labels\t{len(records) - len(forced)}\n")
        target.write(f"fixed_representations\t{len(schema)}\n")
        target.write(f"exact_representations\t{len(exact)}\n")
        target.write("\n[representation ranking]\n")
        target.write(
            "errors\tpositive_errors\tnegative_errors\t"
            "delta_minus1\tdelta_zero\trepresentation\n")
        for score in scores:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[exact representations]\n")
        for score in exact:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[diagnostics]\n")
        target.write(
            "op\twanted_delta\tq\tproduct_shift\tproduct_remainder\t"
            "product_denominator\tsource_low3\tproducer_history\t"
            "best_delta\n")
        best_name = scores[0][-1]
        for row in records:
            target.write("\t".join(map(str, (
                row["op"],
                "ambiguous" if row["wanted_delta"] is None
                else row["wanted_delta"],
                row["q"], row["product_shift"],
                f"{row['product_remainder']:x}",
                f"{row['product_denominator']:x}",
                row["source_low3"], row["producer_history"],
                row["deltas"][best_name],
            ))) + "\n")

    print(
        f"wrote {args.report}: forced={len(forced)} "
        f"representations={len(schema)} exact={len(exact)} "
        f"best={scores[0]}", flush=True,
    )


if __name__ == "__main__":
    main()
