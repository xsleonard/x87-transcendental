#!/usr/bin/env python3
"""Audit fixed-width halfway states in the FCOS polynomial schedule.

Intel US5612909's concrete rounding-history examples alter a later result
when the current pre-rounded operation is exactly halfway.  This cached-data
audit reconstructs every named operation in the six-term cosine schedule and
counts exact-half states at every shared width from 60 through 80 bits.  It
tests a mechanism class; hardware labels do not select a width or predicate.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


CONSTANTS = {
    1: (1, -68, (7 << 64) | 0xFFFFFFFFFFFFFFFE),
    2: (0, -71, (5 << 64) | 0x5555555555554277),
    3: (1, -76, (5 << 64) | 0xB05B05B05A18A1BA),
    4: (0, -82, (6 << 64) | 0x80680675B559F2CF),
    5: (1, -88, (4 << 64) | 0x9F93AF61F5349300),
    6: (0, -95, (4 << 64) | 0x7A4F2483514C1AF8),
}
STAGES = (
    "square", "fourth", "negative.mul1", "negative.add1",
    "negative.mul2", "negative.add2", "positive.mul1", "positive.add1",
    "positive.mul2", "positive.add2", "left", "right",
)
ANCHORS = {
    "3ffc be6000000688f849",
    "3ffc fb900000030c1fc9",
    "3ffc ffffff80075216a0",
}


@dataclass(frozen=True)
class Value:
    sign: int
    exponent: int
    significand: int


@dataclass(frozen=True)
class ExactOperation:
    sign: int
    exponent: int
    magnitude: int


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def quantize(operation: ExactOperation, bits: int, nearest: bool) -> Value:
    shift = max(0, operation.magnitude.bit_length() - bits)
    retained = operation.magnitude >> shift
    remainder = (operation.magnitude & ((1 << shift) - 1)
                 if shift else 0)
    if nearest and shift:
        half = 1 << (shift - 1)
        if remainder > half or (remainder == half and retained & 1):
            retained += 1
            if retained == 1 << bits:
                retained >>= 1
                shift += 1
    return Value(operation.sign, operation.exponent + shift, retained)


def multiply(left: Value, right: Value) -> ExactOperation:
    return ExactOperation(
        left.sign ^ right.sign,
        left.exponent + right.exponent,
        left.significand * right.significand,
    )


def add_same_sign(left: Value, right: Value) -> ExactOperation:
    if left.sign != right.sign:
        raise AssertionError("expected same-sign Horner addition")
    exponent = min(left.exponent, right.exponent)
    magnitude = (
        (left.significand << (left.exponent - exponent))
        + (right.significand << (right.exponent - exponent))
    )
    return ExactOperation(left.sign, exponent, magnitude)


def row_value(row: dict[str, str], name: str) -> Value:
    return Value(
        int(row[f"tc_{name}_sign"]), int(row[f"tc_{name}_exp"]),
        int(row[f"tc_{name}_sig"], 16),
    )


def schedule(row: dict[str, str]) -> dict[str, ExactOperation]:
    magnitude = row_value(row, "mag")
    operations: dict[str, ExactOperation] = {}

    operations["square"] = multiply(magnitude, magnitude)
    square = quantize(operations["square"], 67, False)
    operations["fourth"] = multiply(square, square)
    fourth = quantize(operations["fourth"], 67, False)

    operations["negative.mul1"] = multiply(fourth, Value(*CONSTANTS[5]))
    negative = quantize(operations["negative.mul1"], 67, False)
    operations["negative.add1"] = add_same_sign(
        Value(*CONSTANTS[3]), negative)
    negative = quantize(operations["negative.add1"], 64, True)
    operations["negative.mul2"] = multiply(fourth, negative)
    negative = quantize(operations["negative.mul2"], 67, False)
    operations["negative.add2"] = add_same_sign(
        Value(*CONSTANTS[1]), negative)
    negative = quantize(operations["negative.add2"], 64, True)

    operations["positive.mul1"] = multiply(fourth, Value(*CONSTANTS[6]))
    positive = quantize(operations["positive.mul1"], 67, False)
    operations["positive.add1"] = add_same_sign(
        Value(*CONSTANTS[4]), positive)
    positive = quantize(operations["positive.add1"], 64, True)
    operations["positive.mul2"] = multiply(fourth, positive)
    positive = quantize(operations["positive.mul2"], 67, False)
    operations["positive.add2"] = add_same_sign(
        Value(*CONSTANTS[2]), positive)
    positive = quantize(operations["positive.add2"], 64, True)

    operations["left"] = multiply(square, negative)
    operations["right"] = multiply(fourth, positive)

    expected = {
        "mul": square,
        "f4": fourth,
        "lf": negative,
        "rf": positive,
        "left": quantize(operations["left"], 67, False),
        "right": quantize(operations["right"], 67, False),
    }
    for name, value in expected.items():
        if value != row_value(row, name):
            raise AssertionError(f"{name} mismatch for {row['op']}")
    return operations


def cut_state(operation: ExactOperation, bits: int) -> tuple[str, int, int]:
    shift = max(0, operation.magnitude.bit_length() - bits)
    if not shift:
        return "exact", 0, 0
    denominator = 1 << shift
    remainder = operation.magnitude & (denominator - 1)
    doubled = remainder << 1
    state = ("low" if doubled < denominator else
             "half" if doubled == denominator else "high")
    return state, shift, remainder


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    rows_by_operand = {}
    with args.features.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            rows_by_operand.setdefault(row["op"], row)
    missing = sorted(ANCHORS - set(rows_by_operand))
    if missing:
        raise RuntimeError(f"missing anchors: {missing}")

    counts = Counter()
    diagnostics = []
    for operand, row in rows_by_operand.items():
        operations = schedule(row)
        anchor = operand in ANCHORS
        for stage in STAGES:
            for bits in range(60, 81):
                state, shift, remainder = cut_state(operations[stage], bits)
                counts[stage, bits, anchor, state] += 1
                if anchor:
                    denominator = 1 << shift if shift else 1
                    diagnostics.append((
                        operand, stage, bits, state, shift,
                        f"{remainder:x}", f"{denominator:x}",
                    ))

    ranking = []
    for stage in STAGES:
        for bits in range(60, 81):
            anchor_half = counts[stage, bits, True, "half"]
            control_half = counts[stage, bits, False, "half"]
            ranking.append((
                -anchor_half, control_half, stage, bits,
                anchor_half, control_half,
            ))
    ranking.sort()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"features_sha256\t{digest(args.features)}\n")
        target.write(f"unique_operands\t{len(rows_by_operand)}\n")
        target.write(f"anchors\t{len(ANCHORS)}\n")
        target.write("\n[halfway ranking]\n")
        target.write("anchor_half\tcontrol_half\tstage\tbits\n")
        for _, _, stage, bits, anchor_half, control_half in ranking:
            target.write(
                f"{anchor_half}\t{control_half}\t{stage}\t{bits}\n")
        target.write("\n[anchor cut diagnostics]\n")
        target.write("op\tstage\tbits\tstate\tshift\tremainder\tdenominator\n")
        for entry in sorted(diagnostics):
            target.write("\t".join(map(str, entry)) + "\n")

    best = ranking[0]
    print(
        f"wrote {args.report} unique={len(rows_by_operand)} "
        f"best_anchor_half={best[4]}/{len(ANCHORS)} "
        f"controls={best[5]} stage={best[2]} bits={best[3]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
