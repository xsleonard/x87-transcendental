#!/usr/bin/env python3
"""Audit a finite precision-difference state through the complete polynomial model.

h1251/h1258 quantized only the two local terminal-FMUL tails.  h1355 carried
a finite signed precision difference through the Horner graph, but consumed
it at the final negative Horner FADD.  This experiment tests the remaining
distinct placement: carry one uniform attached state through every modeled
FMUL/FADD, including both terminal FMULs, and consume the terminal states at
the final subtraction carry.

Each scalar value still follows the recovered chop67/RN64 schedule.  Its
attached state is a quantized signed estimate-minus-stored difference on a
fixed fractional-ulp grid, optionally saturated.  FMUL and FADD may use
separate globally fixed formats.  The terminal operation may consume the
left tag, right tag, or their signed-numeric sum, either directly or through
one fixed two-input gate with the incumbent carry.  There are no operand
predicates, identity keys, or learned numeric thresholds.  Cached all-mode
labels are immutable scoring inputs; no x87 instruction is executed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from h1110_carry_gate_mine import allmode_allowed, extract_carry_state
from h1184_upstream_halfway_audit import CONSTANTS, Value, row_value, schedule
from h1192_precision_difference_recurrence import Dyad, dyad_add
from h1355_quantized_precision_difference_recurrence import (
    HistoryValue,
    TagFormat,
    add_history,
    exact_source,
    formats,
    multiply_history,
)


SOURCES = ("left", "right", "both")
GATES = range(16)


@dataclass(frozen=True)
class PreparedRow:
    row: dict[str, str]
    current: int
    allowed: frozenset[int]
    target: bool


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        return list(csv.DictReader(source, delimiter="\t"))


def history_graph(
        magnitude: Value, mul_format: TagFormat,
        add_format: TagFormat) -> tuple[HistoryValue, HistoryValue]:
    """Return attached-state values for the two terminal FMUL outputs."""
    mag = exact_source(magnitude)
    constants = {
        index: exact_source(Value(*value))
        for index, value in CONSTANTS.items()
    }

    square = multiply_history(mag, mag, 67, False, mul_format)
    fourth = multiply_history(square, square, 67, False, mul_format)

    negative = multiply_history(
        fourth, constants[5], 67, False, mul_format)
    negative = add_history(
        constants[3], negative, 64, True, add_format)
    negative = multiply_history(
        fourth, negative, 67, False, mul_format)
    negative = add_history(
        constants[1], negative, 64, True, add_format)

    positive = multiply_history(
        fourth, constants[6], 67, False, mul_format)
    positive = add_history(
        constants[4], positive, 64, True, add_format)
    positive = multiply_history(
        fourth, positive, 67, False, mul_format)
    positive = add_history(
        constants[2], positive, 64, True, add_format)

    left = multiply_history(square, negative, 67, False, mul_format)
    right = multiply_history(fourth, positive, 67, False, mul_format)
    return left, right


def correction(left: HistoryValue, right: HistoryValue, source: str) -> Dyad:
    # Differences are signed numeric differences.  The negative sign of the
    # left product is therefore already represented in left.difference.
    if source == "left":
        return left.difference
    if source == "right":
        return right.difference
    if source == "both":
        return dyad_add(left.difference, right.difference)
    raise ValueError(source)


def add_at_exponent(value: Dyad, numerator: int, exponent: int) -> Dyad:
    return dyad_add(value, Dyad(numerator, exponent))


def predicted_carry(row: dict[str, str], value: Dyad) -> int:
    cut = int(row["k"])
    mask = (1 << cut) - 1
    low_difference = (
        (int(row["S"], 16) & mask) - (int(row["B"], 16) & mask)
    )
    corrected = add_at_exponent(
        value, low_difference, int(row["rscale"]))
    return int(corrected.numerator >= 0)


def output_gate(mask: int, current: int, state: int) -> int:
    return (mask >> (2 * current + state)) & 1


def prepare(
        feature_paths: list[Path], positive_path: Path,
        control_path: Path) -> tuple[list[PreparedRow], dict[str, Value]]:
    positive = allmode_allowed(positive_path)
    controls = allmode_allowed(control_path)
    rows = []
    magnitudes = {}
    seen = set()
    for feature_path in feature_paths:
        for row in read_rows(feature_path):
            key = (row["mode"], row["op"])
            if key in seen:
                raise RuntimeError("duplicate feature row: " + repr(key))
            seen.add(key)
            allowed_delta = (
                positive if row["label"] == "POS" else controls
            )[row["op"]]
            state = extract_carry_state(row, allowed_delta)
            if not state[3]:
                raise RuntimeError("carry-impossible row: " + repr(key))
            if len(state[3]) != 1:
                continue
            schedule(row)
            magnitude = row_value(row, "mag")
            previous = magnitudes.setdefault(row["op"], magnitude)
            if previous != magnitude:
                raise RuntimeError("operand magnitude changed: " + row["op"])
            rows.append(PreparedRow(
                row, state[2], frozenset(state[3]), row["label"] == "POS"))
    return rows, magnitudes


def score_format(
        rows: list[PreparedRow], magnitudes: dict[str, Value],
        mul_format: TagFormat, add_format: TagFormat):
    histories = {
        operand: history_graph(magnitude, mul_format, add_format)
        for operand, magnitude in magnitudes.items()
    }
    ranking = []
    diagnostics = {}
    for source in SOURCES:
        counts = {
            gate: Counter() for gate in GATES
        }
        source_diagnostics = {
            gate: [] for gate in GATES
        }
        for prepared in rows:
            left, right = histories[prepared.row["op"]]
            state = predicted_carry(
                prepared.row, correction(left, right, source))
            for gate in GATES:
                output = output_gate(gate, prepared.current, state)
                wrong = output not in prepared.allowed
                counts[gate]["errors"] += wrong
                counts[gate]["target_errors"] += wrong and prepared.target
                counts[gate]["control_errors"] += wrong and not prepared.target
                counts[gate]["changes"] += output != prepared.current
                counts[gate]["predicted_ones"] += output
                if prepared.target:
                    source_diagnostics[gate].append((
                        prepared.row["mode"], prepared.row["op"],
                        prepared.current, state, output,
                        ",".join(map(str, sorted(prepared.allowed))),
                        int(not wrong),
                    ))
        for gate in GATES:
            item = (
                counts[gate]["errors"], counts[gate]["target_errors"],
                counts[gate]["control_errors"], counts[gate]["changes"],
                counts[gate]["predicted_ones"], source, gate,
                mul_format.name(), add_format.name(),
            )
            ranking.append(item)
            diagnostics[item] = source_diagnostics[gate]
    ranking.sort()
    return ranking, diagnostics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", nargs="+", type=Path)
    parser.add_argument("positive_allmode", type=Path)
    parser.add_argument("control_allmode", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--refinement", type=int, default=8)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit("refusing to overwrite " + str(args.report))

    rows, magnitudes = prepare(
        args.features, args.positive_allmode, args.control_allmode)
    format_list = formats()
    ranking = []
    diagnostic_by_item = {}
    uniform_best = []
    for index, fmt in enumerate(format_list, 1):
        scores, diagnostics = score_format(
            rows, magnitudes, fmt, fmt)
        ranking.extend(scores)
        diagnostic_by_item.update(diagnostics)
        uniform_best.append(scores[0])
        if index % 20 == 0:
            print("uniform", index, "/", len(format_list), flush=True)

    # Choose formats using only uniform arithmetic scores, then exhaust the
    # fixed cross product of the best distinct formats.  This is the same
    # bounded refinement policy as h1355 and does not add operand conditions.
    uniform_best.sort()
    format_by_name = {fmt.name(): fmt for fmt in format_list}
    refinement_names = []
    for item in uniform_best:
        name = item[-1]
        if name not in refinement_names:
            refinement_names.append(name)
        if len(refinement_names) == args.refinement:
            break
    refined_pairs = []
    for mul_name in refinement_names:
        for add_name in refinement_names:
            if mul_name == add_name:
                continue
            mul_format = format_by_name[mul_name]
            add_format = format_by_name[add_name]
            scores, diagnostics = score_format(
                rows, magnitudes, mul_format, add_format)
            ranking.extend(scores)
            diagnostic_by_item.update(diagnostics)
            refined_pairs.append((mul_name, add_name))
        print("refined mul", mul_name, flush=True)

    ranking.sort()
    best = ranking[0]
    exact = [item for item in ranking if item[0] == 0]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        for index, path in enumerate(args.features):
            output.write(f"features_sha256.{index}\t{digest(path)}\n")
        output.write(
            "positive_allmode_sha256\t"
            + digest(args.positive_allmode) + "\n")
        output.write(
            "control_allmode_sha256\t"
            + digest(args.control_allmode) + "\n")
        output.write("hardware_policy\tcached_labels_only_no_x87_execution\n")
        output.write(
            "candidate_policy\tcomplete_graph_finite_signed_"
            "precision_difference_recurrence\n")
        output.write(f"constraining_rows\t{len(rows)}\n")
        output.write(f"unique_operands\t{len(magnitudes)}\n")
        output.write(
            f"targets\t{sum(prepared.target for prepared in rows)}\n")
        output.write(f"uniform_formats\t{len(format_list)}\n")
        output.write(f"refinement_formats\t{len(refinement_names)}\n")
        output.write(f"refined_pairs\t{len(refined_pairs)}\n")
        output.write(f"scored_programs\t{len(ranking)}\n")
        output.write(f"exact_programs\t{len(exact)}\n")
        output.write("difference_sign\tsigned_numeric_estimate_minus_stored\n")
        output.write("\n[ranking]\n")
        output.write(
            "errors\ttarget_errors\tcontrol_errors\tchanges\t"
            "predicted_ones\tsource\tgate\tmul_format\tadd_format\n")
        for item in ranking[:2048]:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[exact programs]\n")
        for item in exact:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[best target diagnostics]\n")
        output.write(
            "mode\top\tincumbent_carry\ttag_carry\toutput_carry\t"
            "allowed_carry\tmatch\n")
        for item in diagnostic_by_item[best]:
            output.write("\t".join(map(str, item)) + "\n")

    print(
        "wrote", args.report, "rows", len(rows),
        "programs", len(ranking), "exact", len(exact),
        "best", best, flush=True)


if __name__ == "__main__":
    main()
