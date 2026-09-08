#!/usr/bin/env python3
"""Test a retained FAMUBUS producer across the terminal FMUL boundary.

The current R59 implementation materializes both final Horner sums as RN64
values before multiplying them by the 67-bit square/fourth-power carriers.
The documented P5 datapath admits a different fixed representation: retain
the FADD result on FAMUBUS, route that 67-bit carrier to FMUL X, and route a
64-bit materialization of the power to FMUL Y.  This is an architectural
route hypothesis, not an operand classifier.

For completeness the audit crosses the bounded documented choices at that
boundary: scalar versus G/R/S input to the final Horner FADD, the four
FAMUBUS sticky interpretations, normalization, FADD materialization, FMUL
port orientation, Y-port materialization, and final 67-bit product mode.
Every program is uniform over an entire branch bank.  Cached all-mode labels
are used only for scoring; this script never executes an x87 instruction.
"""

from __future__ import annotations

import argparse
import csv
import functools
import hashlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import h200_p5_fadd_bitvector as h200
import h206_p5_fadd_complete as h206
import h110_fsin_standalone as h110
from h1110_carry_gate_mine import allmode_allowed
from h1184_upstream_halfway_audit import (
    CONSTANTS,
    ExactOperation,
    Value,
    multiply,
    quantize,
    row_value,
    schedule,
)
from h1321_famubus_grs_carrier_audit import famubus_grs


INPUT_ENCODINGS = ("scalar67", "grs67")
OUTPUT_ACTIONS = ("retain", "rn64", "chop64", "away64", "odd64")
ROUTES = ("power_x_factor_y", "factor_x_power_y")
Y_MODES = ("rn64", "chop64", "away64", "odd64")
PRODUCT_MODES = ("chop67", "rn67", "away67", "odd67")


@dataclass(frozen=True)
class Program:
    input_encoding: str
    add_mode: str
    normalize: bool
    output_action: str
    route: str
    y_mode: str
    product_mode: str

    def name(self) -> str:
        return "/".join((
            self.input_encoding,
            self.add_mode,
            "norm" if self.normalize else "raw",
            self.output_action,
            self.route,
            self.y_mode,
            self.product_mode,
        ))


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        return list(csv.DictReader(source, delimiter="\t"))


def to_bus(value: Value) -> h200.Bus:
    return h200.normalized_bus(
        (value.sign, value.significand, value.exponent))


def from_bus(bus: h200.Bus) -> Value:
    sign, significand, exponent = bus.value()
    return Value(sign, exponent, significand)


def product_input(operation: ExactOperation, encoding: str) -> Value:
    if encoding == "scalar67":
        return quantize(operation, 67, False)
    if encoding == "grs67":
        return famubus_grs(operation)
    raise ValueError(encoding)


@functools.lru_cache(maxsize=None)
def factor_bus_cached(
        operation: ExactOperation, constant_index: int,
        input_encoding: str, add_mode: str, normalize: bool,
        output_action: str) -> h200.Bus:
    source = to_bus(product_input(operation, input_encoding))
    constant = to_bus(Value(*CONSTANTS[constant_index]))
    result, _ = h206.fadd(
        constant, source, add_mode, normalize=normalize)
    return h206.materialize(result, output_action)


def factor_bus(
        operation: ExactOperation, constant_index: int,
        program: Program) -> h200.Bus:
    return factor_bus_cached(
        operation, constant_index, program.input_encoding, program.add_mode,
        program.normalize, program.output_action)


def mode_quant(bits: int, name: str):
    suffix = str(bits)
    if not name.endswith(suffix):
        raise ValueError((bits, name))
    return name[:-len(suffix)]


def as_fp(value: Value):
    return value.sign, value.significand, value.exponent


def from_fp(value) -> Value:
    sign, significand, exponent = value
    return Value(sign, exponent, significand)


@functools.lru_cache(maxsize=None)
def terminal_product_cached(
        power: Value, factor: h200.Bus, route: str,
        y_mode: str, product_mode: str) -> Value:
    factor_value = from_bus(factor)
    if route == "power_x_factor_y":
        x = power
        y = from_fp(h110.quantize(
            as_fp(factor_value), h110.Quant(64, mode_quant(64, y_mode))))
    elif route == "factor_x_power_y":
        x = factor_value
        y = from_fp(h110.quantize(
            as_fp(power), h110.Quant(64, mode_quant(64, y_mode))))
    else:
        raise ValueError(route)
    operation = multiply(x, y)
    return from_fp(h110.quantize(
        (operation.sign, operation.magnitude, operation.exponent),
        h110.Quant(67, mode_quant(67, product_mode))))


def terminal_product(
        power: Value, factor: h200.Bus, program: Program) -> Value:
    return terminal_product_cached(
        power, factor, program.route, program.y_mode, program.product_mode)


