#!/usr/bin/env python3
"""Score the frozen X67/Y64 replacement bank against one-shot hardware."""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from pathlib import Path


MODES = ("rn", "rd", "ru")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def load_capture(directory: Path) -> dict[tuple[str, str], str]:
    result: dict[tuple[str, str], str] = {}
    for mode in MODES:
        inputs = (directory / f"{mode}_inputs.txt").read_text().splitlines()
        outputs = (directory / f"{mode}_hardware.txt").read_text().splitlines()
        if len(inputs) != len(outputs):
            raise RuntimeError(
                f"capture length mismatch for {mode}: {len(inputs)} != {len(outputs)}"
            )
        for operand, line in zip(inputs, outputs):
            fields = line.lower().split()
            if len(fields) < 3 or fields[0] != "ok":
                raise RuntimeError(f"bad capture line for {mode}: {line}")
            result[mode, " ".join(operand.lower().split())] = (
                f"{fields[1]}:{fields[2]}"
            )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("changes", type=Path)
    parser.add_argument("capture_directory", type=Path)
    parser.add_argument("freeze_report", type=Path)
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
            f"capture mismatch: missing={expected-set(captured)} "
            f"extra={set(captured)-expected}"
        )

    counts = Counter()
    labels = []
    for row in changes:
        key = row["mode"], row["op"].lower()
        hardware = captured[key]
        baseline = row["baseline"].lower()
        candidate = row["candidate"].lower()
        if baseline == candidate:
            raise RuntimeError(f"non-separator in changes: {key}")
        if hardware == candidate:
            verdict = "candidate"
        elif hardware == baseline:
            verdict = "baseline"
        else:
            verdict = "neither"
        counts[f"actual.{verdict}"] += 1
        counts[f"mode.{row['mode']}.actual.{verdict}"] += 1
        counts[f"q.{row['q']}.cut.{row['cut']}.actual.{verdict}"] += 1
        counts[f"square_low3.{row['square_low3']}.actual.{verdict}"] += 1
        scored = dict(row)
        scored.update({"hardware": hardware, "actual_verdict": verdict})
        labels.append(scored)

    if counts["actual.neither"]:
        raise RuntimeError(
            f"hardware selected neither frozen endpoint on "
            f"{counts['actual.neither']} legs"
        )

    with labels_path.open("x", newline="") as target:
        writer = csv.DictWriter(target, tuple(labels[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(labels)
    with args.report.open("x") as output:
        output.write(f"changes_sha256\t{digest(args.changes)}\n")
        output.write(f"freeze_report_sha256\t{digest(args.freeze_report)}\n")
        for mode in MODES:
            output.write(
                f"inputs_sha256.{mode}\t"
                f"{digest(args.capture_directory / f'{mode}_inputs.txt')}\n"
            )
            output.write(
                f"hardware_sha256.{mode}\t"
                f"{digest(args.capture_directory / f'{mode}_hardware.txt')}\n"
            )
        output.write("hardware_policy\tone_capture_per_mode_operand_pair\n")
        output.write("capture_processor\tIntel_Core_i7-6700\n")
        output.write(f"separator_legs\t{len(labels)}\n")
        output.write(f"separator_operands\t{len({row['op'] for row in labels})}\n")
        output.write(f"labels_sha256\t{digest(labels_path)}\n")
        output.write("\n[counts]\n")
        for name, count in sorted(counts.items()):
            output.write(f"{name}\t{count}\n")
        output.write("\n[noncandidate]\n")
        for row in labels:
            if row["actual_verdict"] != "candidate":
                output.write(
                    f"{row['mode']}\t{row['op']}\tq={row['q']}\t"
                    f"cut={row['cut']}\tsquare_low3={row['square_low3']}\t"
                    f"actual={row['actual_verdict']}\n"
                )

    print(
        f"wrote {args.report}: legs={len(labels)} "
        f"candidate={counts['actual.candidate']} "
        f"baseline={counts['actual.baseline']} "
        f"neither={counts['actual.neither']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
