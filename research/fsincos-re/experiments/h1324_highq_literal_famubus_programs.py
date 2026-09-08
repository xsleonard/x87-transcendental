#!/usr/bin/env python3
"""Replay literal P5 FAMUBUS programs on the open high-q Horner factor.

h1323 shows that ordinary ripple/carry-select wires of a scalar same-sign
addition do not explain the factor labels.  This audit moves one level up in
representation: h206's patent-backed 68-bit FAMUBUS keeps J, 64 significand
bits, and G/R/S as an integer carrier, with alignment sticky and independently
controlled normalization/rounding.

All fixed local add2 programs are tested.  The bounded recursive audit also
chooses one fixed program for negative.add1, routes its value through the
ordinary recovered 67-bit multiply, and applies one fixed program at add2.
There are no operand conditions or fitted thresholds.  Frozen labels are used
only to score these global programs; no x87 instruction is executed.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
from collections import Counter
from pathlib import Path

import h200_p5_fadd_bitvector as h200
import h206_p5_fadd_complete as h206
from h1184_upstream_halfway_audit import (
    CONSTANTS,
    Value,
    add_same_sign,
    multiply,
    quantize,
    row_value,
    schedule,
)
from h1191_grs_history_isomorphism import magnitude_delta
from h1210_stagea_residual_reframe import parse_dump, run
from h1316_highq_fixed_schedule_representations import (
    load_causal,
    load_direct,
    load_siblings,
)


OUTPUTS = ("retain", "rn64", "chop64", "away64", "odd64", "odd67")


@dataclasses.dataclass(frozen=True)
class Program:
    mode: str
    normalize: bool
    output: str

    def name(self) -> str:
        return f"{self.mode}.{'norm' if self.normalize else 'raw'}.{self.output}"


PROGRAMS = tuple(
    Program(mode, normalize, output)
    for mode in h206.MODES
    for normalize in (False, True)
    for output in OUTPUTS
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


def fadd(left: Value, right: Value, program: Program) -> Value:
    bus, _ = h206.fadd(
        to_bus(left), to_bus(right), program.mode,
        normalize=program.normalize,
    )
    return from_bus(h206.materialize(bus, program.output))


def baseline_inputs(row: dict[str, str]
                    ) -> tuple[Value, Value, Value, Value]:
    operations = schedule(row)
    fourth = quantize(operations["fourth"], 67, False)
    add1 = quantize(operations["negative.add1"], 64, True)
    mul2 = quantize(multiply(fourth, add1), 67, False)
    return fourth, add1, mul2, row_value(row, "lf")


def score(deltas: list[int | None], labels: list[int]
          ) -> tuple[int, int, int, Counter]:
    predictions = [int(delta == -1) for delta in deltas]
    errors = sum(predicted != wanted
                 for predicted, wanted in zip(predictions, labels))
    positive_errors = sum(wanted and predicted != wanted
                          for predicted, wanted in zip(predictions, labels))
    negative_errors = errors - positive_errors
    return errors, positive_errors, negative_errors, Counter(deltas)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("causal_legs", type=Path)
    parser.add_argument("sibling_labels", type=Path)
    parser.add_argument("direct_labels", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    factor_labels: dict[str, int] = {}
    load_causal(args.causal_legs, factor_labels)
    load_siblings(args.sibling_labels, factor_labels)
    load_direct(args.direct_labels, factor_labels)
    operands = sorted(factor_labels)
    _, stderr = run(args.model, "rn", operands, dump=True)
    rows = parse_dump(stderr, operands)
    prepared = [baseline_inputs(row) for row in rows]
    labels = [factor_labels[row["op"]] for row in rows]

    local_values: dict[Program, list[Value]] = {}
    local_scores = []
    for program in PROGRAMS:
        values = [fadd(Value(*CONSTANTS[1]), mul2, program)
                  for _, _, mul2, _ in prepared]
        local_values[program] = values
        deltas = [magnitude_delta(value, baseline)
                  for value, (*_, baseline) in zip(values, prepared)]
        errors, positive_errors, negative_errors, counts = score(deltas, labels)
        local_scores.append((
            errors, positive_errors, negative_errors,
            counts[-1], counts[0], counts[1], program.name(), program,
        ))
    local_scores.sort()

    add1_values: dict[Program, list[Value]] = {}
    for program in PROGRAMS:
        stage_values = []
        for row in rows:
            operations = schedule(row)
            mul1 = quantize(operations["negative.mul1"], 67, False)
            stage_values.append(fadd(Value(*CONSTANTS[3]), mul1, program))
        add1_values[program] = stage_values

    recursive_scores = []
    best_diagnostics = None
    for add1_program in PROGRAMS:
        mul2_values = [
            quantize(multiply(fourth, add1), 67, False)
            for (fourth, _, _, _), add1 in zip(
                prepared, add1_values[add1_program])
        ]
        for add2_program in PROGRAMS:
            values = [fadd(Value(*CONSTANTS[1]), mul2, add2_program)
                      for mul2 in mul2_values]
            deltas = [magnitude_delta(value, baseline)
                      for value, (*_, baseline) in zip(values, prepared)]
            errors, positive_errors, negative_errors, counts = score(
                deltas, labels)
            item = (
                errors, positive_errors, negative_errors,
                counts[-1], counts[0], counts[1],
                add1_program.name(), add2_program.name(),
            )
            recursive_scores.append(item)
            if best_diagnostics is None or item < best_diagnostics[0]:
                best_diagnostics = (item, deltas)
    recursive_scores.sort()
    if best_diagnostics is None:
        raise AssertionError("empty recursive program set")

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        for name, path in (
            ("model", args.model),
            ("causal_legs", args.causal_legs),
            ("sibling_labels", args.sibling_labels),
            ("direct_labels", args.direct_labels),
        ):
            output.write(f"{name}_sha256\t{digest(path)}\n")
        output.write("hardware_policy\tfrozen_factor_labels_no_x87_execution\n")
        output.write("candidate_policy\tfixed_literal_FAMUBUS_programs\n")
        output.write(f"operands\t{len(rows)}\n")
        output.write(f"positive_operands\t{sum(labels)}\n")
        output.write(f"stage_programs\t{len(PROGRAMS)}\n")
        output.write(f"recursive_program_pairs\t{len(recursive_scores)}\n")
        output.write(
            f"exact_local_programs\t{sum(item[0] == 0 for item in local_scores)}\n")
        output.write(
            "exact_recursive_programs\t"
            f"{sum(item[0] == 0 for item in recursive_scores)}\n")
        output.write("\n[local add2 ranking]\n")
        output.write(
            "errors\tpositive_errors\tnegative_errors\tdelta_minus1\t"
            "delta_zero\tdelta_plus1\tprogram\n")
        for item in local_scores:
            output.write("\t".join(map(str, item[:-1])) + "\n")
        output.write("\n[recursive add1/add2 ranking]\n")
        output.write(
            "errors\tpositive_errors\tnegative_errors\tdelta_minus1\t"
            "delta_zero\tdelta_plus1\tadd1_program\tadd2_program\n")
        for item in recursive_scores[:512]:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[best recursive diagnostics]\n")
        output.write("op\twanted_wide\tfactor_delta\n")
        for row, wanted, delta in zip(rows, labels, best_diagnostics[1]):
            output.write(f"{row['op']}\t{wanted}\t{delta}\n")

    print(
        f"wrote {args.report}: operands={len(rows)} "
        f"local_exact={sum(item[0] == 0 for item in local_scores)} "
        f"recursive_exact={sum(item[0] == 0 for item in recursive_scores)} "
        f"best_local={local_scores[0][0]} "
        f"best_recursive={recursive_scores[0][0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
