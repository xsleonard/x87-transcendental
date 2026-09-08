#!/usr/bin/env python3
"""Test patent-bounded rounding-history tags at the terminal FSUB.

US5612909 names a finite metadata vocabulary: whether rounding occurred,
rounding direction/type, below/equal/above-half discarded data, and the
all-discarded-ones case.  It also says the control is operation dependent.
This pass reconstructs those tags at each actual schedule precision and
tests every two-input Boolean control function, with immediate left/right
producer pairs reported separately.

No arbitrary tail prefix, operand interval, or learned numeric threshold is
admitted.  Hardware truth comes only from cached labels.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import defaultdict
from pathlib import Path

from h1184_upstream_halfway_audit import STAGES, schedule


PRECISION = {
    "square": 67,
    "fourth": 67,
    "negative.mul1": 67,
    "negative.add1": 64,
    "negative.mul2": 67,
    "negative.add2": 64,
    "positive.mul1": 67,
    "positive.add1": 64,
    "positive.mul2": 67,
    "positive.add2": 64,
    "left": 67,
    "right": 67,
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def operation_tags(operation, bits: int) -> dict[str, int]:
    shift = max(0, operation.magnitude.bit_length() - bits)
    retained = operation.magnitude >> shift
    remainder = operation.magnitude & ((1 << shift) - 1) if shift else 0
    half = 1 << (shift - 1) if shift else 0
    round_bit = int(bool(shift and remainder & half))
    sticky = int(bool(shift > 1 and remainder & (half - 1)))
    inexact = int(bool(remainder))
    increment_nearest = int(bool(
        shift and (remainder > half or (remainder == half and retained & 1))
    ))
    # Direction is numeric, not magnitude-relative.
    numeric_up_chop = inexact & int(bool(operation.sign))
    numeric_down_chop = inexact & int(not operation.sign)
    return {
        "inexact": inexact,
        "exact": 1 ^ inexact,
        "round_bit": round_bit,
        "sticky": sticky,
        "round_and_sticky": round_bit & sticky,
        "round_without_sticky": round_bit & (1 ^ sticky),
        "below_half": int(bool(shift and remainder < half)),
        "equal_half": int(bool(shift and remainder == half)),
        "above_half": int(bool(shift and remainder > half)),
        "all_discarded_ones": int(bool(
            shift and remainder == (1 << shift) - 1
        )),
        "nearest_increment": increment_nearest,
        "nearest_no_increment": inexact & (1 ^ increment_nearest),
        "numeric_up_chop": numeric_up_chop,
        "numeric_down_chop": numeric_down_chop,
        "sign": int(operation.sign),
        "retained_lsb": retained & 1,
        "shift_parity": shift & 1,
    }


def row_features(row: dict[str, str]) -> dict[str, int]:
    operations = schedule(row)
    values: dict[str, int] = {}
    for stage in STAGES:
        tags = operation_tags(operations[stage], PRECISION[stage])
        for name, value in tags.items():
            values[f"{stage}.{name}"] = value

    # Current terminal subtraction tags at its reconstructed 67-bit cut.
    magnitude = int(row["umag"], 16)
    cut = int(row["k"])
    terminal = type("Terminal", (), {
        "magnitude": magnitude,
        "sign": 1,
    })()
    for name, value in operation_tags(terminal, 67).items():
        values[f"terminal.{name}"] = value
    return values


def gate_output(mask: int, left: int, right: int) -> int:
    return (mask >> (2 * left + right)) & 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rows", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    with args.rows.open(newline="") as source:
        rows = [
            row for row in csv.DictReader(source, delimiter="\t")
            if row["physical_status"] == "constraining"
        ]
    feature_rows = [row_features(row) for row in rows]
    names = sorted(feature_rows[0])
    columns = {
        name: [features[name] for features in feature_rows]
        for name in names
    }
    truth = [
        int(row["physical_label"]) ^ ((int(row["low3"]) >> 1) & 1)
        for row in rows
    ]

    singles = []
    for name in names:
        for invert in (0, 1):
            predicted = [value ^ invert for value in columns[name]]
            errors = sum(a != b for a, b in zip(predicted, truth))
            singles.append((errors, invert, name))
    singles.sort()

    pattern_names: dict[tuple[int, ...], list[str]] = defaultdict(list)
    for name, column in columns.items():
        pattern_names[tuple(column)].append(name)
    patterns = sorted(pattern_names)
    pairs = []
    exact = []
    immediate_exact = []
    for left_index, left_pattern in enumerate(patterns):
        left_name = min(pattern_names[left_pattern], key=lambda n: (len(n), n))
        for right_pattern in patterns[left_index:]:
            right_name = min(
                pattern_names[right_pattern], key=lambda n: (len(n), n)
            )
            for mask in range(16):
                predicted = [
                    gate_output(mask, left, right)
                    for left, right in zip(left_pattern, right_pattern)
                ]
                errors = sum(a != b for a, b in zip(predicted, truth))
                exception_miss = sum(
                    wanted and not got for wanted, got in zip(truth, predicted)
                )
                control_fire = sum(
                    not wanted and got for wanted, got in zip(truth, predicted)
                )
                score = (
                    errors, exception_miss, control_fire, mask,
                    left_name, right_name,
                )
                pairs.append(score)
                if errors == 0:
                    exact.append(score)
                    stages = {left_name.split(".", 1)[0],
                              right_name.split(".", 1)[0]}
                    if stages <= {"left", "right"}:
                        immediate_exact.append(score)
    pairs.sort()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"rows_sha256\t{digest(args.rows)}\n")
        target.write(f"rows\t{len(rows)}\n")
        target.write(f"exception_carry_ones\t{sum(truth)}\n")
        target.write(f"tag_features\t{len(names)}\n")
        target.write(f"unique_patterns\t{len(patterns)}\n")
        target.write(f"exact_two_tag_gates\t{len(exact)}\n")
        target.write(
            f"exact_immediate_left_right_gates\t{len(immediate_exact)}\n"
        )
        target.write("hardware_policy\tcached_labels_only_no_x87_execution\n")
        target.write("\n[single-tag ranking]\n")
        target.write("errors\tinvert\tfeature\n")
        for score in singles:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[two-tag gate ranking]\n")
        target.write(
            "errors\texception_miss\tcontrol_fire\tgate_mask\tleft\tright\n"
        )
        for score in pairs[:3000]:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[exact gates]\n")
        for score in exact:
            target.write("\t".join(map(str, score)) + "\n")

    print(
        f"wrote {args.report} rows={len(rows)} tags={len(names)} "
        f"patterns={len(patterns)} exact={len(exact)} "
        f"immediate_exact={len(immediate_exact)} best={pairs[0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
