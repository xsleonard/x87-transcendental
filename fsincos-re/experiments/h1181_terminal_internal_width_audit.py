#!/usr/bin/env python3
"""Audit fixed internal rounding widths at the R59 terminal subtraction.

Intel US5612909 permits previous rounding history to change a later rounding
decision, with an exact-half result as its motivating case.  Before trying to
decode a history truth table, this cached-label audit tests the necessary
structural premise: at one fixed internal precision, are the anomalous R96
endpoint choices exactly the terminal subtraction's half-way cases?

For each constraining h1163 row, the script reconstructs the exact positive
integer ``S-B`` and classifies the bits discarded by widths 64 through 80.
It reports class enrichment, collisions with controls, and the error count of
the only non-fitted correction rule in this family: invert the incumbent R96
carry choice iff the current subtraction is exactly half way.  No hardware is
executed and no thresholds or operand cases are learned.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from pathlib import Path


WIDTHS = range(64, 81)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def discard_class(value: int, width: int) -> tuple[str, int, int]:
    shift = max(0, value.bit_length() - width)
    if shift == 0:
        return "exact", shift, 0
    remainder = value & ((1 << shift) - 1)
    if remainder == 0:
        name = "exact"
    elif remainder == (1 << shift) - 1:
        name = "all1"
    elif 2 * remainder < (1 << shift):
        name = "low"
    elif 2 * remainder == (1 << shift):
        name = "half"
    else:
        name = "high"
    return name, shift, remainder


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("physical_rows", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    rows = []
    with args.physical_rows.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            if row["physical_status"] != "constraining":
                continue
            s_value = int(row["S"], 16)
            b_value = int(row["B"], 16)
            difference = s_value - b_value
            if difference <= 0 or difference != int(row["umag"], 16):
                raise RuntimeError("terminal reconstruction mismatch: " + row["op"])
            rows.append((row, difference))

    target_count = sum(row["label"] == "POS" for row, _ in rows)
    results = []
    class_counts: dict[int, Counter[tuple[str, str]]] = {}
    target_details = []
    for width in WIDTHS:
        counts: Counter[tuple[str, str]] = Counter()
        half_targets = []
        half_controls = []
        wrong = 0
        wrong_targets = 0
        wrong_controls = 0
        for row, difference in rows:
            name, shift, remainder = discard_class(difference, width)
            kind = "target" if row["label"] == "POS" else "control"
            counts[(name, kind)] += 1
            is_target = kind == "target"
            is_half = name == "half"
            # The incumbent is wrong exactly on POS rows.  Flipping its
            # endpoint at exact-half rows therefore leaves XOR error.
            error = is_target != is_half
            wrong += error
            wrong_targets += error and is_target
            wrong_controls += error and not is_target
            if is_half:
                (half_targets if is_target else half_controls).append(row["op"])
            if is_target:
                target_details.append((width, row["op"], name, shift, remainder))
        class_counts[width] = counts
        results.append((wrong, wrong_targets, wrong_controls,
                        counts[("half", "target")],
                        counts[("half", "control")], width,
                        half_targets, half_controls))

    results.sort()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"physical_rows_sha256\t{digest(args.physical_rows)}\n")
        target.write(f"constraining_rows\t{len(rows)}\n")
        target.write(f"target_rows\t{target_count}\n")
        target.write("\n[half-flip ranking]\n")
        target.write(
            "total_miss\ttarget_miss\tcontrol_miss\thalf_targets\t"
            "half_controls\twidth\n")
        for result in results:
            target.write("\t".join(map(str, result[:6])) + "\n")
        target.write("\n[class census]\n")
        target.write("width\tclass\ttargets\tcontrols\n")
        for width in WIDTHS:
            counts = class_counts[width]
            for name in ("exact", "all1", "low", "half", "high"):
                target.write(
                    f"{width}\t{name}\t{counts[(name, 'target')]}\t"
                    f"{counts[(name, 'control')]}\n")
        target.write("\n[target classes]\n")
        target.write("width\top\tclass\tshift\tremainder_hex\n")
        for width, operand, name, shift, remainder in target_details:
            target.write(
                f"{width}\t{operand}\t{name}\t{shift}\t{remainder:x}\n")
        target.write("\n[best half operands]\n")
        best = results[0]
        target.write(f"width\t{best[5]}\n")
        target.write("half_targets\t" + ",".join(best[6]) + "\n")
        target.write("half_controls\t" + ",".join(best[7]) + "\n")

    best = results[0]
    print(
        f"rows={len(rows)} targets={target_count} best_width={best[5]} "
        f"misses={best[0]} target_miss={best[1]} "
        f"control_miss={best[2]} report={args.report}")


if __name__ == "__main__":
    main()