def retained_delta(
        row: dict[str, str], left: Value, right: Value) -> int | None:
    if left.sign != 1 or right.sign != 0:
        return None
    payload = int(row["payload"])
    payload_exponent = left.exponent - 8
    scale = min(
        left.exponent, right.exponent,
        payload_exponent if payload else left.exponent)
    magnitude = (
        (left.significand << (left.exponent - scale))
        + (payload << (payload_exponent - scale) if payload else 0)
        - (right.significand << (right.exponent - scale))
    )
    if magnitude <= 0:
        return None
    candidate = quantize(ExactOperation(1, scale, magnitude), 67, False)
    retained_exponent = int(row["rscale"]) + int(row["k"])
    common = min(candidate.exponent, retained_exponent)
    candidate_integer = candidate.significand << (candidate.exponent - common)
    baseline_integer = (
        (int(row["umag"], 16) >> int(row["k"]))
        << (retained_exponent - common)
    )
    unit = 1 << (retained_exponent - common)
    difference = candidate_integer - baseline_integer
    if difference % unit:
        return None
    return difference // unit


def row_delta(
        row: dict[str, str], operations: dict[str, ExactOperation],
        program: Program) -> int | None:
    negative = factor_bus(
        operations["negative.mul2"], 1, program)
    positive = factor_bus(
        operations["positive.mul2"], 2, program)
    left = terminal_product(row_value(row, "mul"), negative, program)
    right = terminal_product(row_value(row, "f4"), positive, program)
    return retained_delta(row, left, right)


def programs():
    for input_encoding in INPUT_ENCODINGS:
        for add_mode in h206.MODES:
            for normalize in (False, True):
                for output_action in OUTPUT_ACTIONS:
                    for route in ROUTES:
                        for y_mode in Y_MODES:
                            for product_mode in PRODUCT_MODES:
                                yield Program(
                                    input_encoding, add_mode, normalize,
                                    output_action, route, y_mode,
                                    product_mode)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("positive_allmode", type=Path)
    parser.add_argument("control_allmode", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit("refusing to overwrite " + str(args.report))

    positive = allmode_allowed(args.positive_allmode)
    controls = allmode_allowed(args.control_allmode)
    rows = read_rows(args.features)
    prepared = [(row, schedule(row)) for row in rows]
    allowed = [
        (positive if row["label"] == "POS" else controls)[row["op"]]
        for row in rows
    ]
    positives = [row["label"] == "POS" for row in rows]

    ranking = []
    best_diagnostics = None
    for index, program in enumerate(programs(), 1):
        counts = Counter()
        diagnostics = []
        for (row, operations), valid, target in zip(
                prepared, allowed, positives):
            try:
                delta = row_delta(row, operations, program)
            except ValueError:
                delta = None
            wrong = delta not in valid
            counts["errors"] += wrong
            counts["target_errors"] += wrong and target
            counts["control_errors"] += wrong and not target
            counts["invalid"] += delta is None
            counts[f"delta.{delta}"] += 1
            if target:
                diagnostics.append((row["op"], sorted(valid), delta,
                                    int(not wrong)))
        item = (
            counts["errors"], counts["target_errors"],
            counts["control_errors"], counts["invalid"],
            counts["delta.-2"], counts["delta.-1"], counts["delta.0"],
            counts["delta.1"], counts["delta.2"], program.name(),
        )
        ranking.append(item)
        if best_diagnostics is None or item < best_diagnostics[0]:
            best_diagnostics = (item, diagnostics)
        if index % 256 == 0:
            print("programs", index, flush=True)
    ranking.sort()
    if best_diagnostics is None:
        raise AssertionError("empty program set")

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        for name, path in (
            ("features", args.features),
            ("positive_allmode", args.positive_allmode),
            ("control_allmode", args.control_allmode),
        ):
            output.write(f"{name}_sha256\t{digest(path)}\n")
        output.write("hardware_policy\tcached_labels_only_no_x87_execution\n")
        output.write(
            "candidate_policy\tfixed_FAMUBUS_to_terminal_FMUL_program\n")
        output.write(f"rows\t{len(rows)}\n")
        output.write(f"targets\t{sum(positives)}\n")
        output.write(f"programs\t{len(ranking)}\n")
        output.write(
            f"exact_programs\t{sum(item[0] == 0 for item in ranking)}\n")
        output.write("\n[ranking]\n")
        output.write(
            "errors\ttarget_errors\tcontrol_errors\tinvalid\t"
            "delta_minus2\tdelta_minus1\tdelta_zero\tdelta_plus1\t"
            "delta_plus2\tprogram\n")
        for item in ranking[:1024]:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[best target diagnostics]\n")
        output.write("op\tallowed_delta\tpredicted_delta\tmatch\n")
        for item in best_diagnostics[1]:
            output.write("\t".join(map(str, item)) + "\n")

    print(
        "wrote", args.report, "rows", len(rows), "programs", len(ranking),
        "exact", sum(item[0] == 0 for item in ranking),
        "best", ranking[0][:9], flush=True)


if __name__ == "__main__":
    main()
