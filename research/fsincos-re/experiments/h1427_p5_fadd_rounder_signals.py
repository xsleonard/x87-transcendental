#!/usr/bin/env python3
"""Audit the published P5 FADD-rounder signal history at R59.

Intel US5258943A describes a 68-bit FADD rounder that pre-normalizes from
the incoming overflow/J pair, computes rounding in parallel with padded-zero
and padded-one mantissas, and exposes an all-ones detector plus the carry out
of its 64-bit incrementer.  Earlier history audits included G/R/S, inexact,
rounding direction, retained low bits, and discarded-field classes, but not
the retained-field all-ones / incrementer-carry state.

This audit reconstructs the four causal Horner FADDs in the decoded cosine
schedule.  For every site it records the literal public signal family:
incoming 00/01/1x normalization class, the 1x displaced LSB, normalized
L/G/R/S, inexact, frrbit, frlmones, frhcout, rounding overflow, frojones, and
result-zero.  The operation is fixed to the already validated RN64 FADD
writeback; no precision, threshold, identity, interval, or tree is fitted.

Every global two-input Boolean composition with the incumbent R59 carry is
tested.  More strongly, rows are grouped by branch, incumbent carry, and the
complete stage-ordered public-signal tuple.  An opposite-label collision in
that tuple rules out every deterministic finite-state controller driven only
by these signals (with the fixed model schedule and initial state), not
merely the enumerated two-input gates.

All labels are immutable cached data.  The two d0d0 mode legs are reconstructed
from the current executable and assigned their already-proved carry-one
requirement.  No x87 instruction is executed.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import h1415_terminal_famubus_subtractor as h1415
import h1425_p5_public_mux_signals as h1425
import h206_p5_fadd_complete as h206
from h1110_carry_gate_mine import GATE_NAMES
from h1184_upstream_halfway_audit import (
    CONSTANTS,
    ExactOperation,
    Value,
    quantize,
    schedule,
)
from h1191_grs_history_isomorphism import compare_values


PATENT = "US5258943A"
PATENT_URL = "https://patents.google.com/patent/US5258943A/en"
FADD_STAGES = (
    "negative.add1",
    "positive.add1",
    "negative.add2",
    "positive.add2",
)
NOVEL_SUFFIXES = (
    "pre.case00_left",
    "pre.case01_asis",
    "pre.case1x_right",
    "pre.fr1xlsb",
    "frlmones",
    "frhcout",
    "round_overflow",
    "frojones",
    "frreszero",
)
MASK63 = (1 << 63) - 1
MASK64 = (1 << 64) - 1


@dataclass(frozen=True)
class PreparedRow:
    row: dict[str, str]
    current: int
    required: int
    target: bool
    signals: tuple[int, ...]


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def to_bus(value: Value) -> h206.Bus:
    return h1415.to_bus(value)


def fadd_inputs(
    row: dict[str, str],
) -> dict[str, tuple[Value, Value, ExactOperation]]:
    """Reconstruct the two already-materialized operands of each FADD."""
    operations = schedule(row)
    negative_mul1 = quantize(operations["negative.mul1"], 67, False)
    positive_mul1 = quantize(operations["positive.mul1"], 67, False)
    negative_add1 = quantize(operations["negative.add1"], 64, True)
    positive_add1 = quantize(operations["positive.add1"], 64, True)
    negative_mul2 = quantize(operations["negative.mul2"], 67, False)
    positive_mul2 = quantize(operations["positive.mul2"], 67, False)
    return {
        "negative.add1": (
            Value(*CONSTANTS[3]), negative_mul1, operations["negative.add1"]),
        "positive.add1": (
            Value(*CONSTANTS[4]), positive_mul1, operations["positive.add1"]),
        "negative.add2": (
            Value(*CONSTANTS[1]), negative_mul2, operations["negative.add2"]),
        "positive.add2": (
            Value(*CONSTANTS[2]), positive_mul2, operations["positive.add2"]),
    }


def stage_signals(
    row: dict[str, str],
    stage: str,
    left: Value,
    right: Value,
    operation: ExactOperation,
) -> tuple[dict[str, int], tuple[int, ...]]:
    """Return literal US5258943A signals for one RN64 FADD rounder."""
    raw, raw_trace = h206.fadd(
        to_bus(left), to_bus(right), "mark-after", normalize=False
    )
    normalized, normalized_trace = h206.fadd(
        to_bus(left), to_bus(right), "mark-after", normalize=True
    )
    if raw_trace.operation != "add" or normalized_trace.operation != "add":
        raise RuntimeError(f"non-add FADD at {stage} for {row['op']}")
    if normalized.word.bit_length() != 67:
        raise RuntimeError(f"unnormalized FRND input at {stage} for {row['op']}")

    expected = quantize(operation, 64, True)
    actual = h1415.from_bus(h206.materialize(normalized, "rn64"))
    if compare_values(actual, expected) != 0:
        raise RuntimeError(
            f"RN64 rounder reconstruction mismatch at {stage} for "
            f"{row['op']}: {actual=} {expected=}"
        )

    raw_case = (raw.word >> 66) & 3
    if raw_case not in (1, 2, 3):
        raise RuntimeError(
            f"unexpected pre-normalization case {raw_case:02b} at "
            f"{stage} for {row['op']}"
        )
    normalized_case = (normalized.word >> 66) & 3
    if normalized_case != 1:
        raise RuntimeError(
            f"bad normalized case {normalized_case:02b} at {stage} "
            f"for {row['op']}"
        )

    l_bit = (normalized.word >> 3) & 1
    guard = (normalized.word >> 2) & 1
    round_bit = (normalized.word >> 1) & 1
    sticky = normalized.word & 1
    inexact = int(bool(guard or round_bit or sticky))
    frrbit = guard & int(bool(round_bit or sticky or l_bit))

    retained = (normalized.word >> 3) & MASK64
    fraction = retained & MASK63
    frlmones = int(fraction == MASK63)
    # At extended precision frp1mnt is the normalized 64-bit retained field:
    # no lower retained bits are padded because L is bus bit 3.  The parallel
    # incrementer therefore carries out iff J and all 63 fraction bits are 1.
    frhcout = int(retained == MASK64)
    if frhcout != frlmones:
        raise RuntimeError("normalized J=1 did not equate frhcout/frlmones")

    values = {
        "pre.case00_left": int(raw_case == 0),
        "pre.case01_asis": int(raw_case == 1),
        "pre.case1x_right": int(bool(raw_case & 2)),
        "pre.fr1xlsb": int(bool(raw_case & 2) and bool(raw.word & 1)),
        "normalized.L": l_bit,
        "normalized.G": guard,
        "normalized.R": round_bit,
        "normalized.S": sticky,
        "inexact": inexact,
        "frrbit": frrbit,
        "frlmones": frlmones,
        "frhcout": frhcout,
        "round_overflow": frrbit & frhcout,
        "frojones": int(normalized_case == 3),
        "frreszero": int(not normalized.word),
    }
    trace = (
        raw_case,
        raw.word & 1,
        normalized.word & 7,
        retained,
        frrbit,
        frlmones,
        frhcout,
    )
    return values, trace


def rounder_signals(
    row: dict[str, str],
) -> tuple[dict[str, int], tuple[tuple[int, ...], ...]]:
    values: dict[str, int] = {}
    traces = []
    for stage, pair in fadd_inputs(row).items():
        local, trace = stage_signals(row, stage, *pair)
        values.update({f"{stage}.{name}": value for name, value in local.items()})
        traces.append(trace)
    return values, tuple(traces)


def gate_output(gate: int, current: int, signal: int) -> int:
    return (gate >> (2 * current + signal)) & 1


def prepare(args: argparse.Namespace) -> tuple[
    list[PreparedRow],
    list[dict[str, str]],
    tuple[str, ...],
    list[tuple[tuple[int, ...], ...]],
]:
    base, rows, _, _ = h1425.prepare(args)
    prepared = []
    names: tuple[str, ...] | None = None
    traces = []
    for item in base:
        values, trace = rounder_signals(item.row)
        traces.append(trace)
        if names is None:
            names = tuple(sorted(values))
        elif set(values) != set(names):
            raise RuntimeError("rounder signal schema changed")
        prepared.append(PreparedRow(
            row=item.row,
            current=item.current,
            required=item.required,
            target=item.target,
            signals=tuple(values[name] for name in names),
        ))
    if names is None:
        raise RuntimeError("no constraining rounder rows")
    return prepared, rows, names, traces


def collision_summary(
    prepared: list[PreparedRow],
    indices: tuple[int, ...] | None = None,
) -> tuple[list[tuple], int]:
    groups = defaultdict(lambda: [[], []])
    for item in prepared:
        signal_key = (
            item.signals if indices is None
            else tuple(item.signals[index] for index in indices)
        )
        key = (item.row["branch"], item.current, signal_key)
        groups[key][item.required].append(item)
    mixed = []
    targets_in_mixed = 0
    for key, members in groups.items():
        if not members[0] or not members[1]:
            continue
        targets = [item for side in members for item in side if item.target]
        targets_in_mixed += len(targets)
        mixed.append((
            key,
            len(members[0]),
            len(members[1]),
            tuple((item.row["mode"], item.row["op"]) for item in targets),
            (members[0][0].row["mode"], members[0][0].row["op"]),
            (members[1][0].row["mode"], members[1][0].row["op"]),
        ))
    return mixed, targets_in_mixed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("positive_allmode", type=Path)
    parser.add_argument("control_allmode", type=Path)
    parser.add_argument("model", type=Path)
    parser.add_argument("misses", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--extra-op", default=h1425.EXTRA_OP)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    prepared, rows, names, traces = prepare(args)
    target_count = sum(item.target for item in prepared)
    control_count = len(prepared) - target_count

    ranking = []
    for signal_index, name in enumerate(names):
        for gate in range(16):
            counts = Counter()
            for item in prepared:
                output = gate_output(gate, item.current, item.signals[signal_index])
                wrong = output != item.required
                changed = output != item.current
                counts["errors"] += wrong
                counts["target_errors"] += wrong and item.target
                counts["control_errors"] += wrong and not item.target
                counts["control_changes"] += changed and not item.target
            ranking.append((
                counts["errors"], counts["target_errors"],
                counts["control_errors"], counts["control_changes"],
                GATE_NAMES[gate], gate, name,
            ))
    ranking.sort()
    exact = [item for item in ranking if item[0] == 0]
    improvements = [
        item for item in ranking
        if item[2] == 0 and item[1] < target_count
    ]
    mixed, targets_in_mixed = collision_summary(prepared)

    signal_ones = Counter()
    for item in prepared:
        for name, value in zip(names, item.signals):
            signal_ones[name] += value
    novel_indices = tuple(
        index for index, name in enumerate(names)
        if name.endswith(NOVEL_SUFFIXES)
    )
    novel_names = tuple(names[index] for index in novel_indices)
    novel_varying = tuple(
        name for name in novel_names
        if 0 < signal_ones[name] < len(prepared)
    )
    novel_mixed, novel_targets_in_mixed = collision_summary(
        prepared, novel_indices
    )
    mixed_target_rows = {
        (mode, operand)
        for _, _, _, targets, _, _ in mixed
        for mode, operand in targets
    }
    unmatched_targets = sorted(
        (item.row["mode"], item.row["op"])
        for item in prepared
        if item.target
        and (item.row["mode"], item.row["op"]) not in mixed_target_rows
    )
    raw_case_counts = {
        stage: Counter(trace[index][0] for trace in traces)
        for index, stage in enumerate(FADD_STAGES)
    }
    allones_counts = {
        stage: Counter(trace[index][5] for trace in traces)
        for index, stage in enumerate(FADD_STAGES)
    }

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        for name, path in (
            ("features", args.features),
            ("positive_allmode", args.positive_allmode),
            ("control_allmode", args.control_allmode),
            ("model", args.model),
            ("misses", args.misses),
        ):
            output.write(f"{name}_sha256\t{digest(path)}\n")
        output.write("hardware_policy\timmutable_cached_labels_no_x87_execution\n")
        output.write(f"primary_source\t{PATENT}\t{PATENT_URL}\n")
        output.write(
            "candidate_policy\tliteral_US5258943A_causal_FADD_rounder_"
            "signal_history\n"
        )
        output.write("fadd_writeback\tRN64_fixed_validated_schedule\n")
        output.write(f"source_rows\t{len(rows)}\n")
        output.write(f"constraining_mode_rows\t{len(prepared)}\n")
        output.write(f"target_mode_rows\t{target_count}\n")
        output.write(f"control_mode_rows\t{control_count}\n")
        output.write(f"causal_fadd_stages\t{len(FADD_STAGES)}\n")
        output.write(f"public_signals\t{len(names)}\n")
        output.write(f"novel_metadata_signals\t{len(novel_names)}\n")
        output.write(f"novel_varying_signals\t{len(novel_varying)}\n")
        output.write(f"global_programs\t{len(ranking)}\n")
        output.write(f"exact_programs\t{len(exact)}\n")
        output.write(
            f"zero_control_collateral_improvements\t{len(improvements)}\n"
        )
        output.write(f"complete_history_mixed_groups\t{len(mixed)}\n")
        output.write(
            f"targets_in_complete_history_mixed_groups\t{targets_in_mixed}\n"
        )
        output.write(
            f"novel_metadata_mixed_groups\t{len(novel_mixed)}\n"
        )
        output.write(
            f"targets_in_novel_metadata_mixed_groups\t"
            f"{novel_targets_in_mixed}\n"
        )

        output.write("\n[public signal distribution]\n")
        output.write("signal\tones\tzeros\n")
        for name in names:
            output.write(
                f"{name}\t{signal_ones[name]}\t"
                f"{len(prepared) - signal_ones[name]}\n"
            )

        output.write("\n[novel metadata signals]\n")
        output.write("signal\tones\tzeros\n")
        for name in novel_names:
            output.write(
                f"{name}\t{signal_ones[name]}\t"
                f"{len(prepared) - signal_ones[name]}\n"
            )

        output.write("\n[pre-normalization case distribution]\n")
        output.write("stage\tcase\trows\n")
        for stage in FADD_STAGES:
            for value, count in sorted(raw_case_counts[stage].items()):
                output.write(f"{stage}\t{value:02b}\t{count}\n")

        output.write("\n[frlmones distribution]\n")
        output.write("stage\tfrlmones\trows\n")
        for stage in FADD_STAGES:
            for value, count in sorted(allones_counts[stage].items()):
                output.write(f"{stage}\t{value}\t{count}\n")

        output.write("\n[ranking]\n")
        output.write(
            "errors\ttarget_errors\tcontrol_errors\tcontrol_changes\t"
            "gate\tgate_mask\tsignal\n"
        )
        for item in ranking:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[complete history collision witnesses]\n")
        output.write(
            "branch\tcurrent_carry\tcarry0_rows\tcarry1_rows\t"
            "target_rows\tcarry0_example\tcarry1_example\n"
        )
        for key, zeros, ones, targets, zero_example, one_example in mixed:
            branch, current, _ = key
            target_text = ",".join(f"{mode}:{op}" for mode, op in targets)
            zero_text = f"{zero_example[0]}:{zero_example[1]}"
            one_text = f"{one_example[0]}:{one_example[1]}"
            output.write(
                f"{branch}\t{current}\t{zeros}\t{ones}\t{target_text}\t"
                f"{zero_text}\t{one_text}\n"
            )

        output.write("\n[targets without a complete-history collision]\n")
        output.write("mode\top\n")
        for mode, operand in unmatched_targets:
            output.write(f"{mode}\t{operand}\n")

        output.write("\n[result]\n")
        if not novel_varying and novel_targets_in_mixed == target_count:
            output.write(
                "new_US5258943_metadata_selector\t"
                "impossible_on_constrained_wall\n"
            )
            output.write(
                "new_metadata_reason\tall_novel_signals_are_stage_constant_"
                "and_every_target_collides_with_an_opposite_required_carry\n"
            )
        else:
            output.write(
                "new_US5258943_metadata_selector\t"
                "not_closed_by_metadata_collisions\n"
            )
        output.write(
            "complete_published_history_selector\t"
            "not_closed_by_complete_history_collisions\n"
        )
        output.write(
            f"complete_history_note\tthe_{len(unmatched_targets)}_"
            "noncolliding_targets_are_distinguished_only_by_previously_"
            "audited_LGRS_rounding_fields\n"
        )

    print(
        f"wrote {args.report}: rows={len(rows)} constrained={len(prepared)} "
        f"signals={len(names)} programs={len(ranking)} exact={len(exact)} "
        f"improvements={len(improvements)} mixed_targets={targets_in_mixed} "
        f"novel_varying={len(novel_varying)} "
        f"novel_mixed_targets={novel_targets_in_mixed} "
        f"best={ranking[0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
