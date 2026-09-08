#!/usr/bin/env python3
"""Audit the P6-era 11/29/24-bit rounder carry outputs at R59.

Intel US5917741A describes an extended-precision 64-bit rounding incrementer
split into bits 10:0, 39:11, and 63:40.  When an extended-precision result is
incremented, carry-out 431 from the low 11 retained bits enables the middle
29-bit incrementer, and carry-out 433 from the middle slice enables the high
24-bit incrementer.  h1427 reconstructed the four causal Horner FADD
rounders, but retained only the full 64-bit incrementer carry.  This audit
closes the two source-defined internal-slice outputs omitted there.

For each fixed RN64 Horner FADD, ``carry11`` and ``carry40`` are reconstructed
literally from the validated retained mantissa and round-increment bit.  Every
global two-input Boolean composition with the incumbent R59 carry is scored.
More strongly, rows are grouped by branch, incumbent carry, and the complete
stage-ordered h1427 signal history plus these two carry outputs.  Opposite
labels in that complete tuple rule out every deterministic selector driven
only by this public signal family, not merely the enumerated gates.

The patent describes architectural-format rounding, not a proved Skylake
transcendental implementation.  This script therefore treats the signals as
a source-anchored hypothesis only.  Labels are immutable cached data, and no
x87 instruction is executed.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

import h1425_p5_public_mux_signals as h1425
import h1427_p5_fadd_rounder_signals as h1427
from h1110_carry_gate_mine import GATE_NAMES


PATENT = "US5917741A"
PATENT_URL = "https://patents.google.com/patent/US5917741A/en"
LOW11_MASK = (1 << 11) - 1
LOW40_MASK = (1 << 40) - 1


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def slice_signals(
    traces: list[tuple[tuple[int, ...], ...]],
) -> tuple[tuple[str, ...], list[tuple[int, ...]]]:
    names = tuple(
        f"{stage}.{signal}"
        for stage in h1427.FADD_STAGES
        for signal in ("carry11", "carry40")
    )
    rows = []
    for history in traces:
        values = []
        for trace in history:
            retained = trace[3]
            round_increment = trace[4]
            carry11 = int(
                bool(round_increment) and (retained & LOW11_MASK) == LOW11_MASK
            )
            carry40 = int(
                bool(round_increment) and (retained & LOW40_MASK) == LOW40_MASK
            )
            if carry40 and not carry11:
                raise RuntimeError("middle-slice carry without low-slice carry")
            values.extend((carry11, carry40))
        rows.append(tuple(values))
    return names, rows


def gate_output(gate: int, current: int, signal: int) -> int:
    return (gate >> (2 * current + signal)) & 1


def collision_summary(
    prepared: list[h1427.PreparedRow],
    slice_rows: list[tuple[int, ...]],
    combined: bool,
) -> tuple[list[tuple], int]:
    groups = defaultdict(lambda: [[], []])
    for item, slices in zip(prepared, slice_rows):
        history = item.signals + slices if combined else slices
        key = (item.row["branch"], item.current, history)
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

    prepared, source_rows, base_names, traces = h1427.prepare(args)
    names, slice_rows = slice_signals(traces)
    if len(slice_rows) != len(prepared):
        raise RuntimeError("slice history row count mismatch")

    target_count = sum(item.target for item in prepared)
    control_count = len(prepared) - target_count
    ranking = []
    ones = Counter()
    for signal_index, name in enumerate(names):
        ones[name] = sum(row[signal_index] for row in slice_rows)
        for gate in range(16):
            counts = Counter()
            for item, signals in zip(prepared, slice_rows):
                output = gate_output(gate, item.current, signals[signal_index])
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
    slice_mixed, slice_targets_in_mixed = collision_summary(
        prepared, slice_rows, combined=False
    )
    combined_mixed, combined_targets_in_mixed = collision_summary(
        prepared, slice_rows, combined=True
    )

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
            "source_scope\tpatent_embodiment_not_proved_Skylake_topology\n"
        )
        output.write(
            "candidate_policy\tliteral_11_29_24_rounder_slice_carry_outputs\n"
        )
        output.write("fadd_writeback\tRN64_fixed_validated_schedule\n")
        output.write(f"source_rows\t{len(source_rows)}\n")
        output.write(f"constraining_mode_rows\t{len(prepared)}\n")
        output.write(f"target_mode_rows\t{target_count}\n")
        output.write(f"control_mode_rows\t{control_count}\n")
        output.write(f"causal_fadd_stages\t{len(h1427.FADD_STAGES)}\n")
        output.write(f"inherited_h1427_signals\t{len(base_names)}\n")
        output.write(f"slice_carry_signals\t{len(names)}\n")
        output.write(f"varying_slice_carry_signals\t{sum(0 < ones[name] < len(prepared) for name in names)}\n")
        output.write(f"global_programs\t{len(ranking)}\n")
        output.write(f"exact_programs\t{len(exact)}\n")
        output.write(
            f"zero_control_collateral_improvements\t{len(improvements)}\n"
        )
        output.write(f"slice_history_mixed_groups\t{len(slice_mixed)}\n")
        output.write(
            f"targets_in_slice_history_mixed_groups\t{slice_targets_in_mixed}\n"
        )
        output.write(
            f"combined_history_mixed_groups\t{len(combined_mixed)}\n"
        )
        output.write(
            "targets_in_combined_history_mixed_groups\t"
            f"{combined_targets_in_mixed}\n"
        )

        output.write("\n[slice signal distribution]\n")
        output.write("signal\tones\tzeros\n")
        for name in names:
            output.write(
                f"{name}\t{ones[name]}\t{len(prepared) - ones[name]}\n"
            )

        output.write("\n[ranking]\n")
        output.write(
            "errors\ttarget_errors\tcontrol_errors\tcontrol_changes\t"
            "gate\tgate_mask\tsignal\n"
        )
        for item in ranking:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[zero-collateral improvements]\n")
        for item in improvements:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[zero-error programs]\n")
        for item in exact:
            output.write("\t".join(map(str, item)) + "\n")

        output.write("\n[combined-history mixed groups]\n")
        output.write(
            "branch\tcurrent\thistory\trequired0\trequired1\ttargets\t"
            "example0\texample1\n"
        )
        for key, count0, count1, targets, example0, example1 in combined_mixed:
            branch, current, history = key
            output.write(
                f"{branch}\t{current}\t"
                + ",".join(map(str, history))
                + f"\t{count0}\t{count1}\t{targets}\t{example0}\t{example1}\n"
            )

    print(
        f"wrote {args.report}: rows={len(prepared)} "
        f"slice_signals={len(names)} exact={len(exact)} "
        f"improvements={len(improvements)} "
        f"combined_collision_targets={combined_targets_in_mixed}",
        flush=True,
    )


if __name__ == "__main__":
    main()
