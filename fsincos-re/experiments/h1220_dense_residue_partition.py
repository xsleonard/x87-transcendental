#!/usr/bin/env python3
"""Score fixed operation-remainder partitions on the dense stage-A wall.

The exact-neighborhood audit h1219 found several low-byte partitions that
separate its 316 rows.  That is weak evidence because a wide categorical
state can nearly identify each neighborhood row.  This cached-only audit
freezes the most informative h1219 predicates before looking at the dense
wall, then measures both directional M-threshold separability and the number
of real controls sharing every target state.

No hardware instruction is executed.  Labels come only from the immutable
h1214 classification of the archived h1213 operands.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

from h1178_round_history_state_audit import CELL, signed128
from h1184_upstream_halfway_audit import schedule


FEATURES = (
    ("negative.add2", "bottom", 8),
    ("negative.add1", "bottom", 8),
    ("right", "bottom", 8),
    ("left", "bottom", 8),
    ("left", "bottom", 7),
    ("negative.mul1", "top", 6),
    ("negative.add2", "top", 6),
    ("right", "top", 5),
    ("right", "top", 4),
)
ADD_STAGES = {
    "negative.add1", "negative.add2", "positive.add1", "positive.add2",
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def feature_name(spec: tuple[str, str, int]) -> str:
    stage, side, bits = spec
    return f"{stage}.{side}{bits}"


def new_summary() -> list[int | None]:
    # clean count/min/max, fire count/min/max
    return [0, None, None, 0, None, None]


def add_summary(summary: list[int | None], value: int, label: int) -> None:
    offset = 3 if label else 0
    summary[offset] = int(summary[offset]) + 1
    old_min = summary[offset + 1]
    old_max = summary[offset + 2]
    summary[offset + 1] = value if old_min is None else min(int(old_min), value)
    summary[offset + 2] = value if old_max is None else max(int(old_max), value)


def separable(key: tuple[object, ...], summary: list[int | None]) -> bool:
    if not summary[0] or not summary[3]:
        return True
    theta = int(key[0])
    clean_min, clean_max = int(summary[1]), int(summary[2])
    fire_min, fire_max = int(summary[4]), int(summary[5])
    return fire_max < clean_min if theta >= 0 else clean_max < fire_min


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("selected", type=Path)
    parser.add_argument("labels", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    names = tuple(feature_name(spec) for spec in FEATURES)
    state_summaries = {name: defaultdict(new_summary) for name in names}
    cell_summaries = {name: defaultdict(new_summary) for name in names}
    target_rows = {name: [] for name in names}
    counts = Counter()

    with gzip.open(args.selected, "rt", newline="") as selected_source, \
            args.labels.open(newline="") as label_source:
        selected_rows = csv.DictReader(selected_source, delimiter="\t")
        label_rows = csv.DictReader(label_source, delimiter="\t")
        for row_number, (row, label_row) in enumerate(
                zip(selected_rows, label_rows), 1):
            if row["op"] != label_row["op"]:
                raise RuntimeError(f"row desync at {row_number}")
            counts["archive_rows"] += 1
            status = label_row["selector_status"]
            counts[f"status.{status}"] += 1
            if status != "constraining":
                continue

            operations = schedule(row)
            cell = tuple(int(row[field]) for field in CELL)
            value = signed128(row["Mreg"])
            carry = int(label_row["allowed_carry"])
            # Nonzero physical endpoint displacement, matching h1179/h1196.
            physical_label = int(carry == (1 if cell[0] < 0 else 0))
            target = bool(int(label_row["target_flip"]))
            counts[f"physical.label{physical_label}"] += 1
            counts[f"target.{int(target)}"] += 1

            for spec, name in zip(FEATURES, names):
                stage, side, bits = spec
                operation = operations[stage]
                retained_bits = 64 if stage in ADD_STAGES else 67
                shift = max(0, operation.magnitude.bit_length() - retained_bits)
                denominator = 1 << shift if shift else 1
                remainder = operation.magnitude & (denominator - 1) if shift else 0
                if side == "top":
                    state = (remainder << bits) // denominator
                elif side == "bottom":
                    state = remainder & ((1 << bits) - 1)
                else:
                    raise AssertionError(side)
                key = cell + (state,)
                add_summary(state_summaries[name][state], value, physical_label)
                add_summary(cell_summaries[name][key], value, physical_label)
                if target:
                    target_rows[name].append((row["op"], state, key, value))

            if row_number % 100000 == 0:
                print(
                    f"rows={row_number} constraining={counts['target.0'] + counts['target.1']} "
                    f"targets={counts['target.1']}", flush=True,
                )

        try:
            next(selected_rows)
        except StopIteration:
            pass
        else:
            raise RuntimeError("selected file has extra rows")
        try:
            next(label_rows)
        except StopIteration:
            pass
        else:
            raise RuntimeError("label file has extra rows")

    results = []
    diagnostics = {}
    for name in names:
        states = state_summaries[name]
        groups = cell_summaries[name]
        mixed_states = sum(
            bool(summary[0] and summary[3]) for summary in states.values())
        mixed_groups = 0
        nonmonotone = 0
        rows_in_nonmonotone = 0
        fires_in_nonmonotone = 0
        for key, summary in groups.items():
            if not summary[0] or not summary[3]:
                continue
            mixed_groups += 1
            if not separable(key, summary):
                nonmonotone += 1
                rows_in_nonmonotone += int(summary[0]) + int(summary[3])
                fires_in_nonmonotone += int(summary[3])

        target_nonmonotone = 0
        target_state_collisions = 0
        target_group_collisions = 0
        details = []
        for operand, state, key, value in target_rows[name]:
            state_summary = states[state]
            group_summary = groups[key]
            state_controls = int(state_summary[0]) + int(state_summary[3]) - 1
            group_controls = int(group_summary[0]) + int(group_summary[3]) - 1
            nonmono = not separable(key, group_summary)
            target_nonmonotone += nonmono
            target_state_collisions += bool(state_controls)
            target_group_collisions += bool(group_controls)
            details.append((
                operand, state, state_controls, group_controls, int(nonmono),
                value, tuple(group_summary),
            ))
        diagnostics[name] = details
        results.append((
            target_nonmonotone, nonmonotone, target_group_collisions,
            target_state_collisions, rows_in_nonmonotone,
            fires_in_nonmonotone, mixed_groups, mixed_states,
            len(groups), len(states), name,
        ))
    results.sort()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target_file:
        target_file.write(f"selected\t{args.selected}\t{digest(args.selected)}\n")
        target_file.write(f"labels\t{args.labels}\t{digest(args.labels)}\n")
        target_file.write("hardware_policy\tcached_files_only_no_x87_execution\n")
        target_file.write("feature_policy\tfrozen_from_h1219_neighborhood_ranking\n")
        target_file.write("\n[counts]\n")
        for key, count in sorted(counts.items()):
            target_file.write(f"{key}\t{count}\n")
        target_file.write("\n[dense residue partition audit]\n")
        target_file.write(
            "target_nonmonotone\tnonmonotone_groups\t"
            "target_group_collisions\ttarget_state_collisions\t"
            "rows_in_nonmonotone\tfires_in_nonmonotone\tmixed_groups\t"
            "mixed_states\tgroups\tstates\tfeature\n"
        )
        for result in results:
            target_file.write("\t".join(map(str, result)) + "\n")
        target_file.write("\n[target diagnostics]\n")
        target_file.write(
            "feature\top\tstate\tstate_controls\tgroup_controls\t"
            "nonmonotone\tM\tgroup_summary\n"
        )
        for result in results:
            name = result[-1]
            for detail in sorted(diagnostics[name]):
                target_file.write(
                    name + "\t" + "\t".join(map(str, detail)) + "\n"
                )

    print(
        f"wrote {args.report} rows={counts['archive_rows']} "
        f"constraining={counts['target.0'] + counts['target.1']} "
        f"best={results[0]}", flush=True,
    )


if __name__ == "__main__":
    main()
