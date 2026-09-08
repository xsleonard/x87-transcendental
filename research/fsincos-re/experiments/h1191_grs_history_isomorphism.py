#!/usr/bin/env python3
"""Test finite GRS/history representations of the final cosine Horner adds.

R1186 observes a current 64-bit FADD boundary at exact half or half plus at
most four units of the producer's low-three-bit field.  This audit asks
whether that predicate is exactly the projection of a conventional operation
representation: materialize the preceding FMUL at a 64-bit value boundary,
carry its signed rounding direction separately, and use Intel US5612909's
rounding-history rule on a subsequent exact-half FADD.

The candidate transformations are fixed arithmetic recurrences.  Hardware
labels are used only to report target/control incidence; no candidate is
selected or parameterized from them, and no hardware instruction is run.
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


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def compare_values(left: Value, right: Value) -> int:
    if left.sign != right.sign:
        raise AssertionError("candidate changed factor sign")
    exponent = min(left.exponent, right.exponent)
    left_magnitude = left.significand << (left.exponent - exponent)
    right_magnitude = right.significand << (right.exponent - exponent)
    signed = -1 if left.sign else 1
    difference = signed * (left_magnitude - right_magnitude)
    return (difference > 0) - (difference < 0)


def magnitude_delta(left: Value, right: Value) -> int | None:
    if left.sign != right.sign:
        return None
    exponent = min(left.exponent, right.exponent)
    difference = (
        (left.significand << (left.exponent - exponent))
        - (right.significand << (right.exponent - exponent))
    )
    unit = 1 << (right.exponent - exponent)
    return difference // unit if difference % unit == 0 else None


def quantize_mode(operation: ExactOperation, bits: int, mode: str) -> Value:
    """Quantize a magnitude with an explicit fixed internal mode."""
    shift = max(0, operation.magnitude.bit_length() - bits)
    retained = operation.magnitude >> shift
    remainder = operation.magnitude & ((1 << shift) - 1) if shift else 0
    if remainder:
        if mode == "away":
            retained += 1
        elif mode == "odd":
            retained |= 1
        elif mode == "rn":
            half = 1 << (shift - 1)
            if remainder > half or (remainder == half and retained & 1):
                retained += 1
        elif mode != "chop":
            raise ValueError(mode)
    if retained == 1 << bits:
        retained >>= 1
        shift += 1
    return Value(operation.sign, operation.exponent + shift, retained)


def operation_from_values(left: Value, right: Value) -> ExactOperation:
    return add_same_sign(left, right)


def history_direction(exact: ExactOperation, stored: Value) -> int:
    """Return -1/down, 0/exact, or +1/up in signed numeric order."""
    exact_value = Value(exact.sign, exact.exponent, exact.magnitude)
    return compare_values(stored, exact_value)


def patent_rn64(operation: ExactOperation, histories: tuple[int, int]) -> Value:
    """Apply the concrete US5612909 RN exact-half table.

    If all non-exact source histories have one direction, an exact current
    tie is rounded in the opposite signed direction.  Opposed histories and
    two exact sources use ordinary ties-to-even.
    """
    baseline = quantize(operation, 64, True)
    shift = max(0, operation.magnitude.bit_length() - 64)
    if not shift:
        return baseline
    remainder = operation.magnitude & ((1 << shift) - 1)
    if remainder != 1 << (shift - 1):
        return baseline
    active = {history for history in histories if history}
    if len(active) != 1:
        return baseline
    desired_numeric_direction = -next(iter(active))
    lower = quantize(operation, 64, False)
    upper = Value(lower.sign, lower.exponent, lower.significand + 1)
    if upper.significand == 1 << 64:
        upper = Value(upper.sign, upper.exponent + 1, upper.significand >> 1)
    if operation.sign:
        numeric_lower, numeric_upper = upper, lower
    else:
        numeric_lower, numeric_upper = lower, upper
    return numeric_upper if desired_numeric_direction > 0 else numeric_lower


def low3_centered(source: Value) -> tuple[Value, int]:
    """Decode a 67-bit carrier as a nearest 64-bit word plus direction."""
    operation = ExactOperation(source.sign, source.exponent, source.significand)
    core = quantize_mode(operation, 64, "rn")
    return core, history_direction(operation, core)


def candidates(constant: Value, product: ExactOperation) -> dict[str, Value]:
    source67 = quantize_mode(product, 67, "chop")
    baseline = quantize(operation_from_values(constant, source67), 64, True)
    result = {"baseline": baseline}

    for mode in ("chop", "rn", "away", "odd"):
        direct64 = quantize_mode(product, 64, mode)
        result[f"direct64.{mode}"] = quantize(
            operation_from_values(constant, direct64), 64, True)
        source64 = quantize_mode(
            ExactOperation(source67.sign, source67.exponent,
                           source67.significand),
            64,
            mode,
        )
        result[f"carrier64.{mode}"] = quantize(
            operation_from_values(constant, source64), 64, True)

    core, core_history = low3_centered(source67)
    core_operation = operation_from_values(constant, core)
    result["grs.rn64"] = quantize(core_operation, 64, True)
    result["grs.patent"] = patent_rn64(
        core_operation, (0, core_history))

    product_history = history_direction(product, source67)
    result["numeric67.patent"] = patent_rn64(
        operation_from_values(constant, source67), (0, product_history))

    constant_exact = ExactOperation(
        constant.sign, constant.exponent, constant.significand)
    for constant_mode in ("chop", "rn", "away", "odd"):
        constant64 = quantize_mode(constant_exact, 64, constant_mode)
        constant_history = history_direction(constant_exact, constant64)
        for source_mode in ("chop", "rn", "away", "odd"):
            source64 = quantize_mode(product, 64, source_mode)
            source_history = history_direction(product, source64)
            operation = operation_from_values(constant64, source64)
            prefix = f"core64.c_{constant_mode}.s_{source_mode}"
            result[prefix] = quantize(operation, 64, True)
            result[prefix + ".patent"] = patent_rn64(
                operation, (constant_history, source_history))

    return result


def r1186_value(constant: Value, source: Value, include_exact: bool) -> Value:
    operation = operation_from_values(constant, source)
    value = quantize(operation, 64, True)
    shift = max(0, operation.magnitude.bit_length() - 64)
    if not shift:
        return value
    remainder = operation.magnitude & ((1 << shift) - 1)
    half = 1 << (shift - 1)
    fires = ((include_exact and remainder == half)
             or (half < remainder <= half + 4))
    if fires:
        return Value(value.sign, value.exponent, value.significand - 1)
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("physical_rows", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    labels = {}
    with args.physical_rows.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            labels[(row["mode"], row["op"])] = int(row["label"] == "POS")

    counts = Counter()
    diagnostics = []
    with args.features.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            target = labels.get((row["mode"], row["op"]), 0)
            operations = schedule(row)
            for chain, constant_index, stage, include_exact in (
                ("negative", 1, "negative.mul2", True),
                ("positive", 2, "positive.mul2", False),
            ):
                constant = Value(*CONSTANTS[constant_index])
                product = operations[stage]
                source = quantize_mode(product, 67, "chop")
                variants = candidates(constant, product)
                r1186 = r1186_value(constant, source, include_exact)
                baseline = variants["baseline"]
                expected_delta = magnitude_delta(r1186, baseline)
                counts["rows"] += 1
                counts[f"{chain}.target.{target}"] += 1
                counts[f"{chain}.r1186_delta.{expected_delta}"] += 1
                for name, value in variants.items():
                    delta = magnitude_delta(value, baseline)
                    agrees = value == r1186
                    counts[f"{chain}.{name}.delta.{delta}"] += 1
                    counts[f"{chain}.{name}.agrees.{int(agrees)}"] += 1
                    counts[f"{chain}.{name}.target.{target}.changed."
                           f"{int(value != baseline)}"] += 1
                if target or expected_delta:
                    diagnostics.append((
                        row["mode"], row["op"], chain, target,
                        source.significand & 7,
                        history_direction(product, source),
                        expected_delta,
                        *(magnitude_delta(variants[name], baseline) for name in (
                            "direct64.chop", "direct64.rn", "direct64.away",
                            "direct64.odd", "grs.rn64", "grs.patent",
                            "numeric67.patent",
                        )),
                    ))

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target_file:
        target_file.write(f"features_sha256\t{digest(args.features)}\n")
        target_file.write(
            f"physical_rows_sha256\t{digest(args.physical_rows)}\n"
        )
        target_file.write("\n[counts]\n")
        for name, value in sorted(counts.items()):
            target_file.write(f"{name}\t{value}\n")
        target_file.write("\n[target-or-R1186 diagnostics]\n")
        target_file.write(
            "mode\top\tchain\ttarget\tcarrier_low3\tproducer_history\t"
            "r1186_delta\tdirect_chop\tdirect_rn\tdirect_away\t"
            "direct_odd\tgrs_rn\tgrs_patent\tnumeric67_patent\n"
        )
        for entry in sorted(set(diagnostics)):
            target_file.write("\t".join(map(str, entry)) + "\n")

    print(f"wrote {args.report} rows={counts['rows']}")


if __name__ == "__main__":
    main()
