#!/usr/bin/env python3
"""Test exact mathematical truth as the missing final-R59 carry selector.

This is a cached-only causal audit.  It enumerates the two exact forced
carry endpoints for the ten current targets and the 149,764 h1107 control
legs, retains all 39,464 rows where the endpoints differ, and asks an MPFR helper
which endpoint is closest to cos(x) and which equals correctly rounded
binary80 cos(x).  The helper is run independently at 768 and 1536 bits; all
classifications must agree.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path


MODES = ("rn", "rd", "ru", "rz")


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


def split_ext80(value: str) -> tuple[str, str]:
    fields = value.lower().replace(":", " ").split()
    if len(fields) != 2:
        raise RuntimeError(f"bad binary80 value {value!r}")
    return fields[0].zfill(4), fields[1].zfill(16)


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
        if key in hardware:
            raise RuntimeError(f"duplicate miss key {key}")
        operands.add(operand)
        recorded_model[key] = f"{fields[7]}:{fields[8]}"
        hardware[key] = f"{fields[10]}:{fields[11]}"
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
    if len(rows) != 149_764:
        raise RuntimeError(f"expected 149764 controls, got {len(rows)}")
    return rows


def run_model(model: Path, mode: str,
              operands: list[str]) -> dict[tuple[str, str], str]:
    process = subprocess.run(
        [str(model), "--batch", f"--rc={mode}", "--fcos-standalone"],
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
            f"{model}/{mode}: got {len(values)} outputs for "
            f"{len(operands)} inputs; stderr={process.stderr[:1000]!r}")
    return {(mode, operand): value
            for operand, value in zip(operands, values)}


def run_all(model: Path, operands_by_mode: dict[str, list[str]]) \
        -> dict[tuple[str, str], str]:
    values = {}
    for mode in MODES:
        values.update(run_model(model, mode, operands_by_mode[mode]))
    return values


def mpfr_input(rows: list[dict[str, str]]) -> str:
    rendered = []
    for row in rows:
        op_se, op_sig = split_ext80(row["op"])
        hw_se, hw_sig = split_ext80(row["hardware"])
        c0_se, c0_sig = split_ext80(row["carry0"])
        c1_se, c1_sig = split_ext80(row["carry1"])
        rendered.append("\t".join((
            row["corpus"], row["mode"], op_se, op_sig,
            hw_se, hw_sig, c0_se, c0_sig, c1_se, c1_sig,
        )))
    return "\n".join(rendered) + "\n"


def run_mpfr(helper: Path, precision: int, input_text: str) \
        -> list[dict[str, str]]:
    process = subprocess.run(
        [str(helper), "--precision", str(precision)],
        input=input_text,
        text=True,
        capture_output=True,
        check=True,
    )
    rows = []
    columns = (
        "corpus", "mode", "op_se", "op_sig", "hw_se", "hw_sig",
        "c0_se", "c0_sig", "c1_se", "c1_sig", "required",
        "nearest", "correctly_rounded", "cr_se", "cr_sig",
    )
    for line in process.stdout.splitlines():
        fields = line.split("\t")
        if len(fields) != len(columns):
            raise RuntimeError(f"bad MPFR output: {line!r}")
        rows.append(dict(zip(columns, fields)))
    if f"precision={precision} rows={len(rows)}" not in process.stderr:
        raise RuntimeError(f"unexpected MPFR summary: {process.stderr!r}")
    return rows


def counter_to_dict(counter: Counter[tuple[str, ...]]) -> dict[str, int]:
    return {"/".join(key): value for key, value in sorted(counter.items())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--carry0", required=True, type=Path)
    parser.add_argument("--carry1", required=True, type=Path)
    parser.add_argument("--misses", required=True, type=Path)
    parser.add_argument("--controls", required=True, type=Path)
    parser.add_argument("--mpfr-helper", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--failures", required=True, type=Path)
    args = parser.parse_args()
    for path in (args.report, args.failures):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")

    target_operands, failing_truth, recorded_model = read_misses(args.misses)
    controls = read_controls(args.controls)
    target_keys = {(mode, operand)
                   for operand in target_operands for mode in MODES}
    if target_keys & set(controls):
        raise RuntimeError("control bank overlaps target keys")

    operands_by_mode = {}
    for mode in MODES:
        values = set(target_operands)
        values.update(operand for row_mode, operand in controls
                      if row_mode == mode)
        operands_by_mode[mode] = sorted(values)

    baseline = run_all(args.baseline, operands_by_mode)
    carry0 = run_all(args.carry0, operands_by_mode)
    carry1 = run_all(args.carry1, operands_by_mode)
    for key, value in recorded_model.items():
        if baseline[key] != value:
            raise RuntimeError(
                f"baseline differs from recorded miss at {key}: "
                f"{baseline[key]} != {value}")
    wrong_controls = [key for key, value in controls.items()
                      if baseline[key] != value]
    if wrong_controls:
        raise RuntimeError(
            f"baseline misses {len(wrong_controls)} controls; "
            f"first={wrong_controls[:5]}")

    target_truth = {key: baseline[key] for key in target_keys}
    target_truth.update(failing_truth)
    all_truth = dict(controls)
    all_truth.update(target_truth)

    constrained = []
    endpoint_equal = 0
    unrepresented = []
    for key in sorted(all_truth):
        if carry0[key] == carry1[key]:
            endpoint_equal += 1
            continue
        truth = all_truth[key]
        represented = (truth == carry0[key]) + (truth == carry1[key])
        if represented != 1:
            unrepresented.append((key, truth, carry0[key], carry1[key]))
            continue
        mode, operand = key
        constrained.append({
            "corpus": "target" if key in target_keys else "control",
            "mode": mode,
            "op": operand,
            "hardware": truth,
            "baseline": baseline[key],
            "carry0": carry0[key],
            "carry1": carry1[key],
        })
    if unrepresented:
        raise RuntimeError(
            f"{len(unrepresented)} differing endpoint rows do not contain "
            f"hardware truth; first={unrepresented[:3]}")
    if len(constrained) != 39_464:
        raise RuntimeError(
            f"expected 39464 force-differing rows, got {len(constrained)}")

    input_text = mpfr_input(constrained)
    low = run_mpfr(args.mpfr_helper, 768, input_text)
    high = run_mpfr(args.mpfr_helper, 1536, input_text)
    if low != high:
        differences = [(a, b) for a, b in zip(low, high) if a != b]
        raise RuntimeError(
            f"MPFR classifications differ by precision on "
            f"{len(differences)} rows; first={differences[:2]}")

    required_counts = Counter()
    nearest_counts = Counter()
    cr_counts = Counter()
    failures = []
    for source, classified in zip(constrained, high):
        required = int(classified["required"])
        nearest = int(classified["nearest"])
        correctly_rounded = int(classified["correctly_rounded"])
        if required not in (0, 1):
            raise RuntimeError(f"missing required carry: {classified}")
        required_counts[(source["corpus"], source["mode"], str(required))] += 1
        nearest_counts[(
            source["corpus"], source["mode"],
            "exact" if nearest == required else "wrong",
        )] += 1
        cr_class = "unavailable" if correctly_rounded == -1 \
            else "exact" if correctly_rounded == required else "wrong"
        cr_counts[(source["corpus"], source["mode"], cr_class)] += 1
        if nearest != required or correctly_rounded != required:
            failures.append({
                **source,
                "required": required,
                "nearest": nearest,
                "correctly_rounded": correctly_rounded,
                "correctly_rounded_value":
                    f"{classified['cr_se']}:{classified['cr_sig']}",
            })

    nearest_exact = sum(value for key, value in nearest_counts.items()
                        if key[-1] == "exact")
    cr_exact = sum(value for key, value in cr_counts.items()
                   if key[-1] == "exact")
    report = {
        "experiment": "h1466_exact_truth_carry_selector",
        "status": "EXACT" if nearest_exact == len(constrained) else "FALSIFIED",
        "hardware_policy": "cached_only_no_x87_execution",
        "paper_policy": "handoff_only_no_paper_update",
        "precision_bits": [768, 1536],
        "precision_classifications_identical": True,
        "inputs": {
            "target_operands": len(target_operands),
            "target_legs": len(target_keys),
            "residual_legs": len(failing_truth),
            "control_legs": len(controls),
            "total_rows": len(all_truth),
            "endpoint_equal_rows": endpoint_equal,
            "carry_constraining_rows": len(constrained),
        },
        "nearest_exact": nearest_exact,
        "nearest_wrong": len(constrained) - nearest_exact,
        "correctly_rounded_exact": cr_exact,
        "correctly_rounded_not_required": len(constrained) - cr_exact,
        "required_carry_counts": counter_to_dict(required_counts),
        "nearest_policy_counts": counter_to_dict(nearest_counts),
        "correctly_rounded_policy_counts": counter_to_dict(cr_counts),
        "failure_rows_written": len(failures),
        "sha256": {
            "baseline": digest(args.baseline),
            "carry0": digest(args.carry0),
            "carry1": digest(args.carry1),
            "misses": digest(args.misses),
            "controls": digest(args.controls),
            "mpfr_helper": digest(args.mpfr_helper),
        },
        "bounded_conclusion": (
            "Exact mathematical truth is not the hidden R59 carry selector "
            "on the complete current carry-constraining wall."
            if nearest_exact != len(constrained) else
            "Exact mathematical truth survives the current constrained wall."
        ),
    }

    args.failures.parent.mkdir(parents=True, exist_ok=True)
    columns = (
        "corpus", "mode", "op", "hardware", "baseline", "carry0",
        "carry1", "required", "nearest", "correctly_rounded",
        "correctly_rounded_value",
    )
    with args.failures.open("x", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=columns, delimiter="\t")
        writer.writeheader()
        writer.writerows(failures)
    report["sha256"]["failures"] = digest(args.failures)
    with args.report.open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
