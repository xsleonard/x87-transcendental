#!/usr/bin/env python3
"""Replay the complete documented FAMUBUS at the R59 terminal subtraction.

The remaining R59 object is a single carry choice after two chopped terminal
FMULs.  Earlier audits covered scalar exact-width subtraction, the three-bit
low-field equations from US5027308, generic fused terminal CSA layouts, and
retaining a Horner FADD carrier into the terminal multipliers.  They did not
compose the literal FMUL G/R/S representation with the complete h206
FAMUBUS subtractor *at the terminal subtraction itself*.

This audit closes that representation gap.  Each terminal product is encoded
uniformly as either the current scalar chop67 value or Intel's documented
64+G+R+S bus (the final S is the OR of every lower exact product bit).  The
two buses then traverse one of h206's four patent-bounded sticky treatments,
with normalization fixed on or off.  The output is either retained directly
or materialized through the existing odd67 bus action.  All choices are
global datapath programs: there are no operand predicates, thresholds,
identity keys, branch-local programs, or learned truth tables.

Cached all-mode labels are used only after every program has produced its
carry.  No x87 instruction is executed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import h206_p5_fadd_complete as h206
from h1110_carry_gate_mine import allmode_allowed, extract_carry_state
from h1184_upstream_halfway_audit import Value, multiply, quantize, row_value
from h1321_famubus_grs_carrier_audit import famubus_grs


PRODUCT_ENCODINGS = ("scalar_chop67", "famubus_64grs")
OUTPUT_ACTIONS = ("retain", "odd67")


@dataclass(frozen=True)
class Program:
    left_encoding: str
    right_encoding: str
    add_mode: str
    normalize: bool
    output_action: str

    def name(self) -> str:
        normalization = "norm" if self.normalize else "raw"
        return (
            f"L={self.left_encoding},R={self.right_encoding},"
            f"add={self.add_mode},{normalization},out={self.output_action}"
        )


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    if not rows:
        raise RuntimeError(f"empty feature bank: {path}")
    return rows


def to_bus(value: Value) -> h206.Bus:
    return h206.h200.normalized_bus(
        (value.sign, value.significand, value.exponent)
    )


def from_bus(bus: h206.Bus) -> Value:
    sign, significand, exponent = bus.value()
    return Value(sign, exponent, significand)


def encode_product(operation, encoding: str) -> h206.Bus:
    if encoding == "scalar_chop67":
        value = quantize(operation, 67, False)
    elif encoding == "famubus_64grs":
        value = famubus_grs(operation)
    else:
        raise ValueError(encoding)
    return to_bus(value)


def candidate_value(row: dict[str, str], program: Program) -> Value:
    left_operation = multiply(row_value(row, "mul"), row_value(row, "lf"))
    right_operation = multiply(row_value(row, "f4"), row_value(row, "rf"))

    # Assert that the scalar arm is exactly the already reconstructed pair.
    if quantize(left_operation, 67, False) != row_value(row, "left"):
        raise RuntimeError(f"left terminal reconstruction mismatch: {row['op']}")
    if quantize(right_operation, 67, False) != row_value(row, "right"):
        raise RuntimeError(f"right terminal reconstruction mismatch: {row['op']}")

    left = encode_product(left_operation, program.left_encoding)
    right = encode_product(right_operation, program.right_encoding)
    bus, _ = h206.fadd(
        left, right, program.add_mode, normalize=program.normalize
    )
    if program.output_action != "retain":
        bus = h206.materialize(bus, program.output_action)
    return from_bus(bus)


def carry_from_value(row: dict[str, str], value: Value) -> int | None:
    """Project a negative correction bus onto the two exact R59 endpoints."""
    if value.sign != 1 or not value.significand:
        return None
    rscale = int(row["rscale"])
    cut = int(row["k"])
    retained_exponent = rscale + cut
    displacement = value.exponent - retained_exponent
    if displacement >= 0:
        retained = value.significand << displacement
    else:
        retained = value.significand >> -displacement

    s_value = int(row["S"], 16)
    b_value = int(row["B"], 16)
    mask = (1 << cut) - 1
    borrow = int((s_value & mask) < (b_value & mask))
    base = int(row["umag"], 16) >> cut
    carry = retained - base - borrow + 1
    return carry if carry in (0, 1) else None


def programs() -> tuple[Program, ...]:
    return tuple(
        Program(left, right, mode, normalize, output)
        for left in PRODUCT_ENCODINGS
        for right in PRODUCT_ENCODINGS
        for mode in h206.MODES
        for normalize in (False, True)
        for output in OUTPUT_ACTIONS
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("positive_allmode", type=Path)
    parser.add_argument("control_allmode", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    positive = allmode_allowed(args.positive_allmode)
    controls = allmode_allowed(args.control_allmode)
    rows = read_rows(args.features)
    prepared = []
    for row in rows:
        labels = positive if row["label"] == "POS" else controls
        state = extract_carry_state(row, labels[row["op"]])
        if not state[3]:
            continue
        prepared.append((row, state[2], frozenset(state[3])))

    ranking = []
    diagnostics = {}
    for program in programs():
        counts = Counter()
        target_details = []
        for row, incumbent, allowed in prepared:
            target = row["label"] == "POS"
            carry = carry_from_value(row, candidate_value(row, program))
            wrong = carry is None or carry not in allowed
            counts["errors"] += wrong
            counts["target_errors"] += wrong and target
            counts["control_errors"] += wrong and not target
            counts["unrepresented"] += carry is None
            counts["changes"] += carry is not None and carry != incumbent
            counts["predicted_ones"] += carry == 1
            if target:
                target_details.append((
                    row["mode"], row["op"], incumbent,
                    "-" if carry is None else carry,
                    ",".join(map(str, sorted(allowed))), int(not wrong),
                ))
        item = (
            counts["errors"], counts["target_errors"],
            counts["control_errors"], counts["unrepresented"],
            counts["changes"], counts["predicted_ones"], program.name(),
        )
        ranking.append(item)
        diagnostics[item] = target_details

    ranking.sort()
    exact = [item for item in ranking if item[0] == 0]
    best = ranking[0]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write(f"features_sha256\t{digest(args.features)}\n")
        output.write(
            f"positive_allmode_sha256\t{digest(args.positive_allmode)}\n"
        )
        output.write(
            f"control_allmode_sha256\t{digest(args.control_allmode)}\n"
        )
        output.write("hardware_policy\tcached_labels_only_no_x87_execution\n")
        output.write(
            "candidate_policy\tliteral_terminal_FMUL_GRS_to_complete_"
            "FAMUBUS_subtractor\n"
        )
        output.write(f"source_rows\t{len(rows)}\n")
        output.write(f"constraining_rows\t{len(prepared)}\n")
        output.write(
            f"targets\t{sum(row['label'] == 'POS' for row, _, _ in prepared)}\n"
        )
        output.write(f"global_programs\t{len(ranking)}\n")
        output.write(f"exact_programs\t{len(exact)}\n")
        output.write("\n[ranking]\n")
        output.write(
            "errors\ttarget_errors\tcontrol_errors\tunrepresented\tchanges\t"
            "predicted_ones\tprogram\n"
        )
        for item in ranking:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[best target diagnostics]\n")
        output.write(
            "mode\top\tincumbent_carry\tcandidate_carry\tallowed_carry\tmatch\n"
        )
        for detail in diagnostics[best]:
            output.write("\t".join(map(str, detail)) + "\n")

    print(
        f"wrote {args.report}: rows={len(prepared)} programs={len(ranking)} "
        f"exact={len(exact)} best={best}",
        flush=True,
    )


if __name__ == "__main__":
    main()
