#!/usr/bin/env python3
"""Causally localize the ten current ledger-off FCOS residual operands.

The hardware truth is never recaptured.  The eleven failing legs come from
the authoritative h1378 miss file; the other 29 target legs are constrained
by the ledger-off model because the matched full-suite comparison proves
them exact.  A separately cached all-mode R59 control bank supplies the
collateral wall.

For each named materialization, inject exactly one numerical ulp in either
direction and replay all four architectural rounding modes.  Payload and
aligned terminal-magnitude probes use one integer unit in their native
coordinate.  Two separately compiled binaries force the unresolved final
R59 subtraction carry to zero or one.  These are causal counterfactuals, not
candidate correction rules.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


MODES = ("rn", "rd", "ru", "rz")


@dataclass(frozen=True)
class Stage:
    order: int
    name: str
    argument: str
    unit: str


STAGES = (
    Stage(0, "square", "poly-sq", "materialized numerical ulp"),
    Stage(1, "fourth_power", "poly-f4", "materialized numerical ulp"),
    Stage(2, "negative.mul1", "neg-mul1", "materialized numerical ulp"),
    Stage(3, "negative.add1", "neg-add1", "materialized numerical ulp"),
    Stage(4, "negative.mul2", "neg-mul2", "materialized numerical ulp"),
    Stage(5, "negative.add2", "neg-add2", "materialized numerical ulp"),
    Stage(6, "positive.mul1", "pos-mul1", "materialized numerical ulp"),
    Stage(7, "positive.add1", "pos-add1", "materialized numerical ulp"),
    Stage(8, "positive.mul2", "pos-mul2", "materialized numerical ulp"),
    Stage(9, "positive.add2", "pos-add2", "materialized numerical ulp"),
    Stage(10, "terminal.left_product", "term-left",
          "materialized numerical ulp"),
    Stage(11, "terminal.right_product", "term-right",
          "materialized numerical ulp"),
    Stage(12, "payload.formation", "payload", "raw payload integer unit"),
    Stage(13, "terminal.aligned_difference", "umag",
          "aligned exact subtraction unit"),
    Stage(14, "terminal.result", "term-out", "materialized numerical ulp"),
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def normalize_operand(value: str) -> str:
    fields = value.lower().split()
    if len(fields) != 2:
        raise RuntimeError(f"bad operand {value!r}")
    return " ".join(fields)


def read_misses(path: Path) -> tuple[list[str], dict[tuple[str, str], str],
                                     dict[tuple[str, str], str]]:
    operands = set()
    hardware = {}
    recorded_model = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        fields = line.lower().split()
        if len(fields) != 12 or fields[1] != "cos" or fields[6] != "ok" \
                or fields[9] != "ok":
            raise RuntimeError(f"unexpected miss row: {line}")
        mode = fields[2]
        operand = f"{fields[4]} {fields[5]}"
        key = mode, operand
        prediction = f"{fields[7]}:{fields[8]}"
        truth = f"{fields[10]}:{fields[11]}"
        if key in hardware:
            raise RuntimeError(f"duplicate miss key {key}")
        operands.add(operand)
        recorded_model[key] = prediction
        hardware[key] = truth
    if len(operands) != 10 or len(hardware) != 11:
        raise RuntimeError(
            f"expected ten operands/eleven legs, got "
            f"{len(operands)}/{len(hardware)}")
    return sorted(operands), hardware, recorded_model


def read_controls(path: Path) -> dict[tuple[str, str], str]:
    rows = {}
    with path.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            if row["insn"].lower() != "cos":
                continue
            key = row["mode"].lower(), normalize_operand(row["op"])
            value = row["hw"].lower()
            previous = rows.setdefault(key, value)
            if previous != value:
                raise RuntimeError(f"conflicting control truth for {key}")
    if not rows:
        raise RuntimeError("no cosine controls")
    return rows


def run(model: Path, mode: str, operands: list[str],
        perturb: str | None = None) -> dict[tuple[str, str], str]:
    command = [str(model), "--batch", f"--rc={mode}",
               "--fcos-standalone"]
    if perturb is not None:
        command.append("--perturb=" + perturb)
    process = subprocess.run(
        command,
        input="\n".join(operands) + "\n",
        text=True,
        capture_output=True,
        check=True,
    )
    values = []
    for line in process.stdout.splitlines():
        fields = line.lower().split()
        if len(fields) == 3 and fields[0] == "ok":
            values.append(f"{fields[1]}:{fields[2]}")
    if len(values) != len(operands):
        raise RuntimeError(
            f"{model}/{mode}/{perturb}: got {len(values)} outputs for "
            f"{len(operands)} inputs; stderr={process.stderr[:1000]!r}")
    return {(mode, operand): value
            for operand, value in zip(operands, values)}


def run_all(model: Path, operands_by_mode: dict[str, list[str]],
            perturb: str | None = None) -> dict[tuple[str, str], str]:
    values = {}
    for mode in MODES:
        values.update(run(model, mode, operands_by_mode[mode], perturb))
    return values


def rendered_modes(keys: list[tuple[str, str]]) -> str:
    return ",".join(mode for mode, _ in keys) or "-"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--carry0", required=True, type=Path)
    parser.add_argument("--carry1", required=True, type=Path)
    parser.add_argument("--misses", required=True, type=Path)
    parser.add_argument("--controls", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--details", required=True, type=Path)
    args = parser.parse_args()
    for path in (args.report, args.details):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")

    target_operands, failing_truth, recorded_model = read_misses(args.misses)
    controls = read_controls(args.controls)
    target_keys = {(mode, operand)
                   for operand in target_operands for mode in MODES}
    overlap = target_keys & set(controls)
    if overlap:
        raise RuntimeError(f"control bank overlaps target keys: {overlap}")

    operands_by_mode = {}
    for mode in MODES:
        values = set(target_operands)
        values.update(operand for row_mode, operand in controls
                      if row_mode == mode)
        operands_by_mode[mode] = sorted(values)

    baseline = run_all(args.model, operands_by_mode)
    for key, value in recorded_model.items():
        if baseline[key] != value:
            raise RuntimeError(
                f"baseline differs from authoritative miss row at {key}: "
                f"{baseline[key]} != {value}")
    control_baseline_misses = [
        key for key, value in controls.items() if baseline[key] != value
    ]
    if control_baseline_misses:
        raise RuntimeError(
            f"baseline misses {len(control_baseline_misses)} cached controls; "
            f"first={control_baseline_misses[:5]}")

    target_truth = {key: baseline[key] for key in target_keys}
    target_truth.update(failing_truth)
    baseline_correct = {
        key for key in target_keys if baseline[key] == target_truth[key]
    }
    if len(baseline_correct) != 29:
        raise RuntimeError(
            f"expected 29 baseline-correct target legs, got "
            f"{len(baseline_correct)}")

    variants = []
    for stage in STAGES:
        for delta in (-1, 1):
            variants.append({
                "kind": "ulp",
                "stage_order": stage.order,
                "stage": stage.name,
                "delta": delta,
                "unit": stage.unit,
                "model": args.model,
                "perturb": f"{stage.argument}:{delta}",
            })
    variants.extend((
        {"kind": "carry", "stage_order": 15, "stage": "r59.final_carry",
         "delta": 0, "unit": "forced unresolved carry", "model": args.carry0,
         "perturb": None},
        {"kind": "carry", "stage_order": 15, "stage": "r59.final_carry",
         "delta": 1, "unit": "forced unresolved carry", "model": args.carry1,
         "perturb": None},
    ))

    summaries = []
    details = []
    exact_by_operand: dict[str, list[dict[str, object]]] = defaultdict(list)
    for variant in variants:
        outputs = run_all(
            Path(variant["model"]), operands_by_mode,
            str(variant["perturb"]) if variant["perturb"] is not None else None)
        target_exact = {key for key in target_keys
                        if outputs[key] == target_truth[key]}
        repaired = sorted(set(failing_truth) & target_exact)
        target_collateral = sorted(
            key for key in baseline_correct if key not in target_exact)
        control_collateral = sorted(
            key for key, truth in controls.items() if outputs[key] != truth)
        exact_operands = []
        for operand in target_operands:
            operand_keys = [(mode, operand) for mode in MODES]
            exact_modes = [key for key in operand_keys if key in target_exact]
            repaired_modes = [key for key in operand_keys
                              if key in failing_truth and key in target_exact]
            collateral_modes = [key for key in operand_keys
                                if key in target_collateral]
            all_mode_exact = len(exact_modes) == len(MODES)
            if all_mode_exact:
                exact_operands.append(operand)
                exact_by_operand[operand].append(variant)
            details.append({
                "kind": variant["kind"],
                "stage_order": variant["stage_order"],
                "stage": variant["stage"],
                "delta": variant["delta"],
                "unit": variant["unit"],
                "op": operand,
                "exact_modes": rendered_modes(exact_modes),
                "all_mode_exact": int(all_mode_exact),
                "repaired_residual_modes": rendered_modes(repaired_modes),
                "collateral_target_modes": rendered_modes(collateral_modes),
            })
        summary = {
            "kind": variant["kind"],
            "stage_order": variant["stage_order"],
            "stage": variant["stage"],
            "delta": variant["delta"],
            "unit": variant["unit"],
            "repaired_residual_legs": len(repaired),
            "target_collateral_legs": len(target_collateral),
            "all_mode_exact_operands": len(exact_operands),
            "control_collateral_legs": len(control_collateral),
            "exact_operand_list": ",".join(exact_operands) or "-",
        }
        summaries.append(summary)
        print(
            f"{variant['stage']}:{variant['delta']:+d} "
            f"repairs={len(repaired)}/11 target_collateral="
            f"{len(target_collateral)}/29 exact_operands="
            f"{len(exact_operands)}/10 controls="
            f"{len(control_collateral)}/{len(controls)}",
            flush=True,
        )

    args.details.parent.mkdir(parents=True, exist_ok=True)
    with args.details.open("x", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=tuple(details[0]),
                                delimiter="\t")
        writer.writeheader()
        writer.writerows(details)

    ranked = sorted(
        summaries,
        key=lambda row: (
            -int(row["all_mode_exact_operands"]),
            -int(row["repaired_residual_legs"]),
            int(row["target_collateral_legs"]),
            int(row["control_collateral_legs"]),
            int(row["stage_order"]),
            abs(int(row["delta"])),
            int(row["delta"]),
        ),
    )
    with args.report.open("x") as target:
        for name, path in (
            ("model", args.model), ("carry0", args.carry0),
            ("carry1", args.carry1), ("misses", args.misses),
            ("controls", args.controls), ("details", args.details),
        ):
            target.write(f"{name}_sha256\t{digest(path)}\n")
        target.write("hardware_policy\tcached_only_no_x87_execution\n")
        target.write("truth_policy\t11_h1378_hardware_legs_plus_29_matched_"
                     "ledger_off_exact_legs\n")
        target.write("injection_policy\texact_plus_or_minus_one_native_"
                     "stage_unit_or_forced_binary_r59_carry\n")
        target.write(f"target_operands\t{len(target_operands)}\n")
        target.write(f"target_legs\t{len(target_keys)}\n")
        target.write(f"residual_legs\t{len(failing_truth)}\n")
        target.write(f"baseline_correct_target_legs\t{len(baseline_correct)}\n")
        target.write(f"cached_control_legs\t{len(controls)}\n")
        target.write("\n[stage-by-stage elimination table]\n")
        columns = tuple(key for key in summaries[0]
                        if key != "exact_operand_list")
        target.write("\t".join(columns) + "\n")
        for row in summaries:
            target.write("\t".join(str(row[column]) for column in columns)
                         + "\n")
        target.write("\n[shared counterfactual ranking]\n")
        target.write("\t".join(summaries[0]) + "\n")
        for row in ranked:
            target.write("\t".join(str(row[column]) for column in row) + "\n")
        target.write("\n[earliest all-mode exact counterfactual per operand]\n")
        target.write("op\tearliest_stage_order\tvariants\n")
        for operand in target_operands:
            exact = exact_by_operand[operand]
            if not exact:
                target.write(f"{operand}\t-\t-\n")
                continue
            earliest = min(int(row["stage_order"]) for row in exact)
            earliest_rows = [row for row in exact
                             if int(row["stage_order"]) == earliest]
            rendered = ",".join(
                f"{row['stage']}:{int(row['delta']):+d}"
                for row in earliest_rows)
            target.write(f"{operand}\t{earliest}\t{rendered}\n")
        target.write("\n[all all-mode exact counterfactuals per operand]\n")
        target.write("op\tvariants\n")
        for operand in target_operands:
            rendered = ",".join(
                f"{row['stage']}:{int(row['delta']):+d}"
                for row in exact_by_operand[operand]) or "-"
            target.write(f"{operand}\t{rendered}\n")

    print(f"wrote {args.report} and {args.details}", flush=True)


if __name__ == "__main__":
    main()
