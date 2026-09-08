#!/usr/bin/env python3
"""Test signed-square wires as the carry source of the dcc comparator mux.

h1284 identifies one natural alternate comparator endpoint: the conditional
two-bit result for columns 64..65 with carry-in zero.  It repairs dcc but is
not itself a selector.  This pass asks a stricter structural question: can a
single named wire from the radix-8 signed-low square drive that carry-select
mux directly over every sensitive row in the complete cached cell?

Only rows for which the two conditional endpoints differ constrain the mux.
All other rows are mathematically independent of the candidate carry source.
The already validated R1272 hard-3x correction is composed by leaving its one
fixed row at the incumbent endpoint.  No hardware is executed.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
from pathlib import Path

import numpy as np

from h1101_p5_tree_mine import carry_between as tree_carry_between
from h1129_r60_redundant_comparator_mine import (
    MASK,
    carry_between,
    less_with_carry,
    negate_rows,
    reduce_balanced,
)
from h1172_p5_cpa_predictor_mine import group_state
from h1275_dcc_dense_structural_audit import SCOPE, TARGET
from h1284_signed_low_booth_square import bit, signed_square


R1272_TARGET = "3ffc d80000000b15da62"
POSITIONS = range(44, 77)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def named_vector(values: dict[str, int], prefix: str,
                 sum_vector: int, carry_vector: int) -> None:
    exact_carry = 0
    carries = [0]
    for position in range(96):
        a = bit(sum_vector, position)
        b = bit(carry_vector, position)
        exact_carry = (a & b) | ((a ^ b) & exact_carry)
        carries.append(exact_carry)
    for position in POSITIONS:
        a = bit(sum_vector, position)
        b = bit(carry_vector, position)
        values[f"{prefix}.sum.abs{position}"] = a
        values[f"{prefix}.carry.abs{position}"] = b
        values[f"{prefix}.propagate.abs{position}"] = a ^ b
        values[f"{prefix}.generate.abs{position}"] = a & b
        values[f"{prefix}.kill.abs{position}"] = 1 ^ (a | b)
        values[f"{prefix}.cin.abs{position}"] = carries[position]
    for end in (60, 62, 63, 64, 65, 66, 67, 68, 70, 72):
        for width in (2, 4, 8, 16, 32):
            start = end - width
            state = group_state(sum_vector, carry_vector, start, end)
            for name, value in zip(
                    ("g", "p", "c0", "c1", "cin", "cout"), state):
                values[
                    f"{prefix}.group.end{end}.w{width:02d}.{name}"
                ] = value


def square_wires(representation) -> dict[str, int]:
    digit, carry_digit, high_state, square_sum, square_carry = representation
    values: dict[str, int] = {
        "digit.carry": carry_digit,
        "digit.negative": int(digit < 0),
        "digit.abs3": int(abs(digit) == 3),
        "digit.abs4": int(abs(digit) == 4),
    }
    named_vector(values, "merged", square_sum, square_carry)
    named_vector(values, "high", high_state["sum"], high_state["carry"])
    for node_name, node in high_state["nodes"].items():
        for vector_name in ("sum", "carry", "first_sum", "first_carry"):
            vector = node[vector_name]
            for position in POSITIONS:
                values[
                    f"high.{node_name}.{vector_name}.abs{position}"
                ] = bit(vector, position)
    for row_index, row_value in enumerate(high_state["rows"]):
        for position in POSITIONS:
            values[f"high.pp{row_index:02d}.abs{position}"] = bit(
                row_value, position)
    for row_index, booth_digit in enumerate(high_state["digits"]):
        values[f"high.booth{row_index:02d}.negative"] = int(booth_digit < 0)
        values[f"high.booth{row_index:02d}.zero"] = int(booth_digit == 0)
        values[f"high.booth{row_index:02d}.abs3"] = int(
            abs(booth_digit) == 3)
    return values


def endpoints(row: dict[str, str], square_pair: tuple[int, int]
              ) -> tuple[int, int, int]:
    multiplier = int(row["tc_mul_sig"], 16)
    low3 = int(row["low3"])
    digit = low3 - 8 * int(low3 >= 4)
    carry_digit = int(low3 >= 4)
    sqlow = multiplier - (1 << 66)
    linear_rows = [digit * sqlow, carry_digit * (8 * sqlow)]
    residue_mask = (1 << 67) - 1
    sum_residue = square_pair[0] & residue_mask
    carry_residue = square_pair[1] & residue_mask
    residue_total = sum_residue + carry_residue
    overflow = residue_total >> 67
    rows = list(linear_rows)
    rows.extend(negate_rows([sum_residue, carry_residue]))
    if overflow:
        rows.append(overflow << 67)
    base0 = (2 * low3 + 2 * int(row["b1"]) + 3 * int(row["b2"])
             - 3 * (low3 & 1) - 6)
    u0 = 2 * (base0 // 8) + (low3 & 1)
    rows.append((-(u0 << 66)) & MASK)
    sum_vector, carry_vector = reduce_balanced(rows)
    exact_in = carry_between(sum_vector, carry_vector, 0, 64, 0)
    result = []
    for assumed in (0, 1):
        carry = carry_between(sum_vector, carry_vector, 64, 66, assumed)
        result.append(1 - less_with_carry(sum_vector, carry_vector, carry))
    exact_out = result[exact_in]
    return result[0], result[1], exact_out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("labels", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--freeze", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")
    if args.freeze is not None and args.freeze.exists():
        raise SystemExit(f"refusing to overwrite {args.freeze}")

    with args.labels.open(newline="") as source:
        labels = {(row["corpus"], row["index"]): row
                  for row in csv.DictReader(source, delimiter="\t")}

    names = None
    feature_rows = []
    metadata = []
    frozen_rows = []
    total_rows = 0
    neutral_mux_rows = 0
    with gzip.open(args.features, "rt", newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            if not all(row[name] == value for name, value in SCOPE.items()):
                continue
            label = labels[(row["corpus"], row["index"])]
            if label["selector_status"] != "constraining":
                continue
            total_rows += 1
            representation = signed_square(int(row["tc_mul_sig"], 16))
            square_pair = (representation[3], representation[4])
            endpoint0, endpoint1, exact_out = endpoints(row, square_pair)
            current = int(label["current_carry"])
            desired = int(label["allowed_carry"])
            if exact_out != current:
                raise AssertionError(f"exact signed comparator mismatch {row['op']}")
            if endpoint0 == endpoint1:
                neutral_mux_rows += 1
                continue
            if row["op"] == R1272_TARGET:
                # The hard-3x carry is handled by the composed R1272 path;
                # this mux must not undo that independently validated result.
                desired = current
            values = square_wires(representation)
            if names is None:
                names = tuple(sorted(values))
            elif tuple(sorted(values)) != names:
                raise RuntimeError("signed-square wire schema changed")
            feature_rows.append(np.fromiter(
                (values[name] for name in names), dtype=np.uint8,
                count=len(names)))
            metadata.append((
                row["op"], endpoint0, endpoint1, current, desired,
                int(row["op"] == TARGET),
            ))
            if args.freeze is not None:
                frozen = dict(row)
                frozen.update({
                    "label": "POS" if row["op"] == TARGET else "NEG",
                    "physical_status": "constraining",
                    "physical_label": str(desired),
                    "mux_endpoint0": str(endpoint0),
                    "mux_endpoint1": str(endpoint1),
                    "mux_current": str(current),
                })
                frozen_rows.append(frozen)
            if total_rows % 10000 == 0:
                print(
                    f"rows {total_rows} sensitive {len(feature_rows)}",
                    flush=True,
                )
    if names is None:
        raise RuntimeError("no mux-sensitive rows")

    matrix = np.stack(feature_rows)
    endpoint0 = np.asarray([row[1] for row in metadata], dtype=np.uint8)
    endpoint1 = np.asarray([row[2] for row in metadata], dtype=np.uint8)
    current = np.asarray([row[3] for row in metadata], dtype=np.uint8)
    desired = np.asarray([row[4] for row in metadata], dtype=np.uint8)
    targets = np.asarray([row[5] for row in metadata], dtype=bool)
    scores = []
    for index, name in enumerate(names):
        for invert in (0, 1):
            selected = matrix[:, index] ^ invert
            predicted = np.where(selected, endpoint1, endpoint0)
            changed = predicted != current
            wrong = predicted != desired
            scores.append((
                int(np.count_nonzero(wrong)),
                int(np.count_nonzero(targets & ~changed)),
                int(np.count_nonzero((~targets) & changed)),
                int(np.count_nonzero(changed)),
                invert,
                name,
            ))
    scores.sort()
    exact = [score for score in scores if score[0] == 0]

    if args.freeze is not None:
        args.freeze.parent.mkdir(parents=True, exist_ok=True)
        first = frozen_rows[0]
        leading = (
            "label", "physical_status", "physical_label",
            "mux_endpoint0", "mux_endpoint1", "mux_current",
        )
        columns = leading + tuple(name for name in first if name not in leading)
        with args.freeze.open("x", newline="") as target:
            writer = csv.DictWriter(
                target, columns, delimiter="\t", extrasaction="ignore")
            writer.writeheader()
            writer.writerows(frozen_rows)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"features_sha256\t{digest(args.features)}\n")
        target.write(f"labels_sha256\t{digest(args.labels)}\n")
        target.write("hardware_policy\tcached_labels_only_no_x87_execution\n")
        target.write(f"rows\t{total_rows}\n")
        target.write(f"mux_neutral_rows\t{neutral_mux_rows}\n")
        target.write(f"mux_sensitive_rows\t{len(metadata)}\n")
        target.write(f"signed_square_wires\t{len(names)}\n")
        target.write(f"exact_single_wire_sources\t{len(exact)}\n")
        if args.freeze is not None:
            target.write(f"freeze_sha256\t{digest(args.freeze)}\n")
        target.write("composed_incumbent\tR1272 hard-3x carry\n")
        target.write("\n[ranking]\n")
        target.write(
            "errors\ttarget_miss\tcontrol_changes\tchanges\tinvert\twire\n")
        for score in scores[:2000]:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[exact single-wire sources]\n")
        for score in exact:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[sensitive target diagnostics]\n")
        target.write("op\tendpoint0\tendpoint1\tcurrent\tdesired\n")
        for row in metadata:
            if row[5]:
                target.write("\t".join(map(str, row[:5])) + "\n")

    print(
        f"wrote {args.report} rows={total_rows} sensitive={len(metadata)} "
        f"wires={len(names)} exact={len(exact)} best={scores[0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
