#!/usr/bin/env python3
"""Validate fixed low-three-bit operation-boundary states on dense archives.

The primary candidate is the final negative Horner FADD whose exact result is
halfway plus a nonzero residue confined to the three lowest discarded bits.
For completeness, the same fixed representation is enumerated at every named
FADD and chopped FMUL boundary.  Inputs and labels are immutable cached files;
the script executes no floating-point hardware instruction.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

from h1184_upstream_halfway_audit import STAGES, cut_state, schedule


ADD_STAGES = (
    "negative.add1", "negative.add2", "positive.add1", "positive.add2",
)
MUL_STAGES = tuple(stage for stage in STAGES if stage not in ADD_STAGES)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def boundary_states(row: dict[str, str]) -> set[str]:
    operations = schedule(row)
    states = set()
    for stage in ADD_STAGES:
        operation = operations[stage]
        shift = max(0, operation.magnitude.bit_length() - 64)
        if not shift:
            continue
        denominator = 1 << shift
        remainder = operation.magnitude & (denominator - 1)
        excess = remainder - (denominator >> 1)
        if 0 < excess < 8:
            states.add(f"{stage}.half_plus_low3")
        if -8 < excess < 0:
            states.add(f"{stage}.half_minus_low3")
        if excess == 0:
            states.add(f"{stage}.half_exact")
    for stage in MUL_STAGES:
        operation = operations[stage]
        shift = max(0, operation.magnitude.bit_length() - 67)
        if not shift:
            continue
        denominator = 1 << shift
        remainder = operation.magnitude & (denominator - 1)
        if 0 < remainder < 8:
            states.add(f"{stage}.floor_plus_low3")
        distance_from_ceiling = denominator - remainder
        if 0 < distance_from_ceiling < 8:
            states.add(f"{stage}.ceiling_minus_low3")
        if remainder == 0:
            states.add(f"{stage}.exact")
    return states


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("pairs", nargs="+", metavar="SELECTED,LABELS")
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    pairs = []
    for rendered in args.pairs:
        selected_text, separator, labels_text = rendered.partition(",")
        if not separator:
            raise SystemExit(f"bad pair: {rendered}")
        pairs.append((Path(selected_text), Path(labels_text)))

    counts = Counter()
    state_counts = defaultdict(Counter)
    state_targets = defaultdict(list)
    primary_rows = []
    seen = {}
    target_states = defaultdict(set)
    for selected_path, labels_path in pairs:
        with gzip.open(selected_path, "rt", newline="") as selected_source, \
                labels_path.open(newline="") as labels_source:
            selected_rows = csv.DictReader(selected_source, delimiter="\t")
            label_rows = csv.DictReader(labels_source, delimiter="\t")
            for ordinal, (row, label_row) in enumerate(
                    zip(selected_rows, label_rows), 1):
                if row["op"] != label_row["op"]:
                    raise RuntimeError(
                        f"row mismatch {selected_path}:{ordinal}")
                operand = row["op"]
                label = int(label_row["target_flip"])
                status = label_row["selector_status"]
                identity = (label, status)
                if operand in seen:
                    if seen[operand] != identity:
                        raise RuntimeError(f"duplicate disagreement: {operand}")
                    counts["duplicates"] += 1
                    continue
                seen[operand] = identity
                states = boundary_states(row)
                counts["unique"] += 1
                counts[f"label.{label}"] += 1
                counts[f"status.{status}"] += 1
                counts["any_state"] += bool(states)
                for state in states:
                    state_counts[state]["rows"] += 1
                    state_counts[state][f"label.{label}"] += 1
                    state_counts[state][f"status.{status}"] += 1
                    if label:
                        state_targets[state].append(operand)
                        target_states[operand].add(state)
                primary = "negative.add2.half_plus_low3"
                if primary in states:
                    operations = schedule(row)
                    add_operation = operations["negative.add2"]
                    add_shift = add_operation.magnitude.bit_length() - 64
                    add_denominator = 1 << add_shift
                    add_remainder = add_operation.magnitude & (add_denominator - 1)
                    mul_operation = operations["negative.mul2"]
                    mul_shift = mul_operation.magnitude.bit_length() - 67
                    mul_denominator = 1 << mul_shift
                    mul_remainder = mul_operation.magnitude & (mul_denominator - 1)
                    history = ",".join(
                        cut_state(
                            operations[stage],
                            64 if stage in ADD_STAGES else 67,
                        )[0]
                        for stage in STAGES
                    )
                    cell = ",".join(
                        row.get(name, "") for name in
                        ("theta", "ce", "s4", "side", "low3", "dist",
                         "rsh", "b1", "b2")
                    )
                    primary_rows.append((
                        operand, label, status,
                        add_remainder - (add_denominator >> 1), add_shift,
                        f"{mul_remainder:x}", f"{mul_denominator:x}",
                        history, cell,
                    ))
                if counts["unique"] % 100000 == 0:
                    print(
                        f"unique={counts['unique']} targets={counts['label.1']}",
                        flush=True,
                    )
            try:
                next(selected_rows)
            except StopIteration:
                pass
            else:
                raise RuntimeError(f"extra selected rows: {selected_path}")
            try:
                next(label_rows)
            except StopIteration:
                pass
            else:
                raise RuntimeError(f"extra label rows: {labels_path}")

    primary = "negative.add2.half_plus_low3"
    ordered_states = sorted(
        state_counts,
        key=lambda state: (
            state_counts[state]["label.0"],
            -state_counts[state]["label.1"], state,
        ),
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        for index, (selected_path, labels_path) in enumerate(pairs):
            target.write(
                f"pair{index}_selected\t{selected_path}\t{digest(selected_path)}\n"
            )
            target.write(
                f"pair{index}_labels\t{labels_path}\t{digest(labels_path)}\n"
            )
        target.write("\n[counts]\n")
        for name, value in sorted(counts.items()):
            target.write(f"{name}\t{value}\n")
        target.write("\n[fixed low3 boundary states]\n")
        target.write("state\trows\ttargets\tcontrols\tunrepresented\n")
        for state in ordered_states:
            values = state_counts[state]
            target.write(
                f"{state}\t{values['rows']}\t{values['label.1']}\t"
                f"{values['label.0']}\t{values['status.unrepresented']}\n"
            )
        target.write("\n[primary target operands]\n")
        target.write("op\n")
        for operand in sorted(state_targets[primary]):
            target.write(f"{operand}\n")
        target.write("\n[primary row diagnostics]\n")
        target.write(
            "op\tlabel\tstatus\tadd_excess\tadd_shift\t"
            "prior_mul_remainder\tprior_mul_denominator\t"
            "history_classes\tcell\n"
        )
        for entry in sorted(primary_rows):
            target.write("\t".join(map(str, entry)) + "\n")
        target.write("\n[all target states]\n")
        target.write("op\tstates\n")
        for operand in sorted(op for op, (label, _) in seen.items() if label):
            rendered = ",".join(sorted(target_states[operand])) or "-"
            target.write(f"{operand}\t{rendered}\n")

    values = state_counts[primary]
    print(
        f"wrote {args.report} unique={counts['unique']} "
        f"primary_targets={values['label.1']} "
        f"primary_controls={values['label.0']} "
        f"primary_unrepresented={values['status.unrepresented']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
