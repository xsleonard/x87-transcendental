#!/usr/bin/env python3
"""Audit every fixed absolute carry-block phase on literal terminal P5 rows.

h1128/h1396 carried the terminal products as literal P5 sum/carry rows, but
their carry-prefix observables were bounded to relative suffixes of at most 24
bits and the single zero-origin phase of 4/8/16-bit blocks.  This audit varies
the remaining physically bounded layout choice: one global absolute phase for
each 8/16/32/64-bit carry block, with a fixed zero or one boundary seed.

The arithmetic representations are inherited unchanged from h1128: resolved
terminal words, unresolved product S/C pairs, and all physical multiplier
input rows, aligned either at the materialized bus or at a common fine scale.
Every candidate is a global ``(representation, width, phase, seed, gate)``
program.  Labels are consulted only after all feature columns are generated.
There are no operand thresholds, branch-specific programs, identity keys, or
learned truth tables.  No x87 instruction is executed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
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
    WIDTH,
    bit,
    reduce_balanced,
    terminal_rows,
)


BLOCK_WIDTHS = (8, 16, 32, 64)


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


def row_columns(row: dict[str, str]) -> dict[str, int]:
    values: dict[str, int] = {}
    for representation, (rows, scale, cut) in terminal_rows(row).items():
        if not 0 <= cut < WIDTH:
            raise RuntimeError(f"invalid cut {cut} for {row['op']}")
        sum_vector, carry_vector, _ = reduce_balanced(rows)
        for width in BLOCK_WIDTHS:
            for phase in range(width):
                # ``phase`` names the absolute exponent residue of the block
                # boundary.  The boundary immediately below-or-at the target
                # cut is therefore a global layout choice, not a row fit.
                distance = (scale + cut - phase) % width
                start = cut - distance
                for seed in (0, 1):
                    name = (
                        f"{representation}.w{width:02d}.p{phase:02d}."
                        f"seed{seed}"
                    )
                    values[name] = prefix_carry(
                        sum_vector, carry_vector, start, cut, seed
                    )
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("positive_allmode", type=Path)
    parser.add_argument("control_allmode", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    positive = allmode_allowed(args.positive_allmode)
    controls = allmode_allowed(args.control_allmode)
    rows = read_rows(args.features)
    states = []
    names: list[str] | None = None
    matrix: np.ndarray | None = None
    for index, row in enumerate(rows):
        labels = positive if row["label"] == "POS" else controls
        states.append(extract_carry_state(row, labels[row["op"]]))
        columns = row_columns(row)
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
            ranking.append(
                (
                    int(errors["all"][column]),
                    int(errors["target"][column]),
                    int(errors["control"][column]),
                    int(changes[column]),
                    GATE_NAMES[gate],
                    gate,
                    feature,
                )
            )
    ranking.sort()
    nonidentity = [item for item in ranking if item[5] != 0xC]
    exact = [item for item in ranking if item[0] == 0]
    improvements = [
        item
        for item in nonidentity
        if item[2] == 0 and item[1] < int(targets.sum())
    ]

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write(f"features_sha256\t{digest(args.features)}\n")
        output.write(f"positive_allmode_sha256\t{digest(args.positive_allmode)}\n")
        output.write(f"control_allmode_sha256\t{digest(args.control_allmode)}\n")
        output.write("hardware_policy\tcached_labels_only_no_x87_execution\n")
        output.write(
            "candidate_policy\tliteral_fused_terminal_rows_fixed_absolute_"
            "block_phase\n"
        )
        output.write(f"rows\t{len(rows)}\n")
        output.write(f"carry_capable\t{int(capable.sum())}\n")
        output.write(f"targets\t{int(targets.sum())}\n")
        output.write(f"features\t{len(names)}\n")
        output.write(f"global_programs\t{len(ranking)}\n")
        output.write(f"exact_programs\t{len(exact)}\n")
        output.write(f"zero_collateral_improvements\t{len(improvements)}\n")
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
