#!/usr/bin/env python3
"""Test Intel's documented subtraction-rounding carry automaton at R59.

US5027308 describes a three-bit low-field subtraction.  The minuend supplies
``ml00`` and the subtrahend supplies ``sl,sr,ss``; ``ss`` is the OR-reduced
sticky field.  A two's-complement carry ``c`` and a rounding carry ``b`` can
never both be set, so their OR is fed to the high adder.  The R59 residual is
also exactly a binary high-adder carry choice.  This audit tests whether the
documented automaton, at any of its three documented normalization
alignments, is that missing closed form.

All predictions are fixed equations over cached internal operands.  Hardware
labels are read only after the predictions are formed and are used solely for
scoring; no hardware instruction is executed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def sticky(value: int, below: int) -> int:
    if below <= 0:
        return 0
    return int(bool(value & ((1 << below) - 1)))


def rounding_increment(lsb: int, round_bit: int, sticky_bit: int,
                       mode: str, negative: bool) -> int:
    inexact = round_bit | sticky_bit
    if mode == "rn":
        return round_bit & (sticky_bit | lsb)
    if mode == "ru":
        return inexact & int(not negative)
    if mode == "rd":
        return inexact & int(negative)
    if mode == "rz":
        return 0
    raise ValueError(mode)


def documented_carry(minuend: int, subtrahend: int, lsb_position: int,
                     mode: str, negative: bool, sticky_kind: str) -> int:
    """Return US5027308's high-adder carry b OR c."""
    if lsb_position < 1:
        raise ValueError("low-field LSB position must leave a round bit")
    ml = (minuend >> lsb_position) & 1
    sl = (subtrahend >> lsb_position) & 1
    sr = (subtrahend >> (lsb_position - 1)) & 1
    if sticky_kind == "or":
        ss = sticky(subtrahend, lsb_position - 1)
    elif sticky_kind == "bit":
        ss = ((subtrahend >> (lsb_position - 2)) & 1
              if lsb_position >= 2 else 0)
    elif sticky_kind == "zero":
        ss = 0
    elif sticky_kind == "one":
        ss = 1
    else:
        raise ValueError(sticky_kind)

    minuend_low = ml << 2
    subtrahend_low = (sl << 2) | (sr << 1) | ss
    raw = minuend_low - subtrahend_low
    c = int(raw >= 0)
    low = raw & 7
    lprime, rprime, sprime = (low >> 2) & 1, (low >> 1) & 1, low & 1
    increment = rounding_increment(
        lprime, rprime, sprime, mode, negative)
    b = int(low + (increment << 2) >= 8)
    if b and c:
        raise AssertionError("documented b and c exclusion violated")
    return b | c


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("physical_rows", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    with args.physical_rows.open(newline="") as source:
        rows = [row for row in csv.DictReader(source, delimiter="\t")
                if row["physical_status"] == "constraining"]

    predictions = {}
    configurations = []
    for role in ("S-B", "B-S"):
        for offset in (-1, 0, 1):
            for sticky_kind in ("or", "bit", "zero", "one"):
                for rounding_source in ("architectural", "rn", "ru", "rd", "rz"):
                    for negative in (False, True):
                        name = (role, offset, sticky_kind,
                                rounding_source, int(negative))
                        configurations.append(name)
                        values = []
                        for row in rows:
                            first = int(row["S"], 16)
                            second = int(row["B"], 16)
                            if role == "B-S":
                                first, second = second, first
                            mode = (row["mode"] if rounding_source == "architectural"
                                    else rounding_source)
                            # Carry into bit k corresponds to an L/R/S group
                            # whose retained L bit is k-1.  Offsets cover the
                            # patent's no-shift, left-shift, and right-shift
                            # speculative paths.
                            position = int(row["k"]) - 1 + offset
                            values.append(documented_carry(
                                first, second, position,
                                mode, negative, sticky_kind))
                        predictions[name] = values

    truth = []
    targets = []
    for row in rows:
        physical = int(row["physical_label"])
        # h1163's displacement label maps to the exact binary carry this way.
        truth.append(physical if int(row["theta"]) < 0 else 1 - physical)
        targets.append(row["label"] == "POS")

    ranking = []
    for name in configurations:
        values = predictions[name]
        target_miss = sum(
            predicted != expected and target
            for predicted, expected, target in zip(values, truth, targets))
        control_miss = sum(
            predicted != expected and not target
            for predicted, expected, target in zip(values, truth, targets))
        ranking.append((target_miss + control_miss,
                        target_miss, control_miss, name))
    ranking.sort()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target_file:
        target_file.write(
            f"physical_rows_sha256\t{digest(args.physical_rows)}\n")
        target_file.write(f"rows\t{len(rows)}\n")
        target_file.write(f"targets\t{sum(targets)}\n")
        target_file.write(f"configurations\t{len(configurations)}\n")
        target_file.write("\n[ranking]\n")
        target_file.write(
            "total_miss\ttarget_miss\tcontrol_miss\trole\toffset\t"
            "sticky\trounding_source\tnegative\n")
        for total, target_miss, control_miss, name in ranking:
            target_file.write(
                f"{total}\t{target_miss}\t{control_miss}\t"
                + "\t".join(map(str, name)) + "\n")

        target_file.write("\n[best target diagnostics]\n")
        target_file.write("mode\top\ttruth\tprediction\tmatch\n")
        best_values = predictions[ranking[0][3]]
        for row, expected, predicted, is_target in zip(
                rows, truth, best_values, targets):
            if is_target:
                target_file.write(
                    f"{row['mode']}\t{row['op']}\t{expected}\t{predicted}\t"
                    f"{int(expected == predicted)}\n")

    print(
        f"wrote {args.report} rows={len(rows)} targets={sum(targets)} "
        f"best={ranking[0]}", flush=True)


if __name__ == "__main__":
    main()
