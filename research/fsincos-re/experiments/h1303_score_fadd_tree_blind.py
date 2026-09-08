#!/usr/bin/env python3
"""Score one-shot hardware labels for the h1303 tree-wire bank."""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from pathlib import Path


MODES = ("rn", "rd", "ru", "rz")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def load_captures(directory: Path) -> dict[tuple[str, str], str]:
    result = {}
    for mode in MODES:
        operands = [line.strip().lower() for line in
                    (directory / f"{mode}_inputs.txt").read_text().splitlines()]
        values = []
        for line in (directory / f"{mode}_hardware.txt").read_text().splitlines():
            fields = line.lower().split()
            if len(fields) != 3 or fields[0] != "ok":
                raise RuntimeError(f"bad hardware line: {line}")
            values.append(f"{fields[1]}:{fields[2]}")
        if len(operands) != len(values):
            raise RuntimeError(f"{mode}: input/output count mismatch")
        for operand, value in zip(operands, values):
            key = (mode, operand)
            if key in result:
                raise RuntimeError(f"duplicate capture key {key}")
            result[key] = value
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("changes", type=Path)
    parser.add_argument("capture_directory", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    labels_path = args.report.with_name(args.report.stem + "_labels.tsv")
    for path in (args.report, labels_path):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")

    with args.changes.open(newline="") as source:
        changes = list(csv.DictReader(source, delimiter="\t"))
    captures = load_captures(args.capture_directory)
    expected = {(row["mode"], row["op"].lower()) for row in changes}
    if set(captures) != expected:
        raise RuntimeError(
            f"capture mismatch missing={expected - set(captures)} "
            f"extra={set(captures) - expected}")

    counts = Counter()
    wire_errors = Counter()
    labels = []
    for row in changes:
        key = (row["mode"], row["op"].lower())
        hardware = captures[key]
        baseline = row["baseline"].lower()
        candidate = row["candidate"].lower()
        if hardware == baseline:
            verdict = "predecessor"
            wanted = 0
        elif hardware == candidate:
            verdict = "candidate"
            wanted = 1
        else:
            verdict = "neither"
            wanted = -1
        counts[f"verdict.{verdict}"] += 1
        mask = int(row["tree_mask"], 16)
        for wire in range(10):
            prediction = (mask >> wire) & 1
            wire_errors[wire] += prediction != wanted
        labels.append({**row, "hardware": hardware, "verdict": verdict})

    if counts["verdict.neither"]:
        raise RuntimeError("hardware produced an unmodeled third endpoint")
    surviving = [wire for wire in range(10) if wire_errors[wire] == 0]

    columns = tuple(changes[0]) + ("hardware", "verdict")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with labels_path.open("x", newline="") as target:
        writer = csv.DictWriter(target, columns, delimiter="\t")
        writer.writeheader()
        writer.writerows(labels)
    with args.report.open("x") as target:
        target.write(f"changes_sha256\t{digest(args.changes)}\n")
        for mode in MODES:
            target.write(
                f"inputs_sha256.{mode}\t"
                f"{digest(args.capture_directory / f'{mode}_inputs.txt')}\n")
            target.write(
                f"hardware_sha256.{mode}\t"
                f"{digest(args.capture_directory / f'{mode}_hardware.txt')}\n")
        target.write("hardware_policy\tone_capture_per_mode_operand_pair\n")
        target.write("capture_processor\tIntel_Core_i7-6700\n")
        target.write(f"separator_legs\t{len(changes)}\n")
        target.write(
            f"separator_operands\t{len(set(row['op'] for row in changes))}\n")
        target.write(f"surviving_tree_wires\t{len(surviving)}\n")
        target.write(f"labels_sha256\t{digest(labels_path)}\n")
        target.write("\n[counts]\n")
        for name, value in sorted(counts.items()):
            target.write(f"{name}\t{value}\n")
        target.write("\n[wire errors]\n")
        for wire in range(10):
            target.write(f"wire{wire}\t{wire_errors[wire]}\n")

    print(
        f"wrote {args.report}: legs={len(changes)} "
        f"candidate={counts['verdict.candidate']} "
        f"predecessor={counts['verdict.predecessor']} "
        f"surviving_wires={len(surviving)}", flush=True)


if __name__ == "__main__":
    main()
