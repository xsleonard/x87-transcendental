#!/usr/bin/env python3
"""Compose literal FMUL G/R/S output with the patent-level FADD carrier.

h1321 replaces a chopped product's final value bit with exact sticky, but
then feeds that encoding through scalar addition.  h1324 replays the 68-bit
FAMUBUS adder, but feeds it ordinary chopped-product bits.  Neither audit
tests the literal composition suggested by the two datapaths:

* FMUL emits J plus 63 significand bits and G/R/S, with S the OR of every
  remaining product bit;
* FADD aligns that complete 67-bit bus, preserves alignment sticky, performs
  its integer carrier operation, and only then materializes RN64.

This pass composes those operations over the negative cosine Horner chain.
The four-bit product mask is a bounded routing falsifier over square, fourth,
mul1, and mul2; mask 15 is the uniform literal interpretation.  Each add uses
one of the four patent-backed sticky treatments and a fixed normalization
choice.  There are no operand predicates, thresholds, or learned tables.

Hardware labels are immutable one-shot inputs and this program executes no
x87 instruction.  Any exact program still requires a disjoint challenge and
evidence that its selected bus controls correspond to the physical UOP form.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import h200_p5_fadd_bitvector as h200
import h206_p5_fadd_complete as h206
from h1184_upstream_halfway_audit import (
    CONSTANTS,
    Value,
    multiply,
    quantize,
    row_value,
    schedule,
)
from h1191_grs_history_isomorphism import magnitude_delta
from h1210_stagea_residual_reframe import parse_dump, run
from h1316_highq_fixed_schedule_representations import load_direct
from h1321_famubus_grs_carrier_audit import famubus_grs


PRODUCT_STAGES = ("square", "fourth", "negative.mul1", "negative.mul2")


@dataclass(frozen=True)
class AddProgram:
    mode: str
    normalize: bool

    def name(self) -> str:
        return f"{self.mode}.{'norm' if self.normalize else 'raw'}.rn64"


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


def to_bus(value: Value) -> h200.Bus:
    return h200.normalized_bus((value.sign, value.significand, value.exponent))


def from_bus(bus: h200.Bus) -> Value:
    sign, significand, exponent = bus.value()
    return Value(sign, exponent, significand)


def product_value(operation, literal_grs: bool) -> Value:
    return famubus_grs(operation) if literal_grs else quantize(
        operation, 67, False)


def fadd_value(left: Value, right: Value, program: AddProgram) -> Value:
    bus, _ = h206.fadd(
        to_bus(left), to_bus(right), program.mode,
        normalize=program.normalize,
    )
    return from_bus(h206.materialize(bus, "rn64"))


def negative_factor(
        row: dict[str, str], product_mask: int,
        add1_program: AddProgram, add2_program: AddProgram) -> Value:
    magnitude = row_value(row, "mag")
    square = product_value(
        multiply(magnitude, magnitude), bool(product_mask & 1))
    fourth = product_value(
        multiply(square, square), bool(product_mask & 2))
    mul1 = product_value(
        multiply(fourth, Value(*CONSTANTS[5])), bool(product_mask & 4))
    add1 = fadd_value(Value(*CONSTANTS[3]), mul1, add1_program)
    mul2 = product_value(
        multiply(fourth, add1), bool(product_mask & 8))
    return fadd_value(Value(*CONSTANTS[1]), mul2, add2_program)


def mask_name(mask: int) -> str:
    active = [stage for index, stage in enumerate(PRODUCT_STAGES)
              if mask & (1 << index)]
    return "+".join(active) if active else "scalar_chop67"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument(
        "--direct-label", action="append", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")
    if len(args.direct_label) != 2:
        raise SystemExit("supply the older bank and extension bank in order")

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
    for product_mask in range(16):
        for add1_program in ADD_PROGRAMS:
            for add2_program in ADD_PROGRAMS:
                counts = Counter()
                diagnostics = []
                for row in rows:
                    candidate = negative_factor(
                        row, product_mask, add1_program, add2_program)
                    baseline = row_value(row, "lf")
                    delta = magnitude_delta(candidate, baseline)
                    predicted = int(delta == -1)
                    wanted = labels[row["op"]]
                    wrong = predicted != wanted
                    counts["errors"] += wrong
                    counts["positive_errors"] += wrong and wanted
                    counts["negative_errors"] += wrong and not wanted
                    counts[f"bank{sources[row['op']]}.errors"] += wrong
                    counts[f"delta.{delta}"] += 1
                    diagnostics.append((
                        row["op"], wanted, predicted, delta,
                        sources[row["op"]],
                    ))
                item = (
                    counts["errors"], counts["bank1.errors"],
                    counts["bank0.errors"], counts["positive_errors"],
                    counts["negative_errors"], counts["delta.-1"],
                    counts["delta.0"], counts["delta.1"],
                    mask_name(product_mask), product_mask,
                    add1_program.name(), add2_program.name(),
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
            "candidate_policy\tfixed_composed_FMUL_GRS_to_FAMUBUS_program\n")
        output.write(f"operands\t{len(rows)}\n")
        output.write(f"positive_operands\t{sum(labels.values())}\n")
        output.write(f"product_routing_masks\t16\n")
        output.write(f"add_programs_per_site\t{len(ADD_PROGRAMS)}\n")
        output.write(f"candidates\t{candidate_count}\n")
        output.write(f"exact_candidates\t{sum(item[0] == 0 for item in scores)}\n")
        output.write("\n[ranking]\n")
        output.write(
            "errors\textension_errors\tolder_errors\tpositive_errors\t"
            "negative_errors\tdelta_minus1\tdelta_zero\tdelta_plus1\t"
            "product_routing\tmask\tadd1_program\tadd2_program\n")
        for item in scores[:1024]:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[best program diagnostics]\n")
        output.write("op\twanted_wide\tpredicted_wide\tfactor_delta\tbank\n")
        for item in best_diagnostics[1]:
            output.write("\t".join(map(str, item)) + "\n")

    print(
        f"wrote {args.report}: operands={len(rows)} "
        f"candidates={candidate_count} "
        f"exact={sum(item[0] == 0 for item in scores)} "
        f"best={scores[0][:8]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
