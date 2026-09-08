#!/usr/bin/env python3
"""Close the literal directed-rounding coverage gap in Intel US5612909.

The patent defines ``up`` and ``down`` as numerical directions: round toward
positive and negative infinity, respectively, and separately says that source
operand signs enter the history control.  h1205 and h1429 therefore used the
right sign convention; a magnitude-direction reinterpretation is not another
source-conformant candidate.

The patent publishes two concrete examples relevant to the recovered cosine
ending.  Its RN table acts when the current result is exactly halfway, while
its round-toward-positive-infinity table is explicitly illustrated by
``round-bit=0, sticky=0`` (an exact retained-grid result).  With the exact +1
operand and one inexact correction operand at the final ``FINAL_ADD``, those
tables reduce to fixed rules:

* RN exact half: select the endpoint opposite the correction history.
* RU exact grid: advance one ulp only when the correction was rounded down.

This script scores the previously tested RN-only placement, the missing
RU-only placement, and both published tables together.  It does not search
subsets, operand predicates, thresholds, or truth tables, and it executes no
hardware.  Immutable cached labels are loaded only for scoring.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from pathlib import Path

import h58_constraint_search as h58
import h1424_subtract_final_add_interstage_carrier as h1424
from h1184_upstream_halfway_audit import ExactOperation, Value


POLICIES = ("rn_only", "ru_only", "rn_and_ru")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def compare_value_to_exact(value: Value, exact: ExactOperation) -> int:
    """Compare a materialized value with its exact source numerically."""
    if value.sign != exact.sign:
        raise RuntimeError("materialization unexpectedly changed sign")
    common = min(value.exponent, exact.exponent)
    stored = value.significand << (value.exponent - common)
    source = exact.magnitude << (exact.exponent - common)
    difference = stored - source
    if value.sign:
        difference = -difference
    return (difference > 0) - (difference < 0)


def round_metadata(value: h58.FP) -> tuple[int, int, int, bool, bool, int]:
    """Return shift/remainder/half, exact-half/grid, and retained LSB."""
    shift = max(0, value[1].bit_length() - 64)
    if not shift:
        return 0, 0, 0, False, True, value[1] & 1
    remainder = value[1] & ((1 << shift) - 1)
    half = 1 << (shift - 1)
    retained = value[1] >> shift
    return (
        shift,
        remainder,
        half,
        remainder == half,
        remainder == 0,
        retained & 1,
    )


def next_positive_grid(value: h58.FP) -> h58.FP:
    """Return the 64-bit grid point one ulp above a positive exact point."""
    lower = h58.round_fp(value, 64, "chop")
    if lower[0] or h58.round_fp(value, 64, "away") != lower:
        raise RuntimeError("expected a positive exact 64-bit grid point")
    significand = lower[1] + 1
    scale = lower[2]
    if significand.bit_length() > 64:
        significand >>= 1
        scale += 1
    return 0, significand, scale


def output_delta(left: str, right: str) -> int | None:
    """Return significand delta when two encodings share an exponent."""
    left_exponent, left_significand = left.split(":")
    right_exponent, right_significand = right.split(":")
    if left_exponent != right_exponent:
        return None
    return int(left_significand, 16) - int(right_significand, 16)


def literal_outputs(
    row: dict[str, str],
) -> tuple[dict[str, str], dict[str, object]]:
    exact_correction = h1424.exact_subtract(row)
    stored_correction_value = h1424.incumbent_bus(row).value()
    stored_correction = Value(
        stored_correction_value[0],
        stored_correction_value[2],
        stored_correction_value[1],
    )
    history = compare_value_to_exact(stored_correction, exact_correction)
    hidden = h58.add_exact((0, 1, 0), stored_correction_value)
    shift, remainder, half, exact_half, exact_grid, retained_lsb = (
        round_metadata(hidden)
    )
    normal = h1424.rounded_output(hidden, row["mode"])

    rn_enabled = row["mode"] == "rn" and exact_half and history != 0
    rn_value = hidden
    if rn_enabled:
        rn_value = h58.round_fp(
            hidden, 64, "away" if -history > 0 else "chop"
        )
    rn_output = h1424.rounded_output(rn_value, row["mode"])

    # The patent's RU example gives round-bit=0/sticky=0 and says
    # down/exact -> up, while up/exact and exact/exact select the ordinary
    # lower endpoint.  At this positive cosine output, "up" is +1 ulp.
    ru_enabled = row["mode"] == "ru" and exact_grid and history < 0
    ru_value = next_positive_grid(hidden) if ru_enabled else hidden
    ru_output = h1424.rounded_output(ru_value, row["mode"])

    combined_value = hidden
    if rn_enabled:
        combined_value = rn_value
    elif ru_enabled:
        combined_value = ru_value
    combined_output = h1424.rounded_output(combined_value, row["mode"])

    return {
        "rn_only": rn_output,
        "ru_only": ru_output,
        "rn_and_ru": combined_output,
    }, {
        "history": history,
        "shift": shift,
        "remainder": remainder,
        "half": half,
        "exact_half": exact_half,
        "exact_grid": exact_grid,
        "retained_lsb": retained_lsb,
        "rn_enabled": rn_enabled,
        "ru_enabled": ru_enabled,
        "normal": normal,
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

    counts: Counter[tuple[str, str]] = Counter()
    target_diagnostics: list[tuple[object, ...]] = []
    ru_enabled_diagnostics: list[tuple[object, ...]] = []
    for row in rows:
        outputs, metadata = literal_outputs(row)
        target = row["label"] == "POS"
        hardware = row["hw"].lower()
        model = row["model"].lower()
        for policy in POLICIES:
            candidate = outputs[policy]
            wrong = candidate != hardware
            changed = candidate != model
            counts[(policy, "errors")] += wrong
            counts[(policy, "target_errors")] += target and wrong
            counts[(policy, "control_errors")] += not target and wrong
            counts[(policy, "target_repairs")] += target and not wrong
            counts[(policy, "control_changes")] += not target and changed

        counts[("events", "rn_enabled")] += bool(metadata["rn_enabled"])
        counts[("events", "ru_enabled")] += bool(metadata["ru_enabled"])
        counts[("events", "target_rn_enabled")] += (
            target and bool(metadata["rn_enabled"])
        )
        counts[("events", "target_ru_enabled")] += (
            target and bool(metadata["ru_enabled"])
        )

        diagnostic = (
            row["mode"],
            row["op"],
            row["label"],
            row.get("desired", ""),
            metadata["history"],
            metadata["shift"],
            f"0x{metadata['remainder']:x}",
            f"0x{metadata['half']:x}",
            int(bool(metadata["exact_half"])),
            int(bool(metadata["exact_grid"])),
            metadata["retained_lsb"],
            int(bool(metadata["rn_enabled"])),
            int(bool(metadata["ru_enabled"])),
            model,
            outputs["rn_only"],
            outputs["ru_only"],
            outputs["rn_and_ru"],
            hardware,
            output_delta(hardware, model),
        )
        if target:
            target_diagnostics.append(diagnostic)
        if metadata["ru_enabled"]:
            ru_enabled_diagnostics.append(diagnostic)

    header = (
        "mode\top\tlabel\tdesired\tcorrection_history\tfinal_shift\t"
        "final_remainder\tfinal_half\texact_half\texact_grid\t"
        "retained_lsb\trn_enabled\tru_enabled\tmodel\trn_only\tru_only\t"
        "rn_and_ru\thardware\thardware_minus_model_ulp\n"
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
        output.write("history_direction\tsigned_numeric_patent_definition\n")
        output.write(
            "mechanism\tUS5612909_literal_RN_half_and_RU_exact-grid_tables_"
            "at_final_FINAL_ADD\n"
        )
        output.write(f"rows\t{len(rows)}\n")
        output.write(f"targets\t{targets}\n")
        output.write(f"controls\t{controls}\n")
        output.write(f"rn_enabled\t{counts[('events', 'rn_enabled')]}\n")
        output.write(f"ru_enabled\t{counts[('events', 'ru_enabled')]}\n")
        output.write(
            f"target_rn_enabled\t{counts[('events', 'target_rn_enabled')]}\n"
        )
        output.write(
            f"target_ru_enabled\t{counts[('events', 'target_ru_enabled')]}\n"
        )
        output.write("\n[policy scores]\n")
        output.write(
            "policy\terrors\ttarget_errors\tcontrol_errors\t"
            "target_repairs\tcontrol_changes\texact\t"
            "zero_control_collateral_improvement\n"
        )
        for policy in POLICIES:
            values = tuple(
                counts[(policy, key)]
                for key in (
                    "errors",
                    "target_errors",
                    "control_errors",
                    "target_repairs",
                    "control_changes",
                )
            )
            exact = int(values[0] == 0)
            improvement = int(values[3] > 0 and values[2] == 0)
            output.write(
                "\t".join(map(str, (policy, *values, exact, improvement)))
                + "\n"
            )

        output.write("\n[target diagnostics]\n")
        output.write(header)
        for diagnostic in target_diagnostics:
            output.write("\t".join(map(str, diagnostic)) + "\n")

        output.write("\n[RU-history-enabled diagnostics]\n")
        output.write(header)
        for diagnostic in ru_enabled_diagnostics:
            output.write("\t".join(map(str, diagnostic)) + "\n")

    print(
        f"wrote {args.report}: rows={len(rows)} "
        + " ".join(
            f"{policy}=errors:{counts[(policy, 'errors')]},"
            f"repairs:{counts[(policy, 'target_repairs')]},"
            f"control_errors:{counts[(policy, 'control_errors')]}"
            for policy in POLICIES
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
