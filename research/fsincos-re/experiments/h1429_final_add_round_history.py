#!/usr/bin/env python3
"""Audit Intel's literal attached-history rule at the final FINAL_ADD.

The cosine model materializes the terminal ``_FSUB`` correction and
then adds it to signed one with ``FINAL_ADD``.  h1205 applied the concrete
US5612909 exact-half rule to the internal Horner FADDs, but not to this final
operation.  This experiment closes that placement gap: the correction gets a
signed history equal to materialized-minus-exact ``S-B`` and signed one gets
an exact history.  On an RN exact half, one nonzero source-history direction
forces the result to the endpoint opposite that direction, exactly as in the
published rule.  All other rows retain the incumbent architectural result.

This is one fixed, source-defined rule.  There are no operand predicates,
identity keys, learned thresholds, fitted truth tables, or hardware captures.
The immutable cached labels are loaded only for scoring.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from pathlib import Path

import h58_constraint_search as h58
import h1424_subtract_final_add_interstage_carrier as h1424
from h1184_upstream_halfway_audit import ExactOperation, Value


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def compare_value_to_exact(value: Value, exact: ExactOperation) -> int:
    """Compare a materialized value with its exact source in signed order."""
    if value.sign != exact.sign:
        raise RuntimeError("materialization unexpectedly changed sign")
    common = min(value.exponent, exact.exponent)
    stored = value.significand << (value.exponent - common)
    source = exact.magnitude << (exact.exponent - common)
    difference = stored - source
    if value.sign:
        difference = -difference
    return (difference > 0) - (difference < 0)


def compare_fp(left: h58.FP, right: h58.FP) -> int:
    """Compare two exact FP tuples in signed numeric order."""
    scale = min(left[2], right[2])
    left_integer = (-1 if left[0] else 1) * (
        left[1] << (left[2] - scale))
    right_integer = (-1 if right[0] else 1) * (
        right[1] << (right[2] - scale))
    return (left_integer > right_integer) - (left_integer < right_integer)


def round_metadata(value: h58.FP) -> tuple[int, int, int, bool, int]:
    """Return shift, remainder, half, exact-half, and retained LSB."""
    shift = max(0, value[1].bit_length() - 64)
    if not shift:
        return 0, 0, 0, False, value[1] & 1
    remainder = value[1] & ((1 << shift) - 1)
    half = 1 << (shift - 1)
    retained = value[1] >> shift
    return shift, remainder, half, remainder == half, retained & 1


def output_delta(left: str, right: str) -> int | None:
    """Return significand delta when two encoded values share an exponent."""
    left_exponent, left_significand = left.split(":")
    right_exponent, right_significand = right.split(":")
    if left_exponent != right_exponent:
        return None
    return int(left_significand, 16) - int(right_significand, 16)


def literal_output(row: dict[str, str]) -> tuple[str, dict[str, object]]:
    exact_correction = h1424.exact_subtract(row)
    stored_correction_value = h1424.incumbent_bus(row).value()
    stored_correction = Value(
        stored_correction_value[0], stored_correction_value[2],
        stored_correction_value[1],
    )
    history = compare_value_to_exact(stored_correction, exact_correction)
    hidden = h58.add_exact((0, 1, 0), stored_correction_value)
    shift, remainder, half, exact_half, retained_lsb = round_metadata(hidden)
    normal = h1424.rounded_output(hidden, row["mode"])

    enabled = row["mode"] == "rn" and exact_half and history != 0
    chosen = hidden
    desired_direction = 0
    if enabled:
        desired_direction = -history
        chosen = h58.round_fp(
            hidden, 64, "away" if desired_direction > 0 else "chop")
    candidate = h1424.rounded_output(chosen, row["mode"])

    exact_tail = h1424.exact_subtract(row)
    exact_tail_hidden = h58.add_exact(
        (0, 1, 0),
        (exact_tail.sign, exact_tail.magnitude, exact_tail.exponent),
    )
    exact_tail_output = h1424.rounded_output(exact_tail_hidden, row["mode"])
    return candidate, {
        "history": history,
        "shift": shift,
        "remainder": remainder,
        "half": half,
        "exact_half": exact_half,
        "retained_lsb": retained_lsb,
        "enabled": enabled,
        "desired_direction": desired_direction,
        "normal": normal,
        "changed": candidate != normal,
        "exact_tail_relation": compare_fp(exact_tail_hidden, hidden),
        "exact_tail_output": exact_tail_output,
        "final_grid_exact": remainder == 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("model", type=Path)
    parser.add_argument("misses", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--extra-op", default="3ffc d0d000000cc0b3f8")
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    rows = h1424.read_rows(args.features)
    h1424.append_extra_rows(rows, args.model, args.misses, args.extra_op)
    targets = sum(row["label"] == "POS" for row in rows)
    controls = len(rows) - targets
    if targets != 11:
        raise RuntimeError(f"expected eleven frontier legs, got {targets}")

    counts: Counter[str] = Counter()
    target_diagnostics = []
    enabled_diagnostics = []
    contradiction_diagnostics = []
    for row in rows:
        candidate, metadata = literal_output(row)
        target = row["label"] == "POS"
        hardware = row["hw"].lower()
        model = row["model"].lower()
        wrong = candidate != hardware
        changed = candidate != model

        counts["errors"] += wrong
        counts["target_errors"] += target and wrong
        counts["control_errors"] += not target and wrong
        counts["target_repairs"] += target and not wrong
        counts["control_changes"] += not target and changed
        counts["rule_enabled"] += bool(metadata["enabled"])
        counts["rule_changed"] += bool(metadata["changed"])
        counts["target_rule_enabled"] += target and bool(metadata["enabled"])
        counts["target_rule_changed"] += target and bool(metadata["changed"])
        counts["control_rule_enabled"] += not target and bool(metadata["enabled"])
        counts["control_rule_changed"] += not target and bool(metadata["changed"])

        diagnostic = (
            row["mode"], row["op"], row["label"], row.get("desired", ""),
            metadata["history"], metadata["shift"],
            f"0x{metadata['remainder']:x}", f"0x{metadata['half']:x}",
            int(bool(metadata["exact_half"])), metadata["retained_lsb"],
            int(bool(metadata["enabled"])), metadata["desired_direction"],
            model, candidate, metadata["exact_tail_relation"],
            metadata["exact_tail_output"], hardware,
            output_delta(hardware, model), int(not wrong),
        )
        if target:
            target_diagnostics.append(diagnostic)
        if metadata["enabled"]:
            enabled_diagnostics.append(diagnostic)

        contradiction = bool(
            target
            and row["mode"] == "ru"
            and metadata["history"] > 0
            and metadata["final_grid_exact"]
            and metadata["exact_tail_relation"] < 0
            and output_delta(hardware, model) == 1
        )
        if contradiction:
            contradiction_diagnostics.append(diagnostic)

    header = (
        "mode\top\tlabel\tdesired\tcorrection_history\tfinal_shift\t"
        "final_remainder\tfinal_half\texact_half\tretained_lsb\t"
        "rule_enabled\tdesired_direction\tmodel\tliteral\t"
        "exact_tail_relation_to_stored\texact_tail\thardware\t"
        "hardware_minus_model_ulp\tliteral_correct\n"
    )

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        for name, path in (
            ("features", args.features),
            ("model", args.model),
            ("misses", args.misses),
        ):
            output.write(f"{name}_sha256\t{digest(path)}\n")
        output.write("hardware_policy\timmutable_cached_labels_no_x87_execution\n")
        output.write(
            "mechanism\tUS5612909_literal_RN_exact-half_attached-"
            "history_rule_at_final_FINAL_ADD\n")
        output.write(f"rows\t{len(rows)}\n")
        output.write(f"targets\t{targets}\n")
        output.write(f"controls\t{controls}\n")
        for key in (
            "errors", "target_errors", "control_errors", "target_repairs",
            "control_changes", "rule_enabled", "rule_changed",
            "target_rule_enabled", "target_rule_changed",
            "control_rule_enabled", "control_rule_changed",
        ):
            output.write(f"{key}\t{counts[key]}\n")
        output.write("exact_programs\t" + str(int(counts["errors"] == 0)) + "\n")
        output.write(
            "zero_control_collateral_improvements\t"
            + str(int(counts["target_repairs"] > 0
                      and counts["control_errors"] == 0)) + "\n")
        output.write(
            "opposite_signed-error_corner_contradictions\t"
            f"{len(contradiction_diagnostics)}\n")

        output.write("\n[target diagnostics]\n")
        output.write(header)
        for diagnostic in target_diagnostics:
            output.write("\t".join(map(str, diagnostic)) + "\n")

        output.write("\n[rule-enabled diagnostics]\n")
        output.write(header)
        for diagnostic in enabled_diagnostics:
            output.write("\t".join(map(str, diagnostic)) + "\n")

        output.write("\n[opposite signed-error corner contradictions]\n")
        output.write(header)
        for diagnostic in contradiction_diagnostics:
            output.write("\t".join(map(str, diagnostic)) + "\n")

    print(
        f"wrote {args.report}: rows={len(rows)} errors={counts['errors']} "
        f"target_repairs={counts['target_repairs']} "
        f"control_errors={counts['control_errors']} "
        f"enabled={counts['rule_enabled']} "
        f"corner_contradictions={len(contradiction_diagnostics)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
