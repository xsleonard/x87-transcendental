#!/usr/bin/env python3
"""Audit LZA-relative carry blocks on the complete current R59 frontier.

h1416 exhausts carry-select blocks whose phase is fixed in the absolute
binary grid.  A normalization-coupled implementation permits one materially
different placement: the group boundaries may be relative to a leading-zero
anticipator, and therefore move with the redundantly represented terminal
result.  This experiment tests that bounded topology without fitting an
operand predicate.

For every literal fused-terminal representation inherited from h1128, the
candidate leading position is taken from one of the complete S/C result, the
unresolved S or C row, or the local OR/XOR/generate anticipator words.  Fixed
offsets -2..+2 cover the ordinary one-bit LZA correction and the adjacent
+0/+1/+2 rounding placements.  Carry blocks of width 4/8/16/32/64 are
anchored either on or immediately above that position, with a fixed zero or
one boundary seed.  Each resulting bit is composed with the incumbent carry
by one global two-input Boolean gate.

The separately tracked d0d0 row is reconstructed from the current executable
and appended with its all-mode-required carry=1 label.  Hardware is never
executed; all other labels come from the cached all-mode response banks.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from pathlib import Path

import numpy as np

from h1110_carry_gate_mine import (
    GATE_NAMES,
    allmode_allowed,
    extract_carry_state,
    gate_changes,
    gate_errors,
    state_bad_counts,
)
from h1128_fused_terminal_csa_mine import (
    MASK,
    WIDTH,
    bit,
    reduce_balanced,
    terminal_rows,
)
from h1386_current_r59_feature_bank import dump


BLOCK_WIDTHS = (4, 8, 16, 32, 64)
OFFSETS = range(-2, 3)
ANCHOR_EDGES = ("inclusive", "exclusive")


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


def leading_position(value: int) -> int:
    return value.bit_length() - 1


def anchors(sum_vector: int, carry_vector: int) -> dict[str, int]:
    total = (sum_vector + carry_vector) & MASK
    values = {
        "resolved": total,
        "sum": sum_vector,
        "carry": carry_vector,
        "or": sum_vector | carry_vector,
        "xor": sum_vector ^ carry_vector,
        "generate": sum_vector & carry_vector,
    }
    return {name: leading_position(value) for name, value in values.items()}


def prefix_carry(
    sum_vector: int,
    carry_vector: int,
    start: int,
    end: int,
    seed: int,
) -> int:
    carry = seed
    for position in range(max(0, start), end):
        left = bit(sum_vector, position)
        right = bit(carry_vector, position)
        carry = (left & right) | ((left ^ right) & carry)
    return carry


def row_columns(row: dict[str, str]) -> tuple[dict[str, int], Counter]:
    values: dict[str, int] = {}
    anchor_counts: Counter = Counter()
    for representation, (rows, _scale, cut) in terminal_rows(row).items():
        if not 0 <= cut < WIDTH:
            raise RuntimeError(f"invalid cut {cut} for {row['op']}")
        sum_vector, carry_vector, _ = reduce_balanced(rows)
        for anchor_name, anchor in anchors(sum_vector, carry_vector).items():
            anchor_counts[(representation, anchor_name, anchor)] += 1
            if anchor < 0:
                continue
            for edge in ANCHOR_EDGES:
                edge_position = anchor + int(edge == "exclusive")
                for offset in OFFSETS:
                    origin = edge_position + offset
                    for width in BLOCK_WIDTHS:
                        # Boundaries descend in fixed-width groups from the
                        # candidate leading edge.  Select the boundary at or
                        # immediately below the R59 cut.
                        start = cut - ((cut - origin) % width)
                        for seed in (0, 1):
                            name = (
                                f"{representation}.{anchor_name}.{edge}."
                                f"off{offset:+d}.w{width:02d}.seed{seed}"
                            )
                            values[name] = prefix_carry(
                                sum_vector, carry_vector, start, cut, seed
                            )
    return values, anchor_counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--positive-allmode", type=Path, required=True)
    parser.add_argument("--control-allmode", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--extra-op", default="3ffc d0d000000cc0b3f8")
    parser.add_argument("--extra-mode", default="rd")
    parser.add_argument("--extra-carry", type=int, choices=(0, 1), default=1)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    positive = allmode_allowed(args.positive_allmode)
    controls = allmode_allowed(args.control_allmode)
    rows = read_rows(args.features)
    if any(row["op"] == args.extra_op for row in rows):
        raise RuntimeError("extra operand is already in the feature bank")
    extra = dump(str(args.model), args.extra_mode, [args.extra_op])[0]
    extra.update({
        "label": "POS",
        "desired": f"carry{args.extra_carry}",
        "mode": args.extra_mode,
        "op": args.extra_op,
    })
    rows.append(extra)

    states = []
    names: list[str] | None = None
    matrix: np.ndarray | None = None
    anchor_counts: Counter = Counter()
    for index, row in enumerate(rows):
        if row["op"] == args.extra_op:
            s_value = int(row["S"], 16)
            b_value = int(row["B"], 16)
            mask = (1 << int(row["k"])) - 1
            borrow = int((s_value & mask) < (b_value & mask))
            allowed_delta = {borrow - 1 + args.extra_carry}
        else:
            labels = positive if row["label"] == "POS" else controls
            allowed_delta = labels[row["op"]]
        states.append(extract_carry_state(row, allowed_delta))

        columns, row_anchor_counts = row_columns(row)
        anchor_counts.update(row_anchor_counts)
        if names is None:
            names = sorted(columns)
            matrix = np.empty((len(rows), len(names)), dtype=np.uint8)
        elif set(columns) != set(names):
            raise RuntimeError("feature schema changed")
        assert matrix is not None and names is not None
        matrix[index] = [columns[name] for name in names]
        if (index + 1) % 1000 == 0:
            print(f"features {index + 1}/{len(rows)}", flush=True)

    assert matrix is not None and names is not None
    current = np.asarray([state[2] for state in states], dtype=np.uint8)
    allowed = np.asarray(
        [[carry in state[3] for carry in (0, 1)] for state in states],
        dtype=bool,
    )
    capable = allowed.any(axis=1)
    targets = np.asarray([row["label"] == "POS" for row in rows]) & capable
    controls_mask = (~targets) & capable
    groups = {"all": capable, "target": targets, "control": controls_mask}
    counts = {
        name: state_bad_counts(matrix, current, allowed, subset)
        for name, subset in groups.items()
    }

    ranking = []
    for gate in range(16):
        errors = {name: gate_errors(group, gate) for name, group in counts.items()}
        changes = gate_changes(matrix, current, controls_mask, gate)
        for column, feature in enumerate(names):
            ranking.append((
                int(errors["all"][column]),
                int(errors["target"][column]),
                int(errors["control"][column]),
                int(changes[column]),
                GATE_NAMES[gate],
                gate,
                feature,
            ))
    ranking.sort()
    nonidentity = [item for item in ranking if item[5] != 0xC]
    exact = [item for item in ranking if item[0] == 0]
    improvements = [
        item for item in nonidentity
        if item[2] == 0 and item[1] < int(targets.sum())
    ]

    distinct_anchors = Counter()
    for representation, anchor_name, anchor in anchor_counts:
        distinct_anchors[(representation, anchor_name)] += 1

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        for name, path in (
            ("features", args.features),
            ("positive_allmode", args.positive_allmode),
            ("control_allmode", args.control_allmode),
            ("model", args.model),
        ):
            output.write(f"{name}_sha256\t{digest(path)}\n")
        output.write("hardware_policy\tcached_labels_only_no_x87_execution\n")
        output.write(
            "candidate_policy\tliteral_fused_terminal_rows_"
            "LZA_relative_carry_blocks\n"
        )
        output.write(f"source_rows\t{len(rows)}\n")
        output.write(f"carry_capable\t{int(capable.sum())}\n")
        output.write(f"target_rows\t{int(targets.sum())}\n")
        output.write(f"extra_operand\t{args.extra_op}\n")
        output.write(f"extra_required_carry\t{args.extra_carry}\n")
        output.write(f"features\t{len(names)}\n")
        output.write(f"global_programs\t{len(ranking)}\n")
        output.write(f"exact_programs\t{len(exact)}\n")
        output.write(f"zero_collateral_improvements\t{len(improvements)}\n")
        output.write("\n[anchor cardinality]\n")
        output.write("representation\tanchor\tdistinct_positions\n")
        for (representation, anchor_name), count in sorted(
            distinct_anchors.items()
        ):
            output.write(f"{representation}\t{anchor_name}\t{count}\n")
        output.write("\n[best nonidentity]\n")
        output.write(
            "all_bad\ttarget_bad\tcontrol_bad\tcontrol_changes\tgate\t"
            "gate_mask\tfeature\n"
        )
        for item in nonidentity[:1000]:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[zero-collateral improvements]\n")
        for item in improvements[:2000]:
            output.write("\t".join(map(str, item)) + "\n")
        output.write("\n[zero-error programs]\n")
        for item in exact[:2000]:
            output.write("\t".join(map(str, item)) + "\n")

    print(
        f"wrote {args.report}: rows={len(rows)} features={len(names)} "
        f"programs={len(ranking)} exact={len(exact)} "
        f"improvements={len(improvements)} best={nonidentity[0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
