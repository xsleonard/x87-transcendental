#!/usr/bin/env python3
"""Audit closed precision-difference recurrences for the P6 cosine graph.

The hardware corpus is immutable input to this script; no instruction is
captured.  Every candidate below is an arithmetic recurrence over the
fixed model operation graph.  In particular, no target label is used to
choose a threshold, branch, or table entry.

Two meanings of an operand's carried precision difference are tested:

* one-hop: the exact pre-materialization result of the immediately preceding
  operation, which is the finite-history interpretation described by
  US5612909;
* recursive: the exact result obtained by propagating every earlier discarded
  difference through the dependency graph.

The carried value is projected only at the next 64-bit Horner FADD and at the
terminal 67-bit subtraction.  This directly tests whether R1186 and the
remaining R96 endpoint choices are projections of either closed recurrence.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from h1184_upstream_halfway_audit import (
    CONSTANTS,
    ExactOperation,
    Value,
    add_same_sign,
    multiply,
    quantize,
    row_value,
    schedule,
)
from h1191_grs_history_isomorphism import magnitude_delta, r1186_value


@dataclass(frozen=True)
class Dyad:
    """Signed integer times a power of two."""

    numerator: int
    exponent: int


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def dyad_value(value: Value) -> Dyad:
    numerator = -value.significand if value.sign else value.significand
    return Dyad(numerator, value.exponent)


def dyad_operation(operation: ExactOperation) -> Dyad:
    numerator = -operation.magnitude if operation.sign else operation.magnitude
    return Dyad(numerator, operation.exponent)


def dyad_add(left: Dyad, right: Dyad) -> Dyad:
    exponent = min(left.exponent, right.exponent)
    return Dyad(
        (left.numerator << (left.exponent - exponent))
        + (right.numerator << (right.exponent - exponent)),
        exponent,
    )


def dyad_mul(left: Dyad, right: Dyad) -> Dyad:
    return Dyad(left.numerator * right.numerator,
                left.exponent + right.exponent)


def dyad_quantize(value: Dyad, bits: int, nearest: bool) -> Value:
    if value.numerator == 0:
        return Value(0, 0, 0)
    operation = ExactOperation(
        int(value.numerator < 0), value.exponent, abs(value.numerator))
    return quantize(operation, bits, nearest)


def dyad_scaled_numerator(value: Dyad, exponent: int) -> int:
    shift = value.exponent - exponent
    if shift >= 0:
        return value.numerator << shift
    denominator = 1 << -shift
    if value.numerator % denominator:
        raise AssertionError("requested exponent is not an exact dyadic grid")
    return value.numerator // denominator


def difference(left: Dyad, right: Dyad) -> Dyad:
    return dyad_add(left, Dyad(-right.numerator, right.exponent))


def recurrence(row: dict[str, str]) -> dict[str, Dyad]:
    """Return local and recursively propagated exact graph values."""
    operations = schedule(row)
    stored = {
        name: dyad_value(row_value(row, name))
        for name in ("mag", "mul", "f4", "lf", "rf", "left", "right")
    }
    constants = {index: dyad_value(Value(*value))
                 for index, value in CONSTANTS.items()}

    local = {name: dyad_operation(operation)
             for name, operation in operations.items()}

    recursive: dict[str, Dyad] = {}
    recursive["square"] = dyad_mul(stored["mag"], stored["mag"])
    recursive["fourth"] = dyad_mul(
        recursive["square"], recursive["square"])
    recursive["negative.mul1"] = dyad_mul(
        recursive["fourth"], constants[5])
    recursive["negative.add1"] = dyad_add(
        constants[3], recursive["negative.mul1"])
    recursive["negative.mul2"] = dyad_mul(
        recursive["fourth"], recursive["negative.add1"])
    recursive["negative.add2"] = dyad_add(
        constants[1], recursive["negative.mul2"])
    recursive["positive.mul1"] = dyad_mul(
        recursive["fourth"], constants[6])
    recursive["positive.add1"] = dyad_add(
        constants[4], recursive["positive.mul1"])
    recursive["positive.mul2"] = dyad_mul(
        recursive["fourth"], recursive["positive.add1"])
    recursive["positive.add2"] = dyad_add(
        constants[2], recursive["positive.mul2"])
    recursive["left"] = dyad_mul(
        recursive["square"], recursive["negative.add2"])
    recursive["right"] = dyad_mul(
        recursive["fourth"], recursive["positive.add2"])

    # A one-hop input history at an FADD replaces only its immediately
    # preceding materialized FMUL operand by that FMUL's exact result.
    onehop_negative_add2 = dyad_add(
        constants[1], local["negative.mul2"])
    onehop_positive_add2 = dyad_add(
        constants[2], local["positive.mul2"])

    result = {f"local.{name}": value for name, value in local.items()}
    result.update({f"recursive.{name}": value
                   for name, value in recursive.items()})
    result["onehop.negative.add2"] = onehop_negative_add2
    result["onehop.positive.add2"] = onehop_positive_add2
    return result


def terminal_delta(row: dict[str, str], total: Dyad) -> int:
    """Project a closed exact terminal value onto the inferred 67-bit grid."""
    candidate = dyad_quantize(total, 67, False)
    retained_exponent = int(row["rscale"]) + int(row["k"])
    baseline = int(row["umag"], 16) >> int(row["k"])
    if candidate.sign != 1:
        return 99
    common = min(candidate.exponent, retained_exponent)
    candidate_integer = candidate.significand << (candidate.exponent - common)
    baseline_integer = baseline << (retained_exponent - common)
    unit = 1 << (retained_exponent - common)
    delta = candidate_integer - baseline_integer
    return delta // unit if delta % unit == 0 else 99


def terminal_total(row: dict[str, str], left: Dyad, right: Dyad) -> Dyad:
    total = dyad_add(left, right)
    payload = int(row["payload"])
    if payload:
        payload_value = -payload if int(row["tc_left_sign"]) else payload
        total = dyad_add(
            total, Dyad(payload_value, int(row["tc_left_exp"]) - 8))
    return total


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("physical_rows", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    labels = {}
    expected_terminal = {}
    with args.physical_rows.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            key = (row["mode"], row["op"])
            labels[key] = int(row["label"] == "POS")
            theta = int(row["theta"])
            physical = int(row["physical_label"] or 0)
            expected_terminal[key] = -physical if theta >= 0 else physical

    counts = Counter()
    diagnostics = []
    with args.features.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            key = (row["mode"], row["op"])
            target = labels.get(key, 0)
            graph = recurrence(row)
            operations = schedule(row)

            factor_deltas = {}
            for chain, constant_index, include_exact in (
                ("negative", 1, True),
                ("positive", 2, False),
            ):
                baseline = row_value(row, "lf" if chain == "negative" else "rf")
                source = quantize(operations[f"{chain}.mul2"], 67, False)
                r1186 = r1186_value(
                    Value(*CONSTANTS[constant_index]), source, include_exact)
                factor_deltas[f"{chain}.r1186"] = magnitude_delta(r1186, baseline)
                for history in ("onehop", "recursive"):
                    candidate = dyad_quantize(
                        graph[f"{history}.{chain}.add2"], 64, True)
                    factor_deltas[f"{chain}.{history}"] = magnitude_delta(
                        candidate, baseline)

            terminal_deltas = {
                "local": terminal_delta(
                    row,
                    terminal_total(
                        row, graph["local.left"], graph["local.right"])),
                "recursive": terminal_delta(
                    row,
                    terminal_total(
                        row,
                        graph["recursive.left"],
                        graph["recursive.right"])),
            }

            counts["rows"] += 1
            counts[f"target.{target}"] += 1
            for name, delta in sorted(factor_deltas.items()):
                counts[f"factor.{name}.delta.{delta}"] += 1
                counts[f"factor.{name}.target.{target}.changed.{int(delta != 0)}"] += 1
            expected = expected_terminal.get(key, 0)
            for name, delta in terminal_deltas.items():
                match = delta == expected
                counts[f"terminal.{name}.delta.{delta}"] += 1
                counts[f"terminal.{name}.target.{target}.match.{int(match)}"] += 1

            if target or any(delta for delta in factor_deltas.values()):
                neg_current = dyad_operation(operations["negative.add2"])
                neg_onehop = graph["onehop.negative.add2"]
                neg_recursive = graph["recursive.negative.add2"]
                fine = min(
                    neg_current.exponent,
                    neg_onehop.exponent,
                    neg_recursive.exponent,
                )
                onehop_error = dyad_scaled_numerator(
                    difference(neg_onehop, neg_current), fine)
                recursive_error = dyad_scaled_numerator(
                    difference(neg_recursive, neg_current), fine)
                diagnostics.append((
                    row["mode"], row["op"], target,
                    factor_deltas["negative.r1186"],
                    factor_deltas["negative.onehop"],
                    factor_deltas["negative.recursive"],
                    factor_deltas["positive.r1186"],
                    factor_deltas["positive.onehop"],
                    factor_deltas["positive.recursive"],
                    expected,
                    terminal_deltas["local"],
                    terminal_deltas["recursive"],
                    fine,
                    onehop_error,
                    recursive_error,
                ))

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target_file:
        target_file.write(f"features_sha256\t{digest(args.features)}\n")
        target_file.write(
            f"physical_rows_sha256\t{digest(args.physical_rows)}\n")
        target_file.write("\n[counts]\n")
        for name, value in sorted(counts.items()):
            target_file.write(f"{name}\t{value}\n")
        target_file.write("\n[target-or-factor-change diagnostics]\n")
        target_file.write(
            "mode\top\ttarget\tneg_r1186\tneg_onehop\tneg_recursive\t"
            "pos_r1186\tpos_onehop\tpos_recursive\texpected_terminal\t"
            "terminal_local\tterminal_recursive\terror_scale\t"
            "neg_onehop_error\tneg_recursive_error\n")
        for entry in sorted(set(diagnostics)):
            target_file.write("\t".join(map(str, entry)) + "\n")

    print(
        f"wrote {args.report} rows={counts['rows']} "
        f"local_target_miss={counts['terminal.local.target.1.match.0']} "
        f"local_control_miss={counts['terminal.local.target.0.match.0']} "
        f"recursive_target_miss={counts['terminal.recursive.target.1.match.0']} "
        f"recursive_control_miss={counts['terminal.recursive.target.0.match.0']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
