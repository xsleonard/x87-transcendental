#!/usr/bin/env python3
"""Test operation-remainder coordinates on exact stage-A neighborhoods.

The visible low/exact/high history class retains only one comparison bit from
each materialization.  This audit keeps the natural dyadic remainder of every
fixed P5 FMUL/FADD instead.  It tests two non-fitted representations:

* an unwrapped signed-M coordinate corrected by one normalized remainder or
  one normalized rounding error (and by fixed graph-wide sums); and
* small radix states made from the top 2..6 or bottom 1..8 remainder bits.

The operation graph, precisions, coefficients, and scalings are fixed by the
reconstructed kernel.  Hardware labels are consulted only when scoring
monotonicity inside the existing R59 digit cells.  A categorical state is
reported with the number of target-state controls so a unique-state lookup is
not mistaken for a structural result.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

from h1178_round_history_state_audit import CELL
from h1184_upstream_halfway_audit import STAGES, quantize, schedule
from h1196_reframed_history_partition import physical_deviation


ADD_STAGES = {
    "negative.add1", "negative.add2", "positive.add1", "positive.add2",
}
ONE = 1 << 66


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def signed128(text: str) -> int:
    value = int(text, 16)
    return value - (1 << 128) if value >> 127 else value


def operation_residues(row: dict[str, str]) -> dict[str, dict[str, object]]:
    result = {}
    for stage, operation in schedule(row).items():
        bits = 64 if stage in ADD_STAGES else 67
        nearest = stage in ADD_STAGES
        shift = max(0, operation.magnitude.bit_length() - bits)
        denominator = 1 << shift if shift else 1
        remainder = operation.magnitude & (denominator - 1) if shift else 0
        stored = quantize(operation, bits, nearest)
        floor_word = operation.magnitude >> shift if shift else operation.magnitude
        increment = stored.significand - floor_word
        if increment not in (0, 1):
            raise RuntimeError(f"unexpected increment at {stage}: {row['op']}")
        magnitude_error = Fraction(increment * denominator - remainder, denominator)
        numeric_error = -magnitude_error if operation.sign else magnitude_error
        result[stage] = {
            "remainder": remainder,
            "denominator": denominator,
            "fraction": Fraction(remainder, denominator),
            "magnitude_error": magnitude_error,
            "numeric_error": numeric_error,
        }
    return result


def nonmonotone(theta: int, entries: list[tuple[Fraction, int, str, bool]]) -> bool:
    fires = [value for value, label, _, _ in entries if label]
    cleans = [value for value, label, _, _ in entries if not label]
    if not fires or not cleans:
        return False
    return max(fires) >= min(cleans) if theta >= 0 else max(cleans) >= min(fires)


def score_groups(
    groups: dict[tuple[object, ...], list[tuple[Fraction, int, str, bool]]]
) -> tuple[int, int, int, int, int, int, int]:
    mixed = 0
    bad = 0
    bad_rows = 0
    target_bad = set()
    targets = set()
    target_with_control = set()
    target_control_rows = 0
    for key, entries in groups.items():
        labels = [label for _, label, _, _ in entries]
        controls = sum(not target for _, _, _, target in entries)
        group_targets = {operand for _, _, operand, target in entries if target}
        targets.update(group_targets)
        if controls:
            target_with_control.update(group_targets)
            if group_targets:
                target_control_rows += controls
        if any(labels) and not all(labels):
            mixed += 1
        if nonmonotone(int(key[0]), entries):
            bad += 1
            bad_rows += len(entries)
            target_bad.update(group_targets)
    return (
        bad, bad_rows, mixed, len(target_bad), len(targets),
        len(target_with_control), target_control_rows,
    )


def top_bits(remainder: int, denominator: int, bits: int) -> int:
    return (remainder << bits) // denominator


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rows", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    rows = []
    with args.rows.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            if row["physical_status"] == "constraining":
                rows.append(row)
    if not rows:
        raise SystemExit("no constraining rows")

    records = []
    for index, row in enumerate(rows, 1):
        residues = operation_residues(row)
        records.append({
            "row": row,
            "key": tuple(int(row[field]) for field in CELL),
            "M": Fraction(signed128(row["Mreg"])),
            "label": physical_deviation(row),
            "target": row["label"] == "POS",
            "residues": residues,
        })
        if index % 100 == 0:
            print(f"residues {index}/{len(rows)}", flush=True)

    coordinate_values: dict[str, list[Fraction]] = {}
    coordinate_values["materialized"] = [record["M"] for record in records]
    for stage in STAGES:
        for field in ("fraction", "magnitude_error", "numeric_error"):
            values = [record["residues"][stage][field] for record in records]
            for sign, suffix in ((1, "plus"), (-1, "minus")):
                coordinate_values[f"{stage}.{field}.{suffix}"] = [
                    record["M"] + sign * value * ONE
                    for record, value in zip(records, values)
                ]

    fixed_sets = {
        "all": STAGES,
        "adds": tuple(stage for stage in STAGES if stage in ADD_STAGES),
        "multiplies": tuple(stage for stage in STAGES if stage not in ADD_STAGES),
        "negative": tuple(stage for stage in STAGES if stage.startswith("negative")),
        "positive": tuple(stage for stage in STAGES if stage.startswith("positive")),
        "terminal": ("left", "right"),
    }
    for set_name, stages in fixed_sets.items():
        for field in ("magnitude_error", "numeric_error"):
            sums = [
                sum((record["residues"][stage][field] for stage in stages),
                    Fraction(0))
                for record in records
            ]
            for sign, suffix in ((1, "plus"), (-1, "minus")):
                coordinate_values[f"sum.{set_name}.{field}.{suffix}"] = [
                    record["M"] + sign * value * ONE
                    for record, value in zip(records, sums)
                ]

    coordinate_scores = []
    for name, values in coordinate_values.items():
        groups = defaultdict(list)
        for record, value in zip(records, values):
            groups[record["key"]].append((
                value, record["label"], record["row"]["op"], record["target"]
            ))
        coordinate_scores.append((*score_groups(groups), name))
    coordinate_scores.sort(key=lambda item: (item[:4], item[7]))

    partition_scores = []
    for stage in STAGES:
        for bits in range(2, 7):
            groups = defaultdict(list)
            states = set()
            for record in records:
                residue = record["residues"][stage]
                state = top_bits(
                    int(residue["remainder"]), int(residue["denominator"]), bits
                )
                states.add(state)
                groups[record["key"] + (state,)].append((
                    record["M"], record["label"], record["row"]["op"],
                    record["target"],
                ))
            partition_scores.append(
                (*score_groups(groups), len(states), f"{stage}.top{bits}")
            )
        for bits in range(1, 9):
            groups = defaultdict(list)
            states = set()
            for record in records:
                residue = record["residues"][stage]
                state = int(residue["remainder"]) & ((1 << bits) - 1)
                states.add(state)
                groups[record["key"] + (state,)].append((
                    record["M"], record["label"], record["row"]["op"],
                    record["target"],
                ))
            partition_scores.append(
                (*score_groups(groups), len(states), f"{stage}.bottom{bits}")
            )
    partition_scores.sort(
        key=lambda item: (item[:4], -item[5], -item[6], item[7], item[8])
    )

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target_file:
        target_file.write(f"rows_sha256\t{digest(args.rows)}\n")
        target_file.write(f"constraining_rows\t{len(rows)}\n")
        target_file.write(f"coordinate_candidates\t{len(coordinate_scores)}\n")
        target_file.write(f"partition_candidates\t{len(partition_scores)}\n")
        target_file.write("\n[unwrapped coordinate ranking]\n")
        target_file.write(
            "nonmonotone\tbad_rows\tmixed\ttarget_nonmonotone\ttargets\t"
            "target_with_control\ttarget_control_rows\tcoordinate\n"
        )
        for result in coordinate_scores:
            target_file.write("\t".join(map(str, result)) + "\n")
        target_file.write("\n[small radix partition ranking]\n")
        target_file.write(
            "nonmonotone\tbad_rows\tmixed\ttarget_nonmonotone\ttargets\t"
            "target_with_control\ttarget_control_rows\tstates\tfeature\n"
        )
        for result in partition_scores:
            target_file.write("\t".join(map(str, result)) + "\n")
        target_file.write("\n[target natural residues]\n")
        target_file.write(
            "op\tstage\tshift\ttop6\tbottom8\tboundary_distance\n"
        )
        for record in sorted(
            (item for item in records if item["target"]),
            key=lambda item: item["row"]["op"],
        ):
            for stage in STAGES:
                residue = record["residues"][stage]
                remainder = int(residue["remainder"])
                denominator = int(residue["denominator"])
                if stage in ADD_STAGES:
                    distance = remainder - denominator // 2
                else:
                    distance = min(remainder, remainder - denominator,
                                   key=abs)
                target_file.write(
                    f"{record['row']['op']}\t{stage}\t"
                    f"{denominator.bit_length() - 1}\t"
                    f"{top_bits(remainder, denominator, 6)}\t"
                    f"{remainder & 255}\t{distance}\n"
                )

    print(
        f"wrote {args.report} rows={len(rows)} "
        f"best_coordinate={coordinate_scores[0]} "
        f"best_partition={partition_scores[0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
