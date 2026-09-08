#!/usr/bin/env python3
"""Measure how much discarded-prefix state a power-edge controller needs.

h1341 shows that exposing one additional discarded bit improves the best
65-bit power representation but still leaves five true wider cases.  This
audit does not promote a larger fitted truth table.  It asks a sharper
structural question: at each prefix depth, can *any* fixed controller over

    retained LSB, the top d discarded bits, and sticky below that prefix

select the lower/upper 65-bit endpoint consistently?  It reports the minimum
possible error independently at the square and fourth edges while holding the
other edge at the strongest preceding fixed law.  The table-depth curve
distinguishes a compact round controller from eventual memorization of unique
residues.

Hardware labels are immutable scoring inputs and this program executes no x87
instruction.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

from h1184_upstream_halfway_audit import ExactOperation, Value, multiply, row_value
from h1191_grs_history_isomorphism import magnitude_delta
from h1210_stagea_residual_reframe import parse_dump, run
from h1316_highq_fixed_schedule_representations import load_direct
from h1339_highq_custom_rounding_laws import factor_from_fourth, quantize_law
from h1341_highq_four_input_rounding_laws import quantize_law4


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def quantize_forced(operation: ExactOperation, bits: int, increment: int) -> Value:
    shift = max(0, operation.magnitude.bit_length() - bits)
    retained = operation.magnitude >> shift
    remainder = operation.magnitude & ((1 << shift) - 1) if shift else 0
    retained += int(bool(remainder) and increment)
    if retained == 1 << bits:
        retained >>= 1
        shift += 1
    return Value(operation.sign, operation.exponent + shift, retained)


def prefix_state(operation: ExactOperation, bits: int, depth: int) -> int:
    shift = max(0, operation.magnitude.bit_length() - bits)
    retained = operation.magnitude >> shift
    remainder = operation.magnitude & ((1 << shift) - 1) if shift else 0
    kept = min(depth, shift)
    prefix = remainder >> (shift - kept) if kept else 0
    prefix <<= depth - kept
    sticky = int(
        shift > depth and bool(remainder & ((1 << (shift - depth)) - 1)))
    return (retained & 1) | (prefix << 1) | (sticky << (depth + 1))


def evaluate_family(prepared, family: str, depth: int):
    groups = defaultdict(list)
    endpoint_impossible = 0
    for operand, magnitude, baseline, wanted, bank in prepared:
        square_op = multiply(magnitude, magnitude)
        if family == "square":
            operation = square_op
            predictions = []
            deltas = []
            for increment in (0, 1):
                square = quantize_forced(square_op, 65, increment)
                fourth = quantize_law4(
                    multiply(square, square), 65, 0x4000)
                delta = magnitude_delta(factor_from_fourth(fourth), baseline)
                deltas.append(delta)
                predictions.append(int(delta == -1))
        elif family == "fourth":
            square = quantize_law(square_op, 65, 0x60)
            operation = multiply(square, square)
            predictions = []
            deltas = []
            for increment in (0, 1):
                fourth = quantize_forced(operation, 65, increment)
                delta = magnitude_delta(factor_from_fourth(fourth), baseline)
                deltas.append(delta)
                predictions.append(int(delta == -1))
        else:
            raise ValueError(family)
        endpoint_impossible += all(predicted != wanted for predicted in predictions)
        state = prefix_state(operation, 65, depth)
        groups[state].append((
            operand, wanted, bank, tuple(predictions), tuple(deltas)))

    counts = Counter()
    decisions = {}
    conflicting_groups = 0
    for state, rows in groups.items():
        errors_by_increment = []
        for increment in (0, 1):
            errors = sum(
                row[3][increment] != row[1] for row in rows)
            errors_by_increment.append(errors)
        decision = min((errors, increment) for increment, errors in enumerate(
            errors_by_increment))[1]
        decisions[state] = decision
        if errors_by_increment[0] and errors_by_increment[1]:
            conflicting_groups += 1
        for _, wanted, bank, predictions, deltas in rows:
            predicted = predictions[decision]
            delta = deltas[decision]
            wrong = predicted != wanted
            counts["errors"] += wrong
            counts[f"bank{bank}.errors"] += wrong
            counts["positive_errors"] += wrong and wanted
            counts["negative_errors"] += wrong and not wanted
            counts["predicted_positives"] += predicted
            counts[f"delta.{delta}"] += 1
    score = (
        counts["errors"], counts["bank1.errors"], counts["bank0.errors"],
        counts["positive_errors"], counts["negative_errors"],
        counts["predicted_positives"], len(groups), conflicting_groups,
        endpoint_impossible, family, depth,
    )
    return score, groups, decisions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument(
        "--direct-label", action="append", type=Path, required=True)
    parser.add_argument("--max-depth", type=int, default=20)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")
    if len(args.direct_label) != 2:
        raise SystemExit("supply the older bank and extension bank in order")

    labels: dict[str, int] = {}
    source_bank: dict[str, int] = {}
    for bank, path in enumerate(args.direct_label):
        bank_labels: dict[str, int] = {}
        load_direct(path, bank_labels)
        overlap = set(labels) & set(bank_labels)
        if overlap:
            raise RuntimeError(f"direct-label banks overlap: {sorted(overlap)}")
        labels.update(bank_labels)
        for operand in bank_labels:
            source_bank[operand] = bank
    operands = sorted(labels)
    _, stderr = run(args.model, "rn", operands, dump=True)
    rows = parse_dump(stderr, operands)
    prepared = [(
        row["op"], row_value(row, "mag"), row_value(row, "lf"),
        labels[row["op"]], source_bank[row["op"]],
    ) for row in rows]

    results = []
    details = {}
    for family in ("square", "fourth"):
        for depth in range(1, args.max_depth + 1):
            score, groups, decisions = evaluate_family(prepared, family, depth)
            results.append(score)
            details[(family, depth)] = (groups, decisions)
    results.sort(key=lambda item: (item[9], item[10]))

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write(f"model_sha256\t{digest(args.model)}\n")
        for index, path in enumerate(args.direct_label):
            output.write(f"direct_labels_sha256.{index}\t{digest(path)}\n")
        output.write("hardware_policy\tfrozen_one_shot_labels_no_x87_execution\n")
        output.write("candidate_policy\tminimum_fixed_discarded_prefix_controller\n")
        output.write(f"operands\t{len(prepared)}\n")
        output.write(f"positive_operands\t{sum(labels.values())}\n")
        output.write(f"max_prefix_depth\t{args.max_depth}\n")
        output.write("\n[depth curve]\n")
        output.write(
            "errors\textension_errors\tolder_errors\tpositive_errors\t"
            "negative_errors\tpredicted_positives\tobserved_states\t"
            "conflicting_states\tendpoint_impossible_rows\tfamily\tdepth\n")
        for item in results:
            output.write("\t".join(map(str, item)) + "\n")

        exact = [item for item in results if not item[0]]
        output.write("\n[first exact maps]\n")
        for item in exact:
            family, depth = item[9], item[10]
            if any(prior[9] == family and not prior[0] for prior in results
                   if prior[10] < depth):
                continue
            groups, decisions = details[(family, depth)]
            output.write(f"map\t{family}\tdepth={depth}\tstates={len(groups)}\n")
            for state in sorted(groups):
                output.write(
                    f"state\t{state:0{depth + 2}b}\t{decisions[state]}\t"
                    f"rows={len(groups[state])}\n")

    best_by_family = {
        family: min(item for item in results if item[9] == family)
        for family in ("square", "fourth")
    }
    print(
        f"wrote {args.report}: operands={len(prepared)} "
        f"best_square={best_by_family['square']} "
        f"best_fourth={best_by_family['fourth']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
