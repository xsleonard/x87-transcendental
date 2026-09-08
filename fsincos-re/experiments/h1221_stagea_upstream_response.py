#!/usr/bin/env python3
"""Causally localize the two non-endpoint stage-A residuals.

The dense h1214 classification found two operands whose cached four-mode
truth cannot be represented by either ordinary terminal carry endpoint.  This
software-only experiment perturbs one named producer at a time by a small
integer amount and compares every result with the already reconstructed h1210
four-mode truth.  Producer nudges are causal probes, never correction rules.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import subprocess
from collections import defaultdict
from pathlib import Path


MODES = ("rn", "rd", "ru", "rz")
PRODUCERS = (
    "red", "mag", "sq", "f4", "odd", "even", "left", "right",
    "payload", "umag",
)
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


def read_truth(path: Path) -> tuple[dict[tuple[str, str], str], list[str]]:
    truth = {}
    with path.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            mode = row["mode"].lower()
            operand = row["op"].lower()
            key = mode, operand
            hardware = row["hw"].lower()
            if key in truth and truth[key] != hardware:
                raise RuntimeError(f"conflicting truth for {key}")
            truth[key] = hardware
    operands = sorted({operand for _, operand in truth})
    for operand in operands:
        missing = [mode for mode in MODES if (mode, operand) not in truth]
        if missing:
            raise RuntimeError(f"missing modes for {operand}: {missing}")
    if not TARGETS <= set(operands):
        raise RuntimeError(f"missing targets: {sorted(TARGETS - set(operands))}")
    return truth, operands


def run(model: Path, mode: str, operands: list[str], producer: str | None,
        delta: int) -> list[str]:
    command = [str(model), "--batch", f"--rc={mode}", "--fcos-standalone"]
    if producer is not None:
        command.append(f"--perturb={producer}:{delta}")
    process = subprocess.run(
        command, input="\n".join(operands) + "\n", text=True,
        capture_output=True, check=True,
    )
    values = []
    for line in process.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[0] == "OK":
            values.append(fields[1].lower() + ":" + fields[2].lower())
    if len(values) != len(operands):
        raise RuntimeError(
            f"output count {len(values)} != {len(operands)} for "
            f"{producer}:{delta}/{mode}"
        )
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("truth", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    truth, operands = read_truth(args.truth)
    baseline = {}
    for mode in MODES:
        values = run(args.model, mode, operands, None, 0)
        for operand, value in zip(operands, values):
            baseline[mode, operand] = value

    baseline_wrong = {
        key for key, value in baseline.items() if value != truth[key]
    }
    target_wrong = baseline_wrong & {
        (mode, operand) for mode in MODES for operand in TARGETS
    }
    if not target_wrong:
        raise RuntimeError("both targets are already exact in the baseline")

    rankings = []
    target_matches = defaultdict(list)
    for producer in PRODUCERS:
        for delta in range(-4, 5):
            outputs = {}
            for mode in MODES:
                values = run(args.model, mode, operands, producer, delta)
                for operand, value in zip(operands, values):
                    outputs[mode, operand] = value
            matched = {key for key, value in outputs.items()
                       if value == truth[key]}
            exact_operands = {
                operand for operand in operands
                if all((mode, operand) in matched for mode in MODES)
            }
            exact_targets = exact_operands & TARGETS
            fixes = baseline_wrong & matched
            regressions = set(baseline) - baseline_wrong - matched
            target_legs = sum(
                (mode, operand) in matched
                for operand in TARGETS for mode in MODES
            )
            rankings.append((
                len(exact_targets), target_legs, len(fixes),
                -len(regressions), len(exact_operands), len(matched),
                producer, delta,
            ))
            for operand in exact_targets:
                target_matches[operand].append((producer, delta))
            print(
                f"{producer}:{delta:+d} targets={len(exact_targets)}/2 "
                f"target_legs={target_legs}/8 fixes={len(fixes)} "
                f"regressions={len(regressions)}", flush=True,
            )

    rankings.sort(key=lambda row: (
        -row[0], -row[1], -row[2], -row[3], -row[4], -row[5],
        row[6], abs(row[7]), row[7],
    ))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target_file:
        target_file.write(f"model_sha256\t{digest(args.model)}\n")
        target_file.write(f"truth_sha256\t{digest(args.truth)}\n")
        target_file.write("hardware_policy\tcached_h1210_truth_no_x87_execution\n")
        target_file.write(f"operands\t{len(operands)}\n")
        target_file.write(f"baseline_wrong_legs\t{len(baseline_wrong)}\n")
        target_file.write(f"target_wrong_legs\t{len(target_wrong)}\n")
        target_file.write("targets\t" + ",".join(sorted(TARGETS)) + "\n")
        target_file.write("\n[baseline target residuals]\n")
        target_file.write("mode\top\tmodel\thardware\texact\n")
        for operand in sorted(TARGETS):
            for mode in MODES:
                key = mode, operand
                target_file.write(
                    f"{mode}\t{operand}\t{baseline[key]}\t{truth[key]}\t"
                    f"{int(baseline[key] == truth[key])}\n"
                )
        target_file.write("\n[variant ranking]\n")
        target_file.write(
            "exact_targets\ttarget_legs\tfixes\tregressions\t"
            "exact_operands\texact_legs\tproducer\tdelta\n"
        )
        for row in rankings:
            rendered = (*row[:3], -row[3], *row[4:])
            target_file.write("\t".join(map(str, rendered)) + "\n")
        target_file.write("\n[all-mode exact variants per target]\n")
        target_file.write("op\tcount\tvariants\n")
        for operand in sorted(TARGETS):
            variants = sorted(
                target_matches[operand],
                key=lambda item: (item[0], abs(item[1]), item[1]),
            )
            rendered = ",".join(
                f"{producer}:{delta:+d}" for producer, delta in variants
            )
            target_file.write(f"{operand}\t{len(variants)}\t{rendered or '-'}\n")

    print(f"wrote {args.report} best={rankings[0]}", flush=True)


if __name__ == "__main__":
    main()
