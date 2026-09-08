#!/usr/bin/env python3
"""Compose literal FMUL G/R/S, FAMUBUS, and attached RN history.

h1348 composed the multiplier's 64+G+R+S carrier with the FAMUBUS adder but
used ordinary ties-to-even when the retained bus was materialized at 64 bits.
h1349 implemented US5612909's dependency-local history override, but on a
scalar add rather than on the retained FAMUBUS carrier.  This audit closes
that specific gap.

Every multiplier and adder result carries its immediate signed-numeric
rounding direction.  At either fixed add site, a microcode R-enable may use
the source histories only when the retained FAMUBUS word is exactly halfway
at 64 bits.  Product routing masks, the four documented sticky alternatives,
normalization, and the two add-site enable bits are global program choices;
there are no operand predicates, learned thresholds, or exception tables.

Hardware labels are immutable one-shot inputs.  This program executes no x87
instruction.  An exact candidate would still require a disjoint challenge
and independent evidence for its selected datapath controls.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import h200_p5_fadd_bitvector as h200
import h206_p5_fadd_complete as h206
from h1184_upstream_halfway_audit import (
    CONSTANTS,
    ExactOperation,
    Value,
    add_same_sign,
    multiply,
    row_value,
    schedule,
)
from h1191_grs_history_isomorphism import (
    compare_values,
    magnitude_delta,
    quantize_mode,
)
from h1210_stagea_residual_reframe import parse_dump, run
from h1321_famubus_grs_carrier_audit import famubus_grs


PRODUCT_STAGES = ("square", "fourth", "negative.mul1", "negative.mul2")


@dataclass(frozen=True)
class HistoryValue:
    value: Value
    direction: int


@dataclass(frozen=True)
class AddProgram:
    mode: str
    normalize: bool

    def name(self) -> str:
        return f"{self.mode}.{'norm' if self.normalize else 'raw'}"


ADD_PROGRAMS = tuple(
    AddProgram(mode, normalize)
    for mode in h206.MODES
    for normalize in (False, True)
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def load_direct(path: Path, labels: dict[str, int]) -> None:
    """Load either the older ``verdict`` or h1352 ``actual_verdict`` schema."""
    with path.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            verdict = row.get("verdict", row.get("actual_verdict"))
            if verdict not in ("wide", "predecessor"):
                raise ValueError(f"bad direct verdict in {path}: {verdict!r}")
            label = int(verdict == "wide")
            previous = labels.setdefault(row["op"], label)
            if previous != label:
                raise RuntimeError(f"inconsistent direct label for {row['op']}")


def to_bus(value: Value) -> h200.Bus:
    return h200.normalized_bus((value.sign, value.significand, value.exponent))


def from_bus(bus: h200.Bus) -> Value:
    sign, significand, exponent = bus.value()
    return Value(sign, exponent, significand)


def direction(operation: ExactOperation, stored: Value) -> int:
    exact = Value(operation.sign, operation.exponent, operation.magnitude)
    return compare_values(stored, exact)


def exact_half(operation: ExactOperation, bits: int) -> bool:
    shift = max(0, operation.magnitude.bit_length() - bits)
    if not shift:
        return False
    remainder = operation.magnitude & ((1 << shift) - 1)
    return remainder == 1 << (shift - 1)


def choose_direction(
    operation: ExactOperation, bits: int, wanted_direction: int
) -> Value:
    candidates = (
        quantize_mode(operation, bits, "chop"),
        quantize_mode(operation, bits, "away"),
    )
    matches = [
        candidate
        for candidate in candidates
        if direction(operation, candidate) == wanted_direction
    ]
    if len(matches) != 1:
        raise AssertionError(
            f"cannot choose direction {wanted_direction}: {matches}"
        )
    return matches[0]


def product_value(operation: ExactOperation, literal_grs: bool) -> HistoryValue:
    stored = (
        famubus_grs(operation)
        if literal_grs
        else quantize_mode(operation, 67, "chop")
    )
    return HistoryValue(stored, direction(operation, stored))


def exact_source(value: Value) -> HistoryValue:
    return HistoryValue(value, 0)


def fadd_value(
    left: HistoryValue,
    right: HistoryValue,
    program: AddProgram,
    history_enabled: bool,
    output_scope: str,
) -> tuple[HistoryValue, bool, bool]:
    bus, _ = h206.fadd(
        to_bus(left.value),
        to_bus(right.value),
        program.mode,
        normalize=program.normalize,
    )
    carrier = from_bus(bus)
    carrier_operation = ExactOperation(
        carrier.sign, carrier.exponent, carrier.significand
    )
    stored = from_bus(h206.materialize(bus, "rn64"))
    halfway = exact_half(carrier_operation, 64)
    active = {value for value in (left.direction, right.direction) if value}
    overridden = history_enabled and halfway and len(active) == 1
    if overridden:
        stored = choose_direction(carrier_operation, 64, -next(iter(active)))

    if output_scope == "bus":
        output_operation = carrier_operation
    elif output_scope == "sum":
        output_operation = add_same_sign(left.value, right.value)
    else:
        raise ValueError(output_scope)
    return HistoryValue(stored, direction(output_operation, stored)), halfway, overridden


def negative_factor(
    row: dict[str, str],
    product_mask: int,
    add1_program: AddProgram,
    add2_program: AddProgram,
    enable_mask: int,
    output_scope: str,
) -> tuple[Value, tuple[tuple[str, bool, bool], ...]]:
    magnitude = exact_source(row_value(row, "mag"))
    constant1 = exact_source(Value(*CONSTANTS[1]))
    constant3 = exact_source(Value(*CONSTANTS[3]))
    constant5 = exact_source(Value(*CONSTANTS[5]))
    events: list[tuple[str, bool, bool]] = []

    square = product_value(
        multiply(magnitude.value, magnitude.value), bool(product_mask & 1)
    )
    fourth = product_value(
        multiply(square.value, square.value), bool(product_mask & 2)
    )
    mul1 = product_value(
        multiply(fourth.value, constant5.value), bool(product_mask & 4)
    )
    add1, halfway, overridden = fadd_value(
        constant3,
        mul1,
        add1_program,
        bool(enable_mask & 1),
        output_scope,
    )
    events.append(("negative.add1", halfway, overridden))
    mul2 = product_value(
        multiply(fourth.value, add1.value), bool(product_mask & 8)
    )
    add2, halfway, overridden = fadd_value(
        constant1,
        mul2,
        add2_program,
        bool(enable_mask & 2),
        output_scope,
    )
    events.append(("negative.add2", halfway, overridden))
    return add2.value, tuple(events)


def mask_name(mask: int) -> str:
    active = [
        stage for index, stage in enumerate(PRODUCT_STAGES) if mask & (1 << index)
    ]
    return "+".join(active) if active else "scalar_chop67"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument(
        "--direct-label", action="append", type=Path, required=True
    )
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")
    if len(args.direct_label) < 2:
        raise SystemExit("supply at least two disjoint direct-label banks")

    labels: dict[str, int] = {}
    sources: dict[str, int] = {}
    for bank, path in enumerate(args.direct_label):
        bank_labels: dict[str, int] = {}
        load_direct(path, bank_labels)
        overlap = set(labels) & set(bank_labels)
        if overlap:
            raise RuntimeError(f"direct-label banks overlap: {sorted(overlap)}")
        labels.update(bank_labels)
        sources.update({operand: bank for operand in bank_labels})

    operands = sorted(labels)
    _, stderr = run(args.model, "rn", operands, dump=True)
    rows = parse_dump(stderr, operands)
    for row in rows:
        schedule(row)

    scores = []
    best_diagnostics = None
    candidate_count = 0
    for output_scope in ("bus", "sum"):
        for product_mask in range(16):
            for add1_program in ADD_PROGRAMS:
                for add2_program in ADD_PROGRAMS:
                    for enable_mask in range(4):
                        counts = Counter()
                        diagnostics = []
                        for row in rows:
                            candidate, events = negative_factor(
                                row,
                                product_mask,
                                add1_program,
                                add2_program,
                                enable_mask,
                                output_scope,
                            )
                            baseline = row_value(row, "lf")
                            delta = magnitude_delta(candidate, baseline)
                            predicted = int(delta == -1)
                            wanted = labels[row["op"]]
                            wrong = predicted != wanted
                            counts["errors"] += wrong
                            counts["positive_errors"] += wrong and wanted
                            counts["negative_errors"] += wrong and not wanted
                            counts["predicted_positives"] += predicted
                            counts[f"bank{sources[row['op']]}.errors"] += wrong
                            for stage, halfway, overridden in events:
                                counts[f"{stage}.half"] += halfway
                                counts[f"{stage}.override"] += overridden
                            diagnostics.append(
                                (
                                    row["op"],
                                    wanted,
                                    predicted,
                                    delta,
                                    sources[row["op"]],
                                    ",".join(
                                        stage
                                        for stage, _, overridden in events
                                        if overridden
                                    )
                                    or "-",
                                )
                            )
                        item = (
                            counts["errors"],
                            counts["positive_errors"],
                            counts["negative_errors"],
                            counts["predicted_positives"],
                            *(counts[f"bank{bank}.errors"] for bank in range(len(args.direct_label))),
                            counts["negative.add1.half"],
                            counts["negative.add2.half"],
                            counts["negative.add1.override"],
                            counts["negative.add2.override"],
                            output_scope,
                            product_mask,
                            mask_name(product_mask),
                            add1_program.name(),
                            add2_program.name(),
                            enable_mask,
                        )
                        scores.append(item)
                        if best_diagnostics is None or item < best_diagnostics[0]:
                            best_diagnostics = (item, diagnostics)
                        candidate_count += 1
    scores.sort()
    if best_diagnostics is None:
        raise AssertionError("empty composed-program search")

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write(f"model_sha256\t{digest(args.model)}\n")
        for index, path in enumerate(args.direct_label):
            output.write(f"direct_labels_sha256.{index}\t{digest(path)}\n")
        output.write("hardware_policy\tfrozen_one_shot_labels_no_x87_execution\n")
        output.write(
            "candidate_policy\tcomposed_FMUL_GRS_FAMUBUS_attached_RN_history\n"
        )
        output.write(f"operands\t{len(rows)}\n")
        output.write(f"positive_operands\t{sum(labels.values())}\n")
        output.write(f"product_routing_masks\t16\n")
        output.write(f"add_programs_per_site\t{len(ADD_PROGRAMS)}\n")
        output.write("history_enable_programs\t4\n")
        output.write("history_output_scopes\t2\n")
        output.write(f"candidates\t{candidate_count}\n")
        output.write(f"exact_candidates\t{sum(item[0] == 0 for item in scores)}\n")
        output.write("\n[ranking]\n")
        bank_columns = "\t".join(
            f"bank{bank}_errors" for bank in range(len(args.direct_label))
        )
        output.write(
            "errors\tpositive_errors\tnegative_errors\tpredicted_positives\t"
            f"{bank_columns}\tadd1_half\tadd2_half\tadd1_override\t"
            "add2_override\toutput_scope\tproduct_mask\tproduct_routing\t"
            "add1_program\tadd2_program\tR_mask\n"
        )
        for item in scores[:2048]:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[best program diagnostics]\n")
        output.write("op\twanted_wide\tpredicted_wide\tfactor_delta\tbank\toverrides\n")
        for item in best_diagnostics[1]:
            output.write("\t".join(map(str, item)) + "\n")

    print(
        f"wrote {args.report}: operands={len(rows)} candidates={candidate_count} "
        f"exact={sum(item[0] == 0 for item in scores)} best={scores[0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
