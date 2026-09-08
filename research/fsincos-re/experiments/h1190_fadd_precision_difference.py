#!/usr/bin/env python3
"""Audit an exact one-edge precision-difference recurrence at Horner FADDs.

The P6 rounding-history patent does not say to widen every subsequent
operation.  It says that a producer's rounding direction/precision difference
can modify the immediately consuming operation when microcode enables it.
For each final cosine Horner addition this script therefore compares:

    RN64(C + chop67(fourth * prior_factor))

with the operation-local history form

    RN64(C + exact(fourth * prior_factor)).

Only the immediately preceding multiply is made exact; no error is propagated
from earlier operations.  This is a fixed arithmetic recurrence, not a fitted
selector.  The audit uses cached internal rows and cached physical labels only.
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
    quantize,
    schedule,
)


REMAINING = {
    "3ffc ba100000056e0a67",
    "3ffc cca0000009242f0c",
    "3ffc d920000000749eaa",
    "3ffc f4100000059862dd",
    "3ffc fa50000007503a2f",
    "3ffc ffffc00024077827",
    "3ffc ffffc0006e4548d9",
    "3ffc fffff00047c167a3",
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def add_constant_to_exact_product(
    constant: Value, product: ExactOperation
) -> ExactOperation:
    if constant.sign != product.sign:
        raise AssertionError("expected same-sign final Horner operation")
    exponent = min(constant.exponent, product.exponent)
    magnitude = (
        (constant.significand << (constant.exponent - exponent))
        + (product.magnitude << (product.exponent - exponent))
    )
    return ExactOperation(constant.sign, exponent, magnitude)


def value_delta(actual: Value, baseline: Value) -> int | None:
    if actual.sign != baseline.sign:
        return None
    exponent = min(actual.exponent, baseline.exponent)
    difference = (
        (actual.significand << (actual.exponent - exponent))
        - (baseline.significand << (baseline.exponent - exponent))
    )
    unit = 1 << (baseline.exponent - exponent)
    if difference % unit:
        return None
    return difference // unit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("physical_rows", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    labels: dict[tuple[str, str], dict[str, str]] = {}
    with args.physical_rows.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            if row["physical_status"] == "constraining":
                labels[row["mode"], row["op"]] = row

    counts = Counter()
    diagnostics = []
    seen_operands = set()
    with args.features.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            key = (row["mode"], row["op"])
            physical = labels.get(key)
            if physical is None:
                continue
            operations = schedule(row)

            negative_staged = quantize(operations["negative.add2"], 64, True)
            negative_history = quantize(
                add_constant_to_exact_product(
                    Value(*CONSTANTS[1]), operations["negative.mul2"]
                ),
                64,
                True,
            )
            positive_staged = quantize(operations["positive.add2"], 64, True)
            positive_history = quantize(
                add_constant_to_exact_product(
                    Value(*CONSTANTS[2]), operations["positive.mul2"]
                ),
                64,
                True,
            )
            negative_delta = value_delta(negative_history, negative_staged)
            positive_delta = value_delta(positive_history, positive_staged)
            target = physical["label"] == "POS"
            remaining = row["op"] in REMAINING
            changed = negative_delta != 0 or positive_delta != 0

            counts["rows"] += 1
            counts[f"target.{int(target)}"] += 1
            counts[f"remaining.{int(remaining)}"] += 1
            counts[f"changed.{int(changed)}"] += 1
            counts[f"target.{int(target)}.changed.{int(changed)}"] += 1
            counts[f"remaining.{int(remaining)}.changed.{int(changed)}"] += 1
            counts[f"negative_delta.{negative_delta}"] += 1
            counts[f"positive_delta.{positive_delta}"] += 1
            seen_operands.add(row["op"])
            if target or changed:
                diagnostics.append(
                    (
                        row["mode"], row["op"], int(target), int(remaining),
                        negative_delta, positive_delta, physical["theta"],
                        physical["branch"],
                    )
                )

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target_file:
        target_file.write(f"features_sha256\t{digest(args.features)}\n")
        target_file.write(
            f"physical_rows_sha256\t{digest(args.physical_rows)}\n"
        )
        target_file.write(f"unique_operands\t{len(seen_operands)}\n")
        target_file.write("\n[counts]\n")
        for name, value in sorted(counts.items()):
            target_file.write(f"{name}\t{value}\n")
        target_file.write("\n[target-or-change diagnostics]\n")
        target_file.write(
            "mode\top\ttarget\tremaining\tnegative_delta\t"
            "positive_delta\ttheta\tbranch\n"
        )
        for entry in sorted(set(diagnostics)):
            target_file.write("\t".join(map(str, entry)) + "\n")

    print(
        f"rows={counts['rows']} targets={counts['target.1']} "
        f"changes={counts['changed.1']} "
        f"target_changes={counts['target.1.changed.1']} "
        f"remaining_changes={counts['remaining.1.changed.1']} "
        f"report={args.report}",
        flush=True,
    )


if __name__ == "__main__":
    main()
