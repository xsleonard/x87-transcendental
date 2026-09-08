#!/usr/bin/env python3
"""Replay Intel's documented attached-rounding-history rule recursively.

US5612909 gives a concrete round-to-nearest rule for an exact-half current
addition: prior up/up (or up/exact) histories select the lower endpoint,
prior down/down (or down/exact) histories select the upper endpoint, and
opposed or exact/exact histories retain ordinary ties-to-even.  This audit
attaches the signed numeric rounding direction to every materialized value
and applies that fixed rule at all four 64-bit Horner FADDs.

The recurrence is specified before labels are loaded.  Hardware truth is
read only from cached files; this script performs no hardware captures and
does not fit a table or tune a threshold from the labels.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


CONSTANTS = {
    1: (1, -68, (7 << 64) | 0xFFFFFFFFFFFFFFFE),
    2: (0, -71, (5 << 64) | 0x5555555555554277),
    3: (1, -76, (5 << 64) | 0xB05B05B05A18A1BA),
    4: (0, -82, (6 << 64) | 0x80680675B559F2CF),
    5: (1, -88, (4 << 64) | 0x9F93AF61F5349300),
    6: (0, -95, (4 << 64) | 0x7A4F2483514C1AF8),
}
ADD_STAGES = ("odd_a1", "odd_a2", "even_a1", "even_a2")
VALUE_STAGES = (
    "square", "fourth", "odd_p1", "odd_a1", "odd_p2", "odd_a2",
    "even_p1", "even_a1", "even_p2", "even_a2", "left", "right",
    "terminal",
)


@dataclass(frozen=True)
class Value:
    sign: int
    exponent: int
    significand: int
    history: int = 0


@dataclass(frozen=True)
class ExactOperation:
    sign: int
    exponent: int
    magnitude: int


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def same_number(left: Value, right: Value) -> bool:
    return (left.sign, left.exponent, left.significand) == (
        right.sign, right.exponent, right.significand)


def compare_value_to_exact(value: Value, exact: ExactOperation) -> int:
    """Compare a materialized value to its exact source in signed order."""
    if value.sign != exact.sign:
        raise AssertionError("rounding unexpectedly changed sign")
    common = min(value.exponent, exact.exponent)
    stored = value.significand << (value.exponent - common)
    source = exact.magnitude << (exact.exponent - common)
    difference = stored - source
    if value.sign:
        difference = -difference
    return (difference > 0) - (difference < 0)


def next_magnitude(value: Value) -> Value:
    significand = value.significand + 1
    exponent = value.exponent
    if significand == 1 << 64:
        significand >>= 1
        exponent += 1
    return Value(value.sign, exponent, significand)


def materialize(operation: ExactOperation, bits: int, nearest: bool,
                source_histories: tuple[int, int] | None = None
                ) -> tuple[Value, dict[str, object]]:
    shift = max(0, operation.magnitude.bit_length() - bits)
    retained = operation.magnitude >> shift
    remainder = operation.magnitude & ((1 << shift) - 1) if shift else 0
    half = 1 << (shift - 1) if shift else 0
    exact_half = bool(shift and remainder == half)
    increment = bool(
        nearest and shift
        and (remainder > half or (remainder == half and retained & 1))
    )
    if increment:
        retained += 1
        if retained == 1 << bits:
            retained >>= 1
            shift += 1
    normal = Value(operation.sign, operation.exponent + shift, retained)

    active = ({history for history in source_histories if history}
              if source_histories is not None else set())
    history_rule_enabled = bool(
        nearest and exact_half and len(active) == 1)
    chosen = normal
    desired_direction = 0
    if history_rule_enabled:
        desired_direction = -next(iter(active))
        lower_magnitude = materialize(operation, bits, False)[0]
        upper_magnitude = next_magnitude(lower_magnitude)
        if operation.sign:
            numeric_lower, numeric_upper = upper_magnitude, lower_magnitude
        else:
            numeric_lower, numeric_upper = lower_magnitude, upper_magnitude
        chosen = numeric_upper if desired_direction > 0 else numeric_lower

    history = compare_value_to_exact(chosen, operation)
    chosen = Value(chosen.sign, chosen.exponent, chosen.significand, history)
    return chosen, {
        "shift": shift,
        "remainder": remainder,
        "exact_half": exact_half,
        "source_histories": source_histories,
        "history_rule_enabled": history_rule_enabled,
        "desired_direction": desired_direction,
        "changed": not same_number(chosen, normal),
        "normal_history": compare_value_to_exact(normal, operation),
        "result_history": history,
    }


def multiply(left: Value, right: Value) -> ExactOperation:
    return ExactOperation(
        left.sign ^ right.sign,
        left.exponent + right.exponent,
        left.significand * right.significand,
    )


def add_same_sign(left: Value, right: Value) -> ExactOperation:
    if left.sign != right.sign:
        raise AssertionError("expected same-sign Horner addition")
    exponent = min(left.exponent, right.exponent)
    magnitude = (
        (left.significand << (left.exponent - exponent))
        + (right.significand << (right.exponent - exponent))
    )
    return ExactOperation(left.sign, exponent, magnitude)


def add_opposite_sign(left: Value, right: Value) -> ExactOperation:
    exponent = min(left.exponent, right.exponent)
    signed = (
        (-1 if left.sign else 1)
        * (left.significand << (left.exponent - exponent))
        + (-1 if right.sign else 1)
        * (right.significand << (right.exponent - exponent))
    )
    if not signed:
        return ExactOperation(0, exponent, 0)
    return ExactOperation(int(signed < 0), exponent, abs(signed))


def row_value(row: dict[str, str], name: str) -> Value:
    return Value(
        int(row[f"tc_{name}_sign"]), int(row[f"tc_{name}_exp"]),
        int(row[f"tc_{name}_sig"], 16),
    )


def run_schedule(row: dict[str, str], use_history: bool
                 ) -> tuple[dict[str, Value], dict[str, dict[str, object]]]:
    values: dict[str, Value] = {}
    metadata: dict[str, dict[str, object]] = {}
    magnitude = row_value(row, "mag")

    values["square"], metadata["square"] = materialize(
        multiply(magnitude, magnitude), 67, False)
    values["fourth"], metadata["fourth"] = materialize(
        multiply(values["square"], values["square"]), 67, False)

    def horner(prefix: str, inner_constant: int, outer_constant: int) -> Value:
        product_name = f"{prefix}_p1"
        add_name = f"{prefix}_a1"
        values[product_name], metadata[product_name] = materialize(
            multiply(values["fourth"], Value(*CONSTANTS[inner_constant])),
            67, False)
        histories = ((0, values[product_name].history)
                     if use_history else None)
        values[add_name], metadata[add_name] = materialize(
            add_same_sign(Value(*CONSTANTS[outer_constant]),
                          values[product_name]),
            64, True, histories)

        product_name = f"{prefix}_p2"
        add_name = f"{prefix}_a2"
        values[product_name], metadata[product_name] = materialize(
            multiply(values["fourth"], values[f"{prefix}_a1"]),
            67, False)
        histories = ((0, values[product_name].history)
                     if use_history else None)
        values[add_name], metadata[add_name] = materialize(
            add_same_sign(Value(*CONSTANTS[outer_constant - 2]),
                          values[product_name]),
            64, True, histories)
        return values[add_name]

    odd = horner("odd", 5, 3)
    even = horner("even", 6, 4)
    values["left"], metadata["left"] = materialize(
        multiply(values["square"], odd), 67, False)
    values["right"], metadata["right"] = materialize(
        multiply(values["fourth"], even), 67, False)
    values["terminal"], metadata["terminal"] = materialize(
        add_opposite_sign(values["left"], values["right"]), 67, False)
    return values, metadata


def verify_baseline(row: dict[str, str], values: dict[str, Value]) -> None:
    expected = {
        "square": "mul",
        "fourth": "f4",
        "odd_a2": "lf",
        "even_a2": "rf",
        "left": "left",
        "right": "right",
    }
    for actual_name, trace_name in expected.items():
        if not same_number(values[actual_name], row_value(row, trace_name)):
            raise AssertionError(
                f"{actual_name}/{trace_name} mismatch for "
                f"{row['mode']} {row['op']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("physical_rows", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    labels: dict[tuple[str, str], tuple[str, int]] = {}
    with args.physical_rows.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            labels[(row["mode"], row["op"])] = (
                row["physical_status"],
                int(row["physical_label"]) if row["physical_label"] else -1,
            )

    counts: Counter[object] = Counter()
    diagnostics: list[tuple[object, ...]] = []
    with args.features.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            key = (row["mode"], row["op"])
            status, target = labels[key]
            baseline, baseline_meta = run_schedule(row, False)
            verify_baseline(row, baseline)
            candidate, candidate_meta = run_schedule(row, True)
            counts["rows"] += 1
            counts[("status", status)] += 1
            counts[("status_target", status, target)] += 1

            any_change = False
            for stage in VALUE_STAGES:
                changed = not same_number(candidate[stage], baseline[stage])
                any_change |= changed
                counts[("value_changed", stage, changed)] += 1
                if status == "constraining":
                    counts[("constraining_changed", stage, target, changed)] += 1

            for stage in ADD_STAGES:
                meta = candidate_meta[stage]
                counts[("add_half", stage, bool(meta["exact_half"]))] += 1
                counts[("rule_enabled", stage,
                        bool(meta["history_rule_enabled"]))] += 1
                counts[("rule_changed", stage, bool(meta["changed"]))] += 1
                if status == "constraining":
                    counts[("rule_changed_target", stage, target,
                            bool(meta["changed"]))] += 1
                if meta["history_rule_enabled"] or meta["changed"]:
                    diagnostics.append((
                        row["mode"], row["op"], status, target, stage,
                        meta["source_histories"], meta["normal_history"],
                        meta["desired_direction"], meta["result_history"],
                        int(bool(meta["changed"])),
                        int(not same_number(candidate["terminal"],
                                            baseline["terminal"])),
                    ))
            counts[("row_any_change", status, target, any_change)] += 1

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target_file:
        target_file.write(f"features_sha256\t{digest(args.features)}\n")
        target_file.write(
            f"physical_rows_sha256\t{digest(args.physical_rows)}\n")
        target_file.write("mechanism\tUS5612909 RN exact-half attached "
                          "signed-direction history\n")
        target_file.write("\n[counts]\n")
        target_file.write("key\tcount\n")
        for key, value in sorted(counts.items(), key=lambda item: str(item[0])):
            if isinstance(key, tuple):
                name = ".".join(map(str, key))
            else:
                name = str(key)
            target_file.write(f"{name}\t{value}\n")
        target_file.write("\n[rule-enabled diagnostics]\n")
        target_file.write(
            "mode\top\tphysical_status\ttarget\tstage\tsource_histories\t"
            "normal_history\tdesired_direction\tresult_history\t"
            "stage_changed\tterminal_changed\n")
        for entry in diagnostics:
            target_file.write("\t".join(map(str, entry)) + "\n")

    changed_rows = sum(
        value for key, value in counts.items()
        if isinstance(key, tuple) and key[:1] == ("row_any_change",)
        and key[-1] is True)
    changed_terminal = counts[("value_changed", "terminal", True)]
    enabled = sum(
        counts[("rule_enabled", stage, True)] for stage in ADD_STAGES)
    print(
        f"rows={counts['rows']} enabled_adds={enabled} "
        f"changed_rows={changed_rows} changed_terminal={changed_terminal} "
        f"report={args.report}",
        flush=True,
    )


if __name__ == "__main__":
    main()
