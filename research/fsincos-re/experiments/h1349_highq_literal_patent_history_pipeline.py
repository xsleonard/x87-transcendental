#!/usr/bin/env python3
"""Replay the literal US5612909 per-value rounding-history rule.

The earlier history audits treated history as a generic global automaton or
as an arithmetic side channel.  The patent describes a narrower, structural
mechanism: a rounding direction remains attached to each result, the next
operation receives both source histories, and a microcode R bit enables an
override only when the current round-to-nearest result is exactly halfway.

This audit implements that dependency-local rule over the recovered negative
cosine Horner graph.  Constants and the input magnitude start exact.  Every
materialized result receives its immediate signed-numeric rounding direction
(-1 down, 0 exact, +1 up).  The two RN64 FADD sites independently receive a
fixed R-enable bit; the recovered chop67 FMUL sites still generate history but
cannot invoke the patent's RN exact-half table.  All four enable programs are
global microcode programs, with no operand predicates or fitted thresholds.

The signed-numeric convention is the literal patent candidate.  A separately
labelled magnitude-direction pass is included only as a sign-convention
sensitivity check, not as another claim about the patent.

Hardware labels are immutable one-shot inputs and this program executes no
x87 instruction.  An exact candidate would still require disjoint validation
and evidence that its R bits match the physical micro-operations.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

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
from h1316_highq_fixed_schedule_representations import load_direct


ADD_STAGES = ("negative.add1", "negative.add2")


@dataclass(frozen=True)
class HistoryValue:
    value: Value
    direction: int


@dataclass(frozen=True)
class RoundEvent:
    stage: str
    enabled: bool
    exact_half: bool
    overridden: bool
    left_history: int
    right_history: int
    output_history: int


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def direction(
        operation: ExactOperation, stored: Value, convention: str) -> int:
    exact = Value(operation.sign, operation.exponent, operation.magnitude)
    if convention == "numeric":
        return compare_values(stored, exact)
    if convention == "magnitude":
        delta = magnitude_delta(stored, exact)
        if delta is None:
            raise AssertionError("candidate changed operation sign")
        return (delta > 0) - (delta < 0)
    raise ValueError(convention)


def exact_half(operation: ExactOperation, bits: int) -> bool:
    shift = max(0, operation.magnitude.bit_length() - bits)
    if not shift:
        return False
    remainder = operation.magnitude & ((1 << shift) - 1)
    return remainder == 1 << (shift - 1)


def choose_direction(
        operation: ExactOperation, bits: int,
        wanted_direction: int, convention: str) -> Value:
    """Choose one of the two adjacent values around an exact halfway case."""
    candidates = (
        quantize_mode(operation, bits, "chop"),
        quantize_mode(operation, bits, "away"),
    )
    matches = [
        candidate for candidate in candidates
        if direction(operation, candidate, convention) == wanted_direction
    ]
    if len(matches) != 1:
        raise AssertionError(
            f"cannot choose direction {wanted_direction}: {matches}")
    return matches[0]


def materialize(
        stage: str, operation: ExactOperation, bits: int, mode: str,
        sources: tuple[HistoryValue, HistoryValue], enabled: bool,
        convention: str) -> tuple[HistoryValue, RoundEvent]:
    baseline = quantize_mode(operation, bits, mode)
    halfway = mode == "rn" and exact_half(operation, bits)
    active = {source.direction for source in sources if source.direction}
    overridden = enabled and halfway and len(active) == 1
    stored = baseline
    if overridden:
        stored = choose_direction(
            operation, bits, -next(iter(active)), convention)
    output_direction = direction(operation, stored, convention)
    return HistoryValue(stored, output_direction), RoundEvent(
        stage, enabled, halfway, overridden,
        sources[0].direction, sources[1].direction, output_direction,
    )


def exact_source(value: Value) -> HistoryValue:
    return HistoryValue(value, 0)


def negative_factor(
        row: dict[str, str], add_enable_mask: int,
        convention: str) -> tuple[Value, tuple[RoundEvent, ...]]:
    magnitude = exact_source(row_value(row, "mag"))
    constant1 = exact_source(Value(*CONSTANTS[1]))
    constant3 = exact_source(Value(*CONSTANTS[3]))
    constant5 = exact_source(Value(*CONSTANTS[5]))
    events = []

    square, event = materialize(
        "square", multiply(magnitude.value, magnitude.value), 67, "chop",
        (magnitude, magnitude), False, convention)
    events.append(event)
    fourth, event = materialize(
        "fourth", multiply(square.value, square.value), 67, "chop",
        (square, square), False, convention)
    events.append(event)
    mul1, event = materialize(
        "negative.mul1", multiply(fourth.value, constant5.value),
        67, "chop", (fourth, constant5), False, convention)
    events.append(event)
    add1, event = materialize(
        "negative.add1", add_same_sign(constant3.value, mul1.value),
        64, "rn", (constant3, mul1), bool(add_enable_mask & 1),
        convention)
    events.append(event)
    mul2, event = materialize(
        "negative.mul2", multiply(fourth.value, add1.value),
        67, "chop", (fourth, add1), False, convention)
    events.append(event)
    add2, event = materialize(
        "negative.add2", add_same_sign(constant1.value, mul2.value),
        64, "rn", (constant1, mul2), bool(add_enable_mask & 2),
        convention)
    events.append(event)
    return add2.value, tuple(events)


def mask_name(mask: int) -> str:
    active = [name for index, name in enumerate(ADD_STAGES)
              if mask & (1 << index)]
    return "+".join(active) if active else "history_disabled"


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
    diagnostics_by_candidate = {}
    event_counts_by_candidate = {}
    for convention in ("numeric", "magnitude"):
        for add_enable_mask in range(4):
            counts = Counter()
            event_counts = Counter()
            diagnostics = []
            for row in rows:
                candidate, events = negative_factor(
                    row, add_enable_mask, convention)
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
                counts[f"delta.{delta}"] += 1
                event_summary = []
                for event in events:
                    event_counts[f"{event.stage}.half"] += event.exact_half
                    event_counts[f"{event.stage}.override"] += event.overridden
                    if event.overridden:
                        event_summary.append(
                            f"{event.stage}:{event.left_history},"
                            f"{event.right_history}->{event.output_history}")
                diagnostics.append((
                    row["op"], wanted, predicted, delta,
                    sources[row["op"]],
                    ",".join(event_summary) if event_summary else "-",
                ))
            item = (
                counts["errors"], counts["positive_errors"],
                counts["negative_errors"], counts["predicted_positives"],
                counts["bank1.errors"], counts["bank0.errors"],
                convention, add_enable_mask, mask_name(add_enable_mask),
            )
            scores.append(item)
            diagnostics_by_candidate[(convention, add_enable_mask)] = diagnostics
            event_counts_by_candidate[(convention, add_enable_mask)] = event_counts
    scores.sort()
    exact = [item for item in scores if item[0] == 0]
    literal = next(
        item for item in scores
        if item[6] == "numeric" and item[7] == 3)
    best_key = (scores[0][6], scores[0][7])
    literal_key = (literal[6], literal[7])

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write(f"model_sha256\t{digest(args.model)}\n")
        for index, path in enumerate(args.direct_label):
            output.write(f"direct_labels_sha256.{index}\t{digest(path)}\n")
        output.write("hardware_policy\tfrozen_one_shot_labels_no_x87_execution\n")
        output.write(
            "candidate_policy\tliteral_per_value_US5612909_RN_halfway_history\n")
        output.write("history_scope\tattached_to_each_dependency_value\n")
        output.write("constant_and_input_history\texact\n")
        output.write("output_history\timmediate_actual_rounding_direction\n")
        output.write("literal_direction_convention\tsigned_numeric\n")
        output.write("magnitude_convention\tsensitivity_only\n")
        output.write(f"operands\t{len(rows)}\n")
        output.write(f"positive_operands\t{sum(labels.values())}\n")
        output.write("fixed_R_enable_programs\t4\n")
        output.write(f"scored_candidates\t{len(scores)}\n")
        output.write(f"exact_candidates\t{len(exact)}\n")
        output.write("stage_order\tsquare,fourth,negative.mul1,"
                     "negative.add1,negative.mul2,negative.add2\n")
        output.write("\n[ranking]\n")
        output.write(
            "errors\tpositive_errors\tnegative_errors\t"
            "predicted_positives\textension_errors\tolder_errors\t"
            "direction_convention\tR_mask\tR_enabled_stages\n")
        for item in scores:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[literal patent candidate]\n")
        output.write("\t".join(map(str, literal)) + "\n")
        output.write("\n[literal patent event counts]\n")
        for name, count in sorted(event_counts_by_candidate[literal_key].items()):
            output.write(f"{name}\t{count}\n")
        output.write("\n[best candidate event counts]\n")
        for name, count in sorted(event_counts_by_candidate[best_key].items()):
            output.write(f"{name}\t{count}\n")
        output.write("\n[best candidate diagnostics]\n")
        output.write(
            "op\twanted_wide\tpredicted_wide\tfactor_delta\tbank\t"
            "history_overrides\n")
        for diagnostic in diagnostics_by_candidate[best_key]:
            output.write("\t".join(map(str, diagnostic)) + "\n")

    print(
        f"wrote {args.report}: operands={len(rows)} "
        f"candidates={len(scores)} exact={len(exact)} "
        f"best={scores[0][:6]} literal={literal[:6]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
