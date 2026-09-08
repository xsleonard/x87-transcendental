#!/usr/bin/env python3
"""Audit normalized attached precision-difference fields at terminal FSUB.

h1251 preserved each producer tail's physical exponent.  A small attached
field may instead encode the discarded fraction normalized to that producer's
own rounding unit.  This pass quantizes the left and right terminal-FMUL
fractions onto the same fixed N-bit tag grid, combines them with the current
terminal low field, and tests the resulting carry directly and through every
two-input gate with the incumbent selector carry.

Widths, rounding rules, and signs are fixed arithmetic choices; there are no
operand thresholds or identity tests.  Hardware is read only from the cached
collision labels.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path

from h1184_upstream_halfway_audit import cut_state, schedule
from h1251_terminal_precision_difference import ROUNDINGS, divide_round


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def fraction_tag(remainder: int, shift: int, bits: int, mode: str) -> int:
    if not shift:
        return 0
    return divide_round(remainder << bits, 1 << shift, mode)


def gate(mask: int, current: int, tag: int) -> int:
    return (mask >> (2 * current + tag)) & 1


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
    records = []
    for row in rows:
        operations = schedule(row)
        _, left_shift, left_remainder = cut_state(operations["left"], 67)
        _, right_shift, right_remainder = cut_state(operations["right"], 67)
        cut = int(row["k"])
        mask = (1 << cut) - 1
        low_difference = (
            (int(row["S"], 16) & mask) - (int(row["B"], 16) & mask)
        )
        physical = int(row["physical_label"])
        current = physical ^ int(row["label"] == "POS")
        records.append((
            row, cut, low_difference,
            left_shift, left_remainder, right_shift, right_remainder,
            current, physical,
        ))

    ranking = []
    exact = []
    for bits in range(0, 17):
        for mode in ROUNDINGS:
            for left_sign, right_sign in (
                (1, 1), (1, -1), (-1, 1), (-1, -1)
            ):
                tag_carries = []
                for (_, cut, low_difference, left_shift, left_remainder,
                     right_shift, right_remainder, _, _) in records:
                    left_tag = fraction_tag(
                        left_remainder, left_shift, bits, mode
                    )
                    right_tag = fraction_tag(
                        right_remainder, right_shift, bits, mode
                    )
                    numerator = (
                        (low_difference << bits)
                        + ((left_sign * left_tag + right_sign * right_tag)
                           << cut)
                    )
                    tag_carries.append(int(numerator >= 0))

                for gate_mask in range(16):
                    target_miss = control_miss = changes = 0
                    for record, tag_carry in zip(records, tag_carries):
                        row, *_, current, physical = record
                        predicted = gate(gate_mask, current, tag_carry)
                        wrong = predicted != physical
                        target_miss += wrong and row["label"] == "POS"
                        control_miss += wrong and row["label"] != "POS"
                        changes += predicted != current
                    score = (
                        target_miss + control_miss, target_miss,
                        control_miss, changes, bits, mode,
                        left_sign, right_sign, gate_mask,
                    )
                    ranking.append(score)
                    if score[0] == 0:
                        exact.append(score)
    ranking.sort()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"rows_sha256\t{digest(args.rows)}\n")
        target.write(f"rows\t{len(rows)}\n")
        target.write(
            f"targets\t{sum(row['label'] == 'POS' for row, *_ in records)}\n"
        )
        target.write(f"candidates\t{17 * len(ROUNDINGS) * 4 * 16}\n")
        target.write(f"exact_candidates\t{len(exact)}\n")
        target.write("hardware_policy\tcached_labels_only_no_x87_execution\n")
        target.write("\n[ranking]\n")
        target.write(
            "errors\ttarget_miss\tcontrol_miss\tchanges\ttag_bits\t"
            "rounding\tleft_sign\tright_sign\tgate_mask\n"
        )
        for score in ranking[:3000]:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[exact candidates]\n")
        for score in exact:
            target.write("\t".join(map(str, score)) + "\n")

    print(
        f"wrote {args.report} rows={len(rows)} exact={len(exact)} "
        f"best={ranking[0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
