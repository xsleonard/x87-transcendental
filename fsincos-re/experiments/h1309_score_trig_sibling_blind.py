#!/usr/bin/env python3
"""Score the one-shot h1308 FSIN capture against both causal endpoints."""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path


CAPTURE_MODES = ("rn", "rd", "ru")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def load_capture(directory: Path) -> dict[tuple[str, str], str]:
    captured = {}
    for mode in CAPTURE_MODES:
        input_path = directory / f"{mode}_inputs.txt"
        hardware_path = directory / f"{mode}_hardware.txt"
        operands = [
            line.strip().lower() for line in input_path.read_text().splitlines()
            if line.strip()
        ]
        values = []
        for line in hardware_path.read_text().splitlines():
            fields = line.lower().split()
            if len(fields) != 3 or fields[0] != "ok":
                raise RuntimeError(f"bad hardware line: {line}")
            values.append(f"{fields[1]}:{fields[2]}")
        if len(operands) != len(values):
            raise RuntimeError(
                f"{mode}: {len(operands)} inputs, {len(values)} outputs")
        for operand, value in zip(operands, values):
            key = mode, operand
            if key in captured:
                raise RuntimeError(f"duplicate capture pair {key}")
            captured[key] = value
    return captured


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("changes", type=Path)
    parser.add_argument("capture_directory", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    labels_path = args.report.with_name(args.report.stem + "_labels.tsv")
    for output_path in (args.report, labels_path):
        if output_path.exists():
            raise SystemExit(f"refusing to overwrite {output_path}")

    with args.changes.open(newline="") as source:
        changes = list(csv.DictReader(source, delimiter="\t"))
    captured = load_capture(args.capture_directory)
    expected = {(row["mode"], row["op"].lower()) for row in changes}
    if set(captured) != expected:
        raise RuntimeError(
            f"capture mismatch: missing={expected-set(captured)} "
            f"extra={set(captured)-expected}")

    counts = Counter()
    labels = []
    verdicts_by_operand: dict[str, set[str]] = defaultdict(set)
    for row in changes:
        key = row["mode"], row["op"].lower()
        hardware = captured[key]
        predecessor = row["predecessor"].lower()
        wide = row["wide"].lower()
        if hardware == predecessor:
            verdict = "predecessor"
        elif hardware == wide:
            verdict = "wide"
        else:
            verdict = "neither"
        counts[f"verdict.{verdict}"] += 1
        counts[f"mode.{row['mode']}.verdict.{verdict}"] += 1
        counts[f"q.{row['q']}.verdict.{verdict}"] += 1
        verdicts_by_operand[row["op"].lower()].add(verdict)
        labels.append({
            **row,
            "hardware": hardware,
            "verdict": verdict,
        })

    inconsistent = {
        operand: verdicts
        for operand, verdicts in verdicts_by_operand.items()
        if len(verdicts) != 1 or "neither" in verdicts
    }
    if inconsistent:
        raise RuntimeError(f"inconsistent causal verdicts: {inconsistent}")

    columns = tuple(labels[0])
    with labels_path.open("x", newline="") as target:
        writer = csv.DictWriter(target, columns, delimiter="\t")
        writer.writeheader()
        writer.writerows(labels)
    with args.report.open("x") as target:
        target.write(f"changes_sha256\t{digest(args.changes)}\n")
        for mode in CAPTURE_MODES:
            target.write(
                f"inputs_sha256.{mode}\t"
                f"{digest(args.capture_directory / f'{mode}_inputs.txt')}\n")
            target.write(
                f"hardware_sha256.{mode}\t"
                f"{digest(args.capture_directory / f'{mode}_hardware.txt')}\n")
        target.write("hardware_policy\tone_capture_per_mode_operand_pair\n")
        target.write("capture_processor\tIntel_Core_i7-6700\n")
        target.write(f"separator_legs\t{len(labels)}\n")
        target.write(f"separator_operands\t{len(verdicts_by_operand)}\n")
        target.write(f"labels_sha256\t{digest(labels_path)}\n")
        target.write("\n[counts]\n")
        for name, count in sorted(counts.items()):
            target.write(f"{name}\t{count}\n")
        target.write("\n[operand verdicts]\n")
        for operand, verdicts in sorted(verdicts_by_operand.items()):
            target.write(f"{operand}\t{next(iter(verdicts))}\n")

    print(
        f"wrote {args.report}: legs={len(labels)} "
        f"predecessor={counts['verdict.predecessor']} "
        f"wide={counts['verdict.wide']} neither={counts['verdict.neither']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
