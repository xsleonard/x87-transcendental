#!/usr/bin/env python3
"""Audit the structural enable state behind the R1200 FADD changes.

R1200 applies a rounding-history response whenever a chopped multiply feeds a
same-sign RN64 add whose exact remainder is half through half plus four.  The
complete cached stage-A wall proves that response is not unconditional: some
changes repair hardware agreement and others regress it.  This experiment
reconstructs every changed operand, identifies the responsible Horner add,
and compares fixed producer/add representations (exact tail, GRS, jammed
sticky, and the literal FAMUBUS add).  It uses cached classifications and a
software internal dump only; it never executes an x87 instruction.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import h200_p5_fadd_bitvector as h200
import h206_p5_fadd_complete as h206
from h1210_stagea_residual_reframe import parse_dump, run
from h1184_upstream_halfway_audit import (
    CONSTANTS,
    ExactOperation,
    Value,
    add_same_sign,
    multiply,
    quantize,
    row_value,
    schedule,
)


ADD_STAGES = (
    ("negative.add1", 3, "negative.mul1"),
    ("negative.add2", 1, "negative.mul2"),
    ("positive.add1", 4, "positive.mul1"),
    ("positive.add2", 2, "positive.mul2"),
)


@dataclass(frozen=True)
class HValue:
    value: Value
    history: int


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def value_delta(left: Value, right: Value) -> int | None:
    """Return a magnitude delta in right-value ulps when integral."""
    if left.sign != right.sign:
        return None
    exponent = min(left.exponent, right.exponent)
    difference = (
        (left.significand << (left.exponent - exponent))
        - (right.significand << (right.exponent - exponent))
    )
    unit = 1 << (right.exponent - exponent)
    return difference // unit if difference % unit == 0 else None


def history_direction(operation: ExactOperation, stored: Value) -> int:
    """Return the signed numeric direction of stored relative to exact."""
    exact_exponent = operation.exponent
    common = min(exact_exponent, stored.exponent)
    exact = operation.magnitude << (exact_exponent - common)
    rounded = stored.significand << (stored.exponent - common)
    difference = rounded - exact
    if stored.sign:
        difference = -difference
    return (difference > 0) - (difference < 0)


def quantize_history(operation: ExactOperation, bits: int,
                     nearest: bool) -> HValue:
    stored = quantize(operation, bits, nearest)
    return HValue(stored, history_direction(operation, stored))


def cut_fields(operation: ExactOperation, bits: int) -> dict[str, object]:
    shift = max(0, operation.magnitude.bit_length() - bits)
    retained = operation.magnitude >> shift
    remainder = operation.magnitude & ((1 << shift) - 1) if shift else 0
    denominator = 1 << shift if shift else 1
    half = denominator >> 1 if shift else 0
    guard = (remainder >> (shift - 1)) & 1 if shift else 0
    round_bit = (remainder >> (shift - 2)) & 1 if shift >= 2 else 0
    sticky = int(bool(remainder & ((1 << max(0, shift - 2)) - 1))) \
        if shift >= 2 else 0
    if not remainder:
        fraction_class = "exact"
    elif remainder == denominator - 1:
        fraction_class = "all1"
    elif 2 * remainder < denominator:
        fraction_class = "low"
    elif 2 * remainder == denominator:
        fraction_class = "half"
    else:
        fraction_class = "high"
    return {
        "shift": shift,
        "retained": retained,
        "remainder": remainder,
        "denominator": denominator,
        "half_delta": remainder - half if shift else 0,
        "guard": guard,
        "round": round_bit,
        "sticky": sticky,
        "class": fraction_class,
    }


def history_add(constant: HValue, source: HValue,
                enabled: bool) -> tuple[HValue, dict[str, object]]:
    operation = add_same_sign(constant.value, source.value)
    ordinary = quantize_history(operation, 64, True)
    fields = cut_fields(operation, 64)
    lower = fields["retained"]
    toward_zero = 1 if operation.sign else -1
    active = (
        constant.history == toward_zero
        or source.history == toward_zero
    ) and not (
        constant.history == -toward_zero
        or source.history == -toward_zero
    )
    boundary = (
        fields["shift"] > 0
        and 0 <= fields["half_delta"] <= 4
        and ordinary.value.significand > lower
    )
    fires = bool(enabled and active and boundary)
    result = ordinary
    if fires:
        result = HValue(
            Value(
                ordinary.value.sign,
                ordinary.value.exponent,
                ordinary.value.significand - 1,
            ),
            toward_zero,
        )
    fields.update({
        "active_history": int(active),
        "boundary": int(boundary),
        "fires": int(fires),
        "ordinary_history": ordinary.history,
    })
    return result, fields


def scalar_schedule(row: dict[str, str], enabled: bool
                    ) -> tuple[dict[str, HValue], dict[str, dict[str, object]]]:
    magnitude = HValue(row_value(row, "mag"), 0)
    values: dict[str, HValue] = {"magnitude": magnitude}
    adds: dict[str, dict[str, object]] = {}

    values["square"] = quantize_history(
        multiply(magnitude.value, magnitude.value), 67, False)
    values["fourth"] = quantize_history(
        multiply(values["square"].value, values["square"].value), 67, False)

    values["negative.mul1"] = quantize_history(
        multiply(values["fourth"].value, Value(*CONSTANTS[5])), 67, False)
    values["negative.add1"], adds["negative.add1"] = history_add(
        HValue(Value(*CONSTANTS[3]), 0), values["negative.mul1"], enabled)
    values["negative.mul2"] = quantize_history(
        multiply(values["fourth"].value, values["negative.add1"].value),
        67, False)
    values["negative.add2"], adds["negative.add2"] = history_add(
        HValue(Value(*CONSTANTS[1]), 0), values["negative.mul2"], enabled)

    values["positive.mul1"] = quantize_history(
        multiply(values["fourth"].value, Value(*CONSTANTS[6])), 67, False)
    values["positive.add1"], adds["positive.add1"] = history_add(
        HValue(Value(*CONSTANTS[4]), 0), values["positive.mul1"], enabled)
    values["positive.mul2"] = quantize_history(
        multiply(values["fourth"].value, values["positive.add1"].value),
        67, False)
    values["positive.add2"], adds["positive.add2"] = history_add(
        HValue(Value(*CONSTANTS[2]), 0), values["positive.mul2"], enabled)
    return values, adds


def odd67(operation: ExactOperation) -> Value:
    stored = quantize(operation, 67, False)
    fields = cut_fields(operation, 67)
    if fields["remainder"]:
        return Value(stored.sign, stored.exponent, stored.significand | 1)
    return stored


def bus_value(value: Value) -> h200.Bus:
    return h200.normalized_bus(
        (value.sign, value.significand, value.exponent))


def from_bus(value: h200.Bus) -> Value:
    sign, significand, exponent = value.value()
    return Value(sign, exponent, significand)


def literal_add(constant: Value, source: Value, mode: str) -> Value:
    result, _ = h206.fadd(
        bus_value(constant), bus_value(source), mode, normalize=True)
    return from_bus(h206.materialize(result, "rn64"))


def read_changes(path: Path) -> tuple[dict[str, str], dict[str, list[str]]]:
    classifications: dict[str, str] = {}
    modes: dict[str, list[str]] = defaultdict(list)
    with path.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            operand = row["op"].lower()
            classification = row["classification"]
            if classification not in ("fix", "regression"):
                raise RuntimeError(f"unexpected classification {classification}")
            previous = classifications.setdefault(operand, classification)
            if previous != classification:
                raise RuntimeError(f"classification conflict for {operand}")
            modes[operand].append(row["mode"].lower())
    return classifications, modes


def feature_signature(event: dict[str, object], name: str) -> object:
    fields = {
        "stage": event["stage"],
        "source.low3": event["source_low3"],
        "source.grs": event["source_grs"],
        "producer.grs": event["producer_grs"],
        "producer.class": event["producer_class"],
        "producer.guard": event["producer_guard"],
        "producer.round": event["producer_round"],
        "producer.sticky": event["producer_sticky"],
        "producer.retained_lsb": event["producer_retained_lsb"],
        "add.half_delta": event["add_half_delta"],
        "add.retained_lsb": event["add_retained_lsb"],
        "odd67.delta": event["odd67_delta"],
        "bus_chop.delta": event["bus_chop_delta"],
        "bus_odd.delta": event["bus_odd_delta"],
    }
    if "+" not in name:
        return fields[name]
    return tuple(fields[part] for part in name.split("+"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("changes", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    classifications, modes = read_changes(args.changes)
    operands = sorted(classifications)
    _, stderr = run(args.model, "rn", operands, dump=True)
    rows = parse_dump(stderr, operands)

    events = []
    operand_diagnostics = []
    counts = Counter()
    for row in rows:
        operand = row["op"]
        classification = classifications[operand]
        # Verify the ordinary scalar schedule against the model dump before
        # using any reconstructed state as evidence.
        schedule(row)
        ordinary_values, ordinary_adds = scalar_schedule(row, False)
        history_values, history_adds = scalar_schedule(row, True)
        factor_changes = {
            chain: value_delta(
                history_values[f"{chain}.add2"].value,
                ordinary_values[f"{chain}.add2"].value,
            )
            for chain in ("negative", "positive")
        }
        fired = [name for name, fields in history_adds.items()
                 if fields["fires"]]
        if not fired:
            raise RuntimeError(f"R1200 changed output without a firing add: {operand}")
        counts[f"classification.{classification}"] += 1
        counts[f"firing_count.{len(fired)}"] += 1
        counts[f"factor_delta.{factor_changes['negative']}."
               f"{factor_changes['positive']}"] += 1
        operand_diagnostics.append((
            operand, classification, ",".join(sorted(set(modes[operand]))),
            ",".join(fired), factor_changes["negative"],
            factor_changes["positive"],
        ))

        baseline_operations = schedule(row)
        for stage, constant_index, producer_stage in ADD_STAGES:
            if not history_adds[stage]["fires"]:
                continue
            constant = Value(*CONSTANTS[constant_index])
            producer = baseline_operations[producer_stage]
            source = quantize(producer, 67, False)
            source_odd = odd67(producer)
            producer_cut = cut_fields(producer, 67)
            add_operation = add_same_sign(constant, source)
            add_cut = cut_fields(add_operation, 64)
            ordinary = quantize(add_operation, 64, True)
            scalar_odd = quantize(add_same_sign(constant, source_odd), 64, True)
            bus_chop = literal_add(constant, source, "mark-after")
            bus_odd = literal_add(constant, source_odd, "mark-after")
            event = {
                "op": operand,
                "classification": classification,
                "stage": stage,
                "source_low3": source.significand & 7,
                "source_grs": f"{(source.significand >> 2) & 1}"
                              f"{(source.significand >> 1) & 1}"
                              f"{source.significand & 1}",
                "producer_grs": f"{producer_cut['guard']}"
                                f"{producer_cut['round']}"
                                f"{producer_cut['sticky']}",
                "producer_class": producer_cut["class"],
                "producer_guard": producer_cut["guard"],
                "producer_round": producer_cut["round"],
                "producer_sticky": producer_cut["sticky"],
                "producer_retained_lsb": producer_cut["retained"] & 1,
                "producer_shift": producer_cut["shift"],
                "producer_remainder": producer_cut["remainder"],
                "producer_denominator": producer_cut["denominator"],
                "add_half_delta": add_cut["half_delta"],
                "add_retained_lsb": add_cut["retained"] & 1,
                "ordinary_sig": ordinary.significand,
                "odd67_delta": value_delta(scalar_odd, ordinary),
                "bus_chop_delta": value_delta(bus_chop, ordinary),
                "bus_odd_delta": value_delta(bus_odd, ordinary),
            }
            events.append(event)

    feature_names = (
        "stage", "source.low3", "source.grs", "producer.grs",
        "producer.class", "producer.guard", "producer.round",
        "producer.sticky", "producer.retained_lsb", "add.half_delta",
        "add.retained_lsb", "odd67.delta", "bus_chop.delta",
        "bus_odd.delta", "stage+source.grs", "stage+producer.grs",
        "stage+producer.class", "stage+add.half_delta",
        "source.grs+producer.grs", "source.grs+add.half_delta",
        "producer.grs+add.half_delta",
    )
    partitions = []
    for name in feature_names:
        groups: dict[object, Counter] = defaultdict(Counter)
        for event in events:
            groups[feature_signature(event, name)][event["classification"]] += 1
        mixed = sum(bool(group["fix"] and group["regression"])
                    for group in groups.values())
        rows_mixed = sum(sum(group.values()) for group in groups.values()
                         if group["fix"] and group["regression"])
        partitions.append((mixed, rows_mixed, len(groups), name, groups))
    partitions.sort(key=lambda item: (item[0], item[1], item[2], item[3]))

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"model_sha256\t{digest(args.model)}\n")
        target.write(f"changes_sha256\t{digest(args.changes)}\n")
        target.write("hardware_policy\tcached_change_labels_no_x87_execution\n")
        target.write(f"unique_operands\t{len(operands)}\n")
        target.write(f"firing_events\t{len(events)}\n")
        target.write("\n[counts]\n")
        for name, value in sorted(counts.items()):
            target.write(f"{name}\t{value}\n")
        target.write("\n[operand diagnostics]\n")
        target.write(
            "op\tclassification\tmodes\tfiring_adds\tnegative_factor_delta\t"
            "positive_factor_delta\n"
        )
        for diagnostic in operand_diagnostics:
            target.write("\t".join(map(str, diagnostic)) + "\n")
        target.write("\n[fixed structural partitions]\n")
        target.write("mixed_states\trows_in_mixed\tstates\tfeature\n")
        for mixed, rows_mixed, state_count, name, _ in partitions:
            target.write(f"{mixed}\t{rows_mixed}\t{state_count}\t{name}\n")
        target.write("\n[partition states]\n")
        target.write("feature\tstate\tfix\tregression\n")
        for _, _, _, name, groups in partitions:
            for state, group in sorted(groups.items(), key=lambda item: str(item[0])):
                target.write(
                    f"{name}\t{state}\t{group['fix']}\t{group['regression']}\n")
        target.write("\n[firing-event diagnostics]\n")
        target.write(
            "op\tclassification\tstage\tsource_low3\tsource_grs\t"
            "producer_grs\tproducer_class\tproducer_shift\t"
            "producer_remainder\tproducer_denominator\tadd_half_delta\t"
            "add_retained_lsb\todd67_delta\tbus_chop_delta\tbus_odd_delta\n"
        )
        for event in sorted(events, key=lambda item: (item["op"], item["stage"])):
            target.write("\t".join(map(str, (
                event["op"], event["classification"], event["stage"],
                event["source_low3"], event["source_grs"],
                event["producer_grs"], event["producer_class"],
                event["producer_shift"], f"{event['producer_remainder']:x}",
                f"{event['producer_denominator']:x}", event["add_half_delta"],
                event["add_retained_lsb"], event["odd67_delta"],
                event["bus_chop_delta"], event["bus_odd_delta"],
            ))) + "\n")

    best = partitions[0]
    print(
        f"wrote {args.report} operands={len(operands)} events={len(events)} "
        f"best={best[3]} mixed={best[0]} rows={best[1]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
