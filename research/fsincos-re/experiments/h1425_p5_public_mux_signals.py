#!/usr/bin/env python3
"""Audit the remaining published P5 multiplier/FADD mux signals at R59.

Intel US5260889A describes two multiplier sticky candidates computed in
parallel from the input trailing-zero counts.  For extended precision their
literal comparator constants are 0x45 and 0x46; product overflow selects the
0x46 (FMWFSTKV) candidate, while no overflow selects the 0x45 (FMWFSTKA)
candidate.  Intel US5257215A separately identifies exponent distance greater
than one as the FADD far-subtract path, and its FRND output can normalize by a
one-bit left shift.

This audit exposes exactly those public comparator, overflow, path, sticky,
and normalization mux signals for the two terminal FMULs, the terminal
``_FSUB``, and the final ``FINAL_ADD``.  It tests every global two-input Boolean
composition with the incumbent R59 carry and also performs a collision proof
on their complete joint tuple.  It does not mine arbitrary trailing-zero
thresholds, input identities, numeric intervals, or learned decision trees.

All hardware labels are immutable cached data.  The two d0d0 mode legs are
reconstructed from the current executable and assigned their already-proved
physical carry-one requirement.  No x87 instruction is executed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import h1415_terminal_famubus_subtractor as h1415
import h1424_subtract_final_add_interstage_carrier as h1424
import h206_p5_fadd_complete as h206
from h1110_carry_gate_mine import (
    GATE_NAMES,
    allmode_allowed,
    extract_carry_state,
)


EXTRA_OP = "3ffc d0d000000cc0b3f8"
STICKY_A_CONSTANT = 0x45
STICKY_V_CONSTANT = 0x46


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


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    if not rows:
        raise RuntimeError(f"empty feature bank: {path}")
    return rows


def trailing_zeros(value: int) -> int:
    if value <= 0:
        raise ValueError("trailing-zero input must be positive")
    return (value & -value).bit_length() - 1


def multiplier_signals(
    row: dict[str, str], left_name: str, right_name: str
) -> tuple[dict[str, int], tuple[int, int, int]]:
    left = h1415.row_value(row, left_name).significand
    right = h1415.row_value(row, right_name).significand
    if left.bit_length() != 67 or right.bit_length() != 64:
        raise RuntimeError(
            f"non-P5 FMUL port width for {row['op']}: "
            f"{left.bit_length()}x{right.bit_length()}"
        )
    count = trailing_zeros(left) + trailing_zeros(right)
    overflow = int((left * right).bit_length() == 131)
    sticky_a = int(count < STICKY_A_CONSTANT)
    sticky_v = int(count < STICKY_V_CONSTANT)
    selected = sticky_v if overflow else sticky_a
    return {
        "sticky_A": sticky_a,
        "sticky_V": sticky_v,
        "overflow": overflow,
        "selected_sticky": selected,
    }, (count, overflow, selected)


def final_add_signals(row: dict[str, str]) -> tuple[dict[str, int], tuple[int, int, int]]:
    one = h206.h200.normalized_bus((0, 1, 0))
    correction = h1424.incumbent_bus(row)
    if one.sign != 0 or correction.sign != 1:
        raise RuntimeError(f"unexpected FINAL_ADD operand signs for {row['op']}")
    exponent = max(one.exponent, correction.exponent)
    left, left_tail = h206.h200.shift_right(
        one.word << 1, exponent - one.exponent
    )
    right, right_tail = h206.h200.shift_right(
        correction.word << 1, exponent - correction.exponent
    )
    raw = left - right
    if raw <= 0:
        raise RuntimeError(f"nonpositive FINAL_ADD result for {row['op']}")
    top = raw.bit_length() - 1
    distance = abs(one.exponent - correction.exponent)
    outgoing_sticky = int(left_tail or right_tail)
    return {
        "far_path": int(distance > 1),
        "normalize_left1": int(top == 66),
        "aligned_tail_sticky": outgoing_sticky,
    }, (distance, top, outgoing_sticky)


def public_signals(row: dict[str, str]) -> tuple[dict[str, int], tuple[object, ...]]:
    left, left_trace = multiplier_signals(row, "mul", "lf")
    right, right_trace = multiplier_signals(row, "f4", "rf")
    final, final_trace = final_add_signals(row)
    terminal_distance = int(row["dist"])
    values = {
        **{f"left_fmul.{name}": value for name, value in left.items()},
        **{f"right_fmul.{name}": value for name, value in right.items()},
        "terminal_fsub.far_path": int(terminal_distance > 1),
        **{f"final_add.{name}": value for name, value in final.items()},
    }
    trace = (terminal_distance, left_trace, right_trace, final_trace)
    return values, trace


def gate_output(gate: int, current: int, signal: int) -> int:
    return (gate >> (2 * current + signal)) & 1


def prepare(args: argparse.Namespace) -> tuple[
    list[PreparedRow], list[dict[str, str]], tuple[str, ...], list[tuple[object, ...]]
]:
    rows = read_rows(args.features)
    h1424.append_extra_rows(rows, args.model, args.misses, args.extra_op)
    positive = allmode_allowed(args.positive_allmode)
    controls = allmode_allowed(args.control_allmode)

    prepared = []
    names: tuple[str, ...] | None = None
    traces = []
    for row in rows:
        values, trace = public_signals(row)
        traces.append(trace)
        if names is None:
            names = tuple(sorted(values))
        elif set(values) != set(names):
            raise RuntimeError("public signal schema changed")

        if row["op"] == args.extra_op:
            state = extract_carry_state(row, {0})
            allowed = {1}
        else:
            labels = positive if row["label"] == "POS" else controls
            state = extract_carry_state(row, labels[row["op"]])
            allowed = state[3]
        if len(allowed) != 1:
            continue
        prepared.append(PreparedRow(
            row=row,
            current=state[2],
            required=next(iter(allowed)),
            target=row["label"] == "POS",
            signals=tuple(values[name] for name in names),
        ))
    if names is None:
        raise RuntimeError("no public signals")
    return prepared, rows, names, traces


def collision_summary(prepared: list[PreparedRow]) -> tuple[list[tuple], int]:
    groups = defaultdict(lambda: [[], []])
    for item in prepared:
        key = (item.row["branch"], item.current, item.signals)
        groups[key][item.required].append(item)
    mixed = []
    target_in_mixed = 0
    for key, members in groups.items():
        if not members[0] or not members[1]:
            continue
        targets = [item for side in members for item in side if item.target]
        target_in_mixed += len(targets)
        mixed.append((
            key,
            len(members[0]),
            len(members[1]),
            tuple((item.row["mode"], item.row["op"]) for item in targets),
            (members[0][0].row["mode"], members[0][0].row["op"]),
            (members[1][0].row["mode"], members[1][0].row["op"]),
        ))
    return mixed, target_in_mixed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("positive_allmode", type=Path)
    parser.add_argument("control_allmode", type=Path)
    parser.add_argument("model", type=Path)
    parser.add_argument("misses", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--extra-op", default=EXTRA_OP)
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
    mixed, target_in_mixed = collision_summary(prepared)

    signal_ones = Counter()
    for item in prepared:
        for name, value in zip(names, item.signals):
            signal_ones[name] += value
    terminal_distances = Counter(trace[0] for trace in traces)
    left_tz = Counter(trace[1][0] for trace in traces)
    right_tz = Counter(trace[2][0] for trace in traces)
    final_classes = Counter(trace[3] for trace in traces)

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
        output.write(
            "candidate_policy\tliteral_US5260889_multiplier_sticky_mux_plus_"
            "US5257215_FADD_path_normalizer_signals\n"
        )
        output.write(f"source_rows\t{len(rows)}\n")
        output.write(f"constraining_mode_rows\t{len(prepared)}\n")
        output.write(f"target_mode_rows\t{target_count}\n")
        output.write(f"control_mode_rows\t{control_count}\n")
        output.write(f"public_signals\t{len(names)}\n")
        output.write(f"global_programs\t{len(ranking)}\n")
        output.write(f"exact_programs\t{len(exact)}\n")
        output.write(
            f"zero_control_collateral_improvements\t{len(improvements)}\n"
        )
        output.write(f"joint_mixed_groups\t{len(mixed)}\n")
        output.write(f"targets_in_joint_mixed_groups\t{target_in_mixed}\n")

        output.write("\n[public signal distribution]\n")
        output.write("signal\tones\tzeros\n")
        for name in names:
            output.write(
                f"{name}\t{signal_ones[name]}\t"
                f"{len(prepared) - signal_ones[name]}\n"
            )

        output.write("\n[structural trace distribution]\n")
        output.write("terminal_fsub_distance\trows\n")
        for value, count in sorted(terminal_distances.items()):
            output.write(f"{value}\t{count}\n")
        output.write("left_fmul_tzsum\trows\n")
        for value, count in sorted(left_tz.items()):
            output.write(f"{value}\t{count}\n")
        output.write("right_fmul_tzsum\trows\n")
        for value, count in sorted(right_tz.items()):
            output.write(f"{value}\t{count}\n")
        output.write("final_distance\tfinal_top\tfinal_tail_sticky\trows\n")
        for value, count in sorted(final_classes.items()):
            output.write("\t".join(map(str, (*value, count))) + "\n")

        output.write("\n[ranking]\n")
        output.write(
            "errors\ttarget_errors\tcontrol_errors\tcontrol_changes\t"
            "gate\tgate_mask\tsignal\n"
        )
        for item in ranking:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[joint collision witnesses]\n")
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

        output.write("\n[result]\n")
        output.write("public_mux_selector\timpossible_on_constrained_wall\n")
        output.write(
            "reason\topposite_required_carries_share_branch_current_carry_"
            "and_complete_public_mux_signal_tuple\n"
        )

    print(
        f"wrote {args.report}: rows={len(rows)} constrained={len(prepared)} "
        f"programs={len(ranking)} exact={len(exact)} "
        f"improvements={len(improvements)} mixed_targets={target_in_mixed} "
        f"best={ranking[0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
