#!/usr/bin/env python3
"""Solve small fixed discarded-prefix controllers jointly at both powers.

h1342 proves that neither square nor fourth endpoint selection alone can
reach every wider label.  This audit allows both 65-bit power edges to choose
their adjacent endpoint.  At each edge the choice is one fixed Boolean table
indexed only by retained LSB, a bounded top discarded prefix, and sticky
below that prefix.  Square depths 1--3 are exhaustively enumerated; for every
square table, the globally optimal fourth table is solved independently per
observed fourth state at depths 1--6.

This is a bounded round-controller grammar, not an accepted selector.  An
exact table still requires structural simplification and a disjoint frozen
challenge.  Hardware labels are immutable scoring inputs and this program
executes no x87 instruction.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

from h1184_upstream_halfway_audit import multiply, row_value
from h1191_grs_history_isomorphism import magnitude_delta
from h1210_stagea_residual_reframe import parse_dump, run
from h1316_highq_fixed_schedule_representations import load_direct
from h1339_highq_custom_rounding_laws import factor_from_fourth
from h1342_highq_round_prefix_depth import prefix_state, quantize_forced


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def branch_records(prepared, square_depth: int, fourth_depth: int):
    raw = []
    square_states = set()
    fourth_states = set()
    endpoint_impossible = 0
    for operand, magnitude, baseline, wanted, bank in prepared:
        square_op = multiply(magnitude, magnitude)
        square_state = prefix_state(square_op, 65, square_depth)
        square_states.add(square_state)
        branches = []
        any_match = False
        for square_increment in (0, 1):
            square = quantize_forced(square_op, 65, square_increment)
            fourth_op = multiply(square, square)
            fourth_state = prefix_state(fourth_op, 65, fourth_depth)
            fourth_states.add(fourth_state)
            predictions = []
            for fourth_increment in (0, 1):
                fourth = quantize_forced(fourth_op, 65, fourth_increment)
                delta = magnitude_delta(factor_from_fourth(fourth), baseline)
                predictions.append(int(delta == -1))
                any_match |= predictions[-1] == wanted
            branches.append((fourth_state, tuple(predictions)))
        endpoint_impossible += not any_match
        raw.append((
            operand, square_state, tuple(branches), wanted, bank))

    square_index = {
        state: index for index, state in enumerate(sorted(square_states))}
    fourth_index = {
        state: index for index, state in enumerate(sorted(fourth_states))}
    records = [(
        operand,
        square_index[square_state],
        tuple((fourth_index[state], predictions)
              for state, predictions in branches),
        wanted,
        bank,
    ) for operand, square_state, branches, wanted, bank in raw]
    return records, square_index, fourth_index, endpoint_impossible


def solve(records, square_state_count: int, fourth_state_count: int):
    best = None
    exact = []
    for square_table in range(1 << square_state_count):
        error_counts = [[0, 0] for _ in range(fourth_state_count)]
        bank_error_counts = [
            [[0, 0] for _ in range(fourth_state_count)] for _ in range(2)]
        for _, square_state, branches, wanted, bank in records:
            square_increment = (square_table >> square_state) & 1
            fourth_state, predictions = branches[square_increment]
            for fourth_increment in (0, 1):
                wrong = predictions[fourth_increment] != wanted
                error_counts[fourth_state][fourth_increment] += wrong
                bank_error_counts[bank][fourth_state][fourth_increment] += wrong
        fourth_table = 0
        errors = 0
        for state, pair in enumerate(error_counts):
            state_errors, increment = min((value, choice)
                                          for choice, value in enumerate(pair))
            errors += state_errors
            fourth_table |= increment << state

        positive_errors = negative_errors = predicted_positives = 0
        bank_errors = [0, 0]
        if best is None or errors <= best[0]:
            for _, square_state, branches, wanted, bank in records:
                square_increment = (square_table >> square_state) & 1
                fourth_state, predictions = branches[square_increment]
                fourth_increment = (fourth_table >> fourth_state) & 1
                predicted = predictions[fourth_increment]
                wrong = predicted != wanted
                positive_errors += wrong and wanted
                negative_errors += wrong and not wanted
                predicted_positives += predicted
                bank_errors[bank] += wrong
        item = (
            errors, bank_errors[1], bank_errors[0], positive_errors,
            negative_errors, predicted_positives, square_table, fourth_table)
        if best is None or item < best:
            best = item
        if not errors:
            exact.append(item)
    if best is None:
        raise AssertionError("no square tables evaluated")
    return best, exact


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument(
        "--direct-label", action="append", type=Path, required=True)
    parser.add_argument("--max-square-depth", type=int, default=3)
    parser.add_argument("--max-fourth-depth", type=int, default=6)
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
    exact_results = []
    for square_depth in range(1, args.max_square_depth + 1):
        for fourth_depth in range(1, args.max_fourth_depth + 1):
            records, square_index, fourth_index, impossible = branch_records(
                prepared, square_depth, fourth_depth)
            best, exact = solve(records, len(square_index), len(fourth_index))
            item = (
                *best[:6], len(square_index), len(fourth_index), impossible,
                square_depth, fourth_depth, best[6], best[7], len(exact),
            )
            results.append(item)
            for exact_item in exact:
                exact_results.append((
                    square_depth, fourth_depth, len(square_index),
                    len(fourth_index), exact_item[6], exact_item[7]))
    results.sort(key=lambda item: (item[9], item[10]))

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write(f"model_sha256\t{digest(args.model)}\n")
        for index, path in enumerate(args.direct_label):
            output.write(f"direct_labels_sha256.{index}\t{digest(path)}\n")
        output.write("hardware_policy\tfrozen_one_shot_labels_no_x87_execution\n")
        output.write("candidate_policy\tjoint_fixed_power_prefix_controllers\n")
        output.write(f"operands\t{len(prepared)}\n")
        output.write(f"positive_operands\t{sum(labels.values())}\n")
        output.write(f"max_square_depth\t{args.max_square_depth}\n")
        output.write(f"max_fourth_depth\t{args.max_fourth_depth}\n")
        output.write(f"exact_depth_pairs\t{sum(not item[0] for item in results)}\n")
        output.write("\n[depth grid]\n")
        output.write(
            "errors\textension_errors\tolder_errors\tpositive_errors\t"
            "negative_errors\tpredicted_positives\tsquare_states\t"
            "fourth_states\tendpoint_impossible\tsquare_depth\t"
            "fourth_depth\tsquare_table_hex\tfourth_table_hex\t"
            "exact_square_tables\n")
        for item in results:
            rendered = (
                *item[:11], f"{item[11]:x}", f"{item[12]:x}", item[13])
            output.write("\t".join(map(str, rendered)) + "\n")
        output.write("\n[exact controllers]\n")
        output.write(
            "square_depth\tfourth_depth\tsquare_states\tfourth_states\t"
            "square_table_hex\tfourth_table_hex\n")
        for item in exact_results[:4096]:
            rendered = (*item[:4], f"{item[4]:x}", f"{item[5]:x}")
            output.write("\t".join(map(str, rendered)) + "\n")
        if len(exact_results) > 4096:
            output.write(f"truncated\t{len(exact_results) - 4096}\n")

    print(
        f"wrote {args.report}: operands={len(prepared)} "
        f"depth_pairs={len(results)} exact_pairs="
        f"{sum(not item[0] for item in results)} best={min(results)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
