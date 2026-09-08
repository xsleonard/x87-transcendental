#!/usr/bin/env python3
"""Test fixed asymmetric X67/Y64 recurrences for the power-building products.

The strongest scalar approximation before the h1351 blind bank used a
65-bit round-to-odd square and a 65-bit chopped fourth power.  That may be an
alias for port asymmetry rather than a novel rounding mode: contemporary
Intel multiplier diagrams expose a 67-bit X input and a 64-bit Y input.

This audit places the same value on X67 and a globally materialized 64-bit
copy on Y64 for each of the square and fourth-power multiplies.  It exhausts
chop, nearest, away, and odd materialization at the Y input and at 64--67-bit
product outputs.  ``full`` Y inputs retain the symmetric scalar schedules as
controls.  The Horner chain remains at its recovered chop67/RN64 schedule.

These are fixed arithmetic programs, not operand predicates or tables.
Hardware labels are immutable one-shot inputs and this program executes no
x87 instruction.  An exact survivor would require a separately frozen blind
challenge and evidence for the chosen port controls.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from h1184_upstream_halfway_audit import ExactOperation, Value, multiply, row_value
from h1191_grs_history_isomorphism import magnitude_delta, quantize_mode
from h1210_stagea_residual_reframe import parse_dump, run
from h1337_highq_fused_power_carrier import factor_from_fourth


MODES = ("chop", "rn", "away", "odd")
Y_MODES = ("full", *MODES)


@dataclass(frozen=True)
class ProductProgram:
    y_mode: str
    output_width: int
    output_mode: str

    def name(self) -> str:
        return f"X67.Y{self.y_mode}.O{self.output_mode}{self.output_width}"


PROGRAMS = tuple(
    ProductProgram(y_mode, width, output_mode)
    for y_mode in Y_MODES
    for width in range(64, 68)
    for output_mode in MODES
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def load_labels(paths: list[Path]) -> tuple[dict[str, int], dict[str, int]]:
    labels: dict[str, int] = {}
    sources: dict[str, int] = {}
    for bank, path in enumerate(paths):
        with path.open(newline="") as source:
            for row in csv.DictReader(source, delimiter="\t"):
                verdict = row.get("verdict", row.get("actual_verdict"))
                if verdict not in ("wide", "predecessor"):
                    raise ValueError(f"bad direct verdict in {path}: {verdict!r}")
                operand = row["op"].lower()
                label = int(verdict == "wide")
                previous = labels.setdefault(operand, label)
                if previous != label:
                    raise RuntimeError(f"inconsistent direct label for {operand}")
                previous_bank = sources.setdefault(operand, bank)
                if previous_bank != bank:
                    raise RuntimeError(f"operand occurs in two banks: {operand}")
    return labels, sources


def as_operation(value: Value) -> ExactOperation:
    return ExactOperation(value.sign, value.exponent, value.significand)


def product(value: Value, program: ProductProgram) -> Value:
    y = (
        value
        if program.y_mode == "full"
        else quantize_mode(as_operation(value), 64, program.y_mode)
    )
    return quantize_mode(
        multiply(value, y), program.output_width, program.output_mode
    )


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

    labels, sources = load_labels(args.direct_label)
    operands = sorted(labels)
    _, stderr = run(args.model, "rn", operands, dump=True)
    rows = parse_dump(stderr, operands)
    prepared = [
        (
            row["op"],
            row_value(row, "mag"),
            row_value(row, "lf"),
            labels[row["op"]],
            sources[row["op"]],
        )
        for row in rows
    ]

    square_values = {
        program: [product(row[1], program) for row in prepared]
        for program in PROGRAMS
    }
    scores = []
    best_diagnostics = None
    candidate_count = 0
    for square_program in PROGRAMS:
        squares = square_values[square_program]
        for fourth_program in PROGRAMS:
            counts = Counter()
            diagnostics = []
            for row, square in zip(prepared, squares):
                fourth = product(square, fourth_program)
                delta = magnitude_delta(factor_from_fourth(fourth), row[2])
                predicted = int(delta == -1)
                wanted = row[3]
                wrong = predicted != wanted
                counts["errors"] += wrong
                counts["positive_errors"] += wrong and wanted
                counts["negative_errors"] += wrong and not wanted
                counts["predicted_positives"] += predicted
                counts[f"bank{row[4]}.errors"] += wrong
                counts[f"delta.{delta}"] += 1
                diagnostics.append((row[0], wanted, predicted, delta, row[4]))
            item = (
                counts["errors"],
                counts["positive_errors"],
                counts["negative_errors"],
                counts["predicted_positives"],
                *(counts[f"bank{bank}.errors"] for bank in range(len(args.direct_label))),
                counts["delta.-1"],
                counts["delta.0"],
                len(prepared) - counts["delta.-1"] - counts["delta.0"],
                square_program.name(),
                fourth_program.name(),
            )
            scores.append(item)
            if best_diagnostics is None or item < best_diagnostics[0]:
                best_diagnostics = (item, diagnostics)
            candidate_count += 1
    scores.sort()
    if best_diagnostics is None:
        raise AssertionError("empty recurrence search")

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write(f"model_sha256\t{digest(args.model)}\n")
        for index, path in enumerate(args.direct_label):
            output.write(f"direct_labels_sha256.{index}\t{digest(path)}\n")
        output.write("hardware_policy\tfrozen_one_shot_labels_no_x87_execution\n")
        output.write("candidate_policy\tfixed_X67_Y64_power_recurrences\n")
        output.write(f"operands\t{len(prepared)}\n")
        output.write(f"positive_operands\t{sum(labels.values())}\n")
        output.write(f"programs_per_power_site\t{len(PROGRAMS)}\n")
        output.write(f"candidates\t{candidate_count}\n")
        output.write(f"exact_candidates\t{sum(item[0] == 0 for item in scores)}\n")
        output.write("\n[ranking]\n")
        bank_columns = "\t".join(
            f"bank{bank}_errors" for bank in range(len(args.direct_label))
        )
        output.write(
            "errors\tpositive_errors\tnegative_errors\tpredicted_positives\t"
            f"{bank_columns}\tdelta_minus1\tdelta_zero\tdelta_other\t"
            "square_program\tfourth_program\n"
        )
        for item in scores[:2048]:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[best program diagnostics]\n")
        output.write("op\twanted_wide\tpredicted_wide\tfactor_delta\tbank\n")
        for item in best_diagnostics[1]:
            output.write("\t".join(map(str, item)) + "\n")

    print(
        f"wrote {args.report}: operands={len(prepared)} candidates={candidate_count} "
        f"exact={sum(item[0] == 0 for item in scores)} best={scores[0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
