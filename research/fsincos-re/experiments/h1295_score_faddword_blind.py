#!/usr/bin/env python3
"""Score the one-shot hardware verdict on R1290's fresh separators.

The input set is the seven architecturally visible differences frozen by
h1294.  Each (mode, operand) pair is captured exactly once.  This scorer
checks that the capture files contain exactly those pairs, compares the raw
hardware result with both frozen software endpoints, and requires all visible
legs of one operand to imply the same internal FADD response.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path


MODES = ("rn", "rd", "ru", "rz")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def load_capture(directory: Path) -> dict[tuple[str, str], str]:
    captured: dict[tuple[str, str], str] = {}
    for mode in MODES:
        inputs_path = directory / f"{mode}_inputs.txt"
        hardware_path = directory / f"{mode}_hardware.txt"
        operands = [line.strip().lower() for line in inputs_path.read_text().splitlines()]
        values = []
        for line in hardware_path.read_text().splitlines():
            fields = line.lower().split()
            if len(fields) != 3 or fields[0] != "ok":
                raise RuntimeError(f"bad hardware line in {hardware_path}: {line}")
            values.append(f"{fields[1]}:{fields[2]}")
        if len(operands) != len(values):
            raise RuntimeError(
                f"{mode}: {len(operands)} inputs but {len(values)} outputs")
        for operand, value in zip(operands, values):
            key = (mode, operand)
            if key in captured:
                raise RuntimeError(f"duplicate capture pair: {key}")
            captured[key] = value
    return captured


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
    captured = load_capture(args.capture_directory)
    expected = {(row["mode"], row["op"].lower()) for row in changes}
    if set(captured) != expected:
        raise RuntimeError(
            f"capture key mismatch: missing={expected - set(captured)} "
            f"extra={set(captured) - expected}")

    counts = Counter()
    labels = []
    operand_verdicts: dict[str, set[str]] = defaultdict(set)
    for row in changes:
        key = (row["mode"], row["op"].lower())
        hardware = captured[key]
        baseline = row["baseline"].lower()
        candidate = row["candidate"].lower()
        if baseline == candidate:
            raise RuntimeError(f"h1294 row is not a separator: {key}")
        if hardware == baseline:
            verdict = "predecessor"
        elif hardware == candidate:
            verdict = "candidate"
        else:
            verdict = "neither"
        counts[f"verdict.{verdict}"] += 1
        counts[f"mode.{row['mode']}.verdict.{verdict}"] += 1
        operand_verdicts[row["op"].lower()].add(verdict)
        labels.append({
            "mode": row["mode"],
            "op": row["op"].lower(),
            "chain": row["chain"],
            "q": row["q"],
            "word": row["word"],
            "baseline": baseline,
            "candidate": candidate,
            "hardware": hardware,
            "verdict": verdict,
        })

    inconsistent = {
        operand: verdicts for operand, verdicts in operand_verdicts.items()
        if len(verdicts) != 1 or "neither" in verdicts
    }
    if inconsistent:
        raise RuntimeError(f"inconsistent operand verdicts: {inconsistent}")

    columns = (
        "mode", "op", "chain", "q", "word", "baseline", "candidate",
        "hardware", "verdict",
    )
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
        target.write(f"separator_operands\t{len(operand_verdicts)}\n")
        target.write(f"labels_sha256\t{digest(labels_path)}\n")
        target.write("\n[counts]\n")
        for name, value in sorted(counts.items()):
            target.write(f"{name}\t{value}\n")
        target.write("\n[operand_verdicts]\n")
        for operand, verdicts in sorted(operand_verdicts.items()):
            target.write(f"{operand}\t{next(iter(verdicts))}\n")

    print(
        f"wrote {args.report}: legs={len(changes)} "
        f"candidate={counts['verdict.candidate']} "
        f"predecessor={counts['verdict.predecessor']} "
        f"neither={counts['verdict.neither']}")


if __name__ == "__main__":
    main()
