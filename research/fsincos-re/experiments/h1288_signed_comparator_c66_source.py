#!/usr/bin/env python3
"""Test literal circuit wires as the carry-in to comparator column 66.

h1284 found that forcing carry-in zero at the signed comparator's column 66
changes the final dcc endpoint.  h1285 mistakenly interpreted that endpoint
as a two-bit recurrence beginning at column 64; dcc is insensitive to that
earlier mux and was consequently absent from h1286.  This audit uses the
actual h1284 boundary: the two conditional endpoints are the comparator high
part evaluated with carry-in 0 or 1 directly at column 66.

The incumbent endpoint is checked against the exact carry propagated from
column zero.  Only rows whose conditional endpoints differ constrain a
candidate source.  No hardware is executed and no operand threshold is fit.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
from pathlib import Path

import numpy as np

from h1129_r60_redundant_comparator_mine import (
    MASK,
    carry_between,
    less_with_carry,
    negate_rows,
    reduce_balanced,
)
from h1275_dcc_dense_structural_audit import SCOPE, TARGET
from h1284_signed_low_booth_square import signed_square
from h1285_signed_square_carry_source import square_wires


R1272_TARGET = "3ffc d80000000b15da62"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def comparator(row: dict[str, str], square_pair: tuple[int, int]):
    multiplier = int(row["tc_mul_sig"], 16)
    low3 = int(row["low3"])
    digit = low3 - 8 * int(low3 >= 4)
    carry_digit = int(low3 >= 4)
    sqlow = multiplier - (1 << 66)
    residue_mask = (1 << 67) - 1
    sum_residue = square_pair[0] & residue_mask
    carry_residue = square_pair[1] & residue_mask
    residue_total = sum_residue + carry_residue
    if (residue_total & residue_mask) != int(row["t4"], 16):
        raise AssertionError("signed square residue mismatch")

    rows = [digit * sqlow, carry_digit * (8 * sqlow)]
    rows.extend(negate_rows([sum_residue, carry_residue]))
    overflow = residue_total >> 67
    if overflow:
        rows.append(overflow << 67)
    base0 = (2 * low3 + 2 * int(row["b1"]) + 3 * int(row["b2"])
             - 3 * (low3 & 1) - 6)
    u0 = 2 * (base0 // 8) + (low3 & 1)
    threshold = u0 << 66
    rows.append((-threshold) & MASK)
    sum_vector, carry_vector = reduce_balanced(rows)

    mreg = int(row["Mreg"], 16)
    if mreg >> 127:
        mreg -= 1 << 128
    exact_less = int(mreg < threshold)
    exact_carry = carry_between(sum_vector, carry_vector, 0, 66, 0)
    represented_less = less_with_carry(
        sum_vector, carry_vector, exact_carry)
    if represented_less != exact_less:
        raise AssertionError("exact redundant comparator changed scalar result")
    endpoints = tuple(
        1 - less_with_carry(sum_vector, carry_vector, assumed)
        for assumed in (0, 1)
    )
    return endpoints, exact_carry, sum_vector, carry_vector


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
    vectors = []
    metadata = []
    frozen_rows = []
    total_rows = 0
    neutral_rows = 0
    target_seen = 0
    with gzip.open(args.features, "rt", newline="") as source:
        reader = csv.DictReader(source, delimiter="\t")
        for row in reader:
            if not all(row[name] == value for name, value in SCOPE.items()):
                continue
            label = labels[(row["corpus"], row["index"])]
            if label["selector_status"] != "constraining":
                continue
            total_rows += 1
            representation = signed_square(int(row["tc_mul_sig"], 16))
            endpoints, exact_carry, pair_sum, pair_carry = comparator(
                row, (representation[3], representation[4]))
            current = int(label["current_carry"])
            desired = int(label["allowed_carry"])
            if endpoints[exact_carry] != current:
                raise AssertionError(f"incumbent mismatch for {row['op']}")
            if endpoints[0] == endpoints[1]:
                neutral_rows += 1
                continue
            if row["op"] == R1272_TARGET:
                desired = current
            target = int(row["op"] == TARGET)
            target_seen += target

            values = square_wires(representation)
            for position in range(48, 72):
                values[f"comparator.sum.abs{position}"] = (
                    pair_sum >> position) & 1
                values[f"comparator.carry.abs{position}"] = (
                    pair_carry >> position) & 1
            if names is None:
                names = tuple(sorted(values))
            elif tuple(sorted(values)) != names:
                raise RuntimeError("candidate wire schema changed")
            vectors.append(np.fromiter(
                (values[name] for name in names), dtype=np.uint8,
                count=len(names)))
            metadata.append((
                row["op"], endpoints[0], endpoints[1], exact_carry,
                current, desired, target,
            ))
            if args.freeze is not None:
                frozen = dict(row)
                frozen.update({
                    "label": "POS" if target else "NEG",
                    "physical_status": "constraining",
                    "physical_label": str(desired),
                    "mux_endpoint0": str(endpoints[0]),
                    "mux_endpoint1": str(endpoints[1]),
                    "mux_exact_carry": str(exact_carry),
                    "mux_current": str(current),
                })
                frozen_rows.append(frozen)
            if total_rows % 10000 == 0:
                print(f"rows {total_rows} sensitive {len(metadata)}", flush=True)

    if names is None or not metadata:
        raise RuntimeError("no mux-sensitive rows")
    if target_seen != 1:
        raise RuntimeError(f"expected one sensitive dcc target, got {target_seen}")

    matrix = np.stack(vectors)
    endpoint0 = np.asarray([row[1] for row in metadata], dtype=np.uint8)
    endpoint1 = np.asarray([row[2] for row in metadata], dtype=np.uint8)
    exact_carry = np.asarray([row[3] for row in metadata], dtype=np.uint8)
    current = np.asarray([row[4] for row in metadata], dtype=np.uint8)
    desired = np.asarray([row[5] for row in metadata], dtype=np.uint8)
    targets = np.asarray([row[6] for row in metadata], dtype=bool)
    if np.any(np.where(exact_carry, endpoint1, endpoint0) != current):
        raise AssertionError("vectorized incumbent mismatch")

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
                int(np.count_nonzero(changed)), invert, name,
            ))
    scores.sort()
    exact = [score for score in scores if score[0] == 0]

    if args.freeze is not None:
        args.freeze.parent.mkdir(parents=True, exist_ok=True)
        first = frozen_rows[0]
        leading = (
            "label", "physical_status", "physical_label",
            "mux_endpoint0", "mux_endpoint1", "mux_exact_carry",
            "mux_current",
        )
        columns = leading + tuple(name for name in first if name not in leading)
        with args.freeze.open("x", newline="") as target_file:
            writer = csv.DictWriter(
                target_file, columns, delimiter="\t", extrasaction="ignore")
            writer.writeheader()
            writer.writerows(frozen_rows)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target_file:
        target_file.write(f"features_sha256\t{digest(args.features)}\n")
        target_file.write(f"labels_sha256\t{digest(args.labels)}\n")
        target_file.write("hardware_policy\tcached_labels_only_no_x87_execution\n")
        target_file.write("mux_boundary\tcomparator_column_66\n")
        target_file.write(f"rows\t{total_rows}\n")
        target_file.write(f"mux_neutral_rows\t{neutral_rows}\n")
        target_file.write(f"mux_sensitive_rows\t{len(metadata)}\n")
        target_file.write(f"candidate_wires\t{len(names)}\n")
        target_file.write(f"exact_single_wire_sources\t{len(exact)}\n")
        target_file.write(f"target_sensitive_rows\t{target_seen}\n")
        if args.freeze is not None:
            target_file.write(f"freeze_sha256\t{digest(args.freeze)}\n")
        target_file.write("composed_incumbent\tR1272 hard-3x carry\n")
        target_file.write("\n[ranking]\n")
        target_file.write(
            "errors\ttarget_miss\tcontrol_changes\tchanges\tinvert\twire\n")
        for score in scores[:3000]:
            target_file.write("\t".join(map(str, score)) + "\n")
        target_file.write("\n[exact single-wire sources]\n")
        for score in exact:
            target_file.write("\t".join(map(str, score)) + "\n")
        target_file.write("\n[sensitive target diagnostics]\n")
        target_file.write(
            "op\tendpoint0\tendpoint1\texact_carry\tcurrent\tdesired\n")
        for row in metadata:
            if row[6]:
                target_file.write("\t".join(map(str, row[:6])) + "\n")

    print(
        f"wrote {args.report} rows={total_rows} sensitive={len(metadata)} "
        f"wires={len(names)} exact={len(exact)} best={scores[0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
