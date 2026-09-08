#!/usr/bin/env python3
"""Test reconstructed rounding-history states on dense archived hard cells.

The h1178 development audit found that small patent-motivated history states
do not repair the nonmonotone R59 selector cells, while the full twelve-stage
class tuple nearly identifies individual development rows.  This script asks
the important held-out question: do those fixed history representations still
separate the required carry flips from dense controls selected from immutable
comb archives?

Each selected/label pair is consumed in lockstep.  Duplicate operands across
archives are counted once after their labels and reconstructed states agree.
No hardware instruction is executed and no capture artifact is modified.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

from h1178_round_history_state_audit import CELL, row_states, signed128


SCHEMES = (
    "terminal.class_pair",
    "terminal.class_and_fraction_order",
    "terminal.class_and_physical_order",
    "factor.class_pair",
    "factor.direction_pair",
    "horner.direction_tuple",
    "schedule.direction_tuple",
    "horner.class_tuple",
    "schedule.class_tuple",
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def new_summary() -> list[int | None]:
    # clean count/min/max, fire count/min/max
    return [0, None, None, 0, None, None]


def add_summary(summary: list[int | None], value: int, label: int) -> None:
    offset = 3 if label else 0
    summary[offset] = int(summary[offset]) + 1
    current_min = summary[offset + 1]
    current_max = summary[offset + 2]
    summary[offset + 1] = value if current_min is None else min(current_min, value)
    summary[offset + 2] = value if current_max is None else max(current_max, value)


def merge_summary(target: list[int | None], source: list[int | None]) -> None:
    for offset in (0, 3):
        target[offset] = int(target[offset]) + int(source[offset])
        if source[offset + 1] is None:
            continue
        if target[offset + 1] is None:
            target[offset + 1] = source[offset + 1]
            target[offset + 2] = source[offset + 2]
        else:
            target[offset + 1] = min(
                int(target[offset + 1]), int(source[offset + 1]))
            target[offset + 2] = max(
                int(target[offset + 2]), int(source[offset + 2]))


def is_separable(key: tuple[object, ...], summary: list[int | None]) -> bool:
    if not summary[0] or not summary[3]:
        return True
    theta = int(key[0])
    clean_min, clean_max = int(summary[1]), int(summary[2])
    fire_min, fire_max = int(summary[4]), int(summary[5])
    return fire_max < clean_min if theta >= 0 else clean_max < fire_min


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument(
        "pairs", nargs="+", metavar="SELECTED,LABELS",
        help="comma-separated h1168 selected gzip and h1169 labels TSV")
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    pairs = []
    for rendered in args.pairs:
        selected_text, separator, labels_text = rendered.partition(",")
        if not separator:
            raise SystemExit(f"bad pair (need SELECTED,LABELS): {rendered}")
        pairs.append((Path(selected_text), Path(labels_text)))

    # The state-only summaries test whether a history representation itself is
    # label-pure.  The cell summaries test the weaker and more plausible law:
    # one directional threshold in M for each visible digit cell and state.
    state_summaries = {
        name: defaultdict(new_summary) for name in SCHEMES
    }
    cell_summaries = {
        name: defaultdict(new_summary) for name in SCHEMES
    }
    physical_state_summaries = {
        name: defaultdict(new_summary) for name in SCHEMES
    }
    physical_cell_summaries = {
        name: defaultdict(new_summary) for name in SCHEMES
    }
    target_rows: dict[str, list[tuple[str, object, tuple[object, ...], int]]] = {
        name: [] for name in SCHEMES
    }
    impossible = []
    counts = Counter()
    seen: dict[bytes, tuple[str, int, tuple[object, ...]]] = {}

    for selected_path, labels_path in pairs:
        with gzip.open(selected_path, "rt", newline="") as selected_source, \
                labels_path.open(newline="") as label_source:
            selected_rows = csv.DictReader(selected_source, delimiter="\t")
            label_rows = csv.DictReader(label_source, delimiter="\t")
            pair_rows = 0
            for pair_rows, (row, label_row) in enumerate(
                    zip(selected_rows, label_rows), 1):
                if row["op"] != label_row["op"]:
                    raise RuntimeError(
                        f"row desync {selected_path}:{labels_path}:{pair_rows}")
                counts["archive_rows"] += 1
                operand = bytes.fromhex(row["op"])
                status = label_row["selector_status"]
                label = int(label_row["target_flip"])
                cell = tuple(int(row[field]) for field in CELL)
                prior = seen.get(operand)
                identity = (status, label, cell)
                if prior is not None:
                    if prior != identity:
                        raise RuntimeError(
                            f"duplicate disagreement for {row['op']}: "
                            f"{prior} != {identity}")
                    counts["duplicate_rows"] += 1
                    continue
                seen[operand] = identity
                counts["unique_rows"] += 1
                counts[f"status.{status}"] += 1
                if status == "unrepresented":
                    impossible.append(row["op"])
                    continue
                if status != "constraining":
                    continue

                states = row_states(row)
                value = signed128(row["Mreg"])
                carry = int(label_row["allowed_carry"])
                # The physical "fire" convention used by h1163 is the
                # nonzero endpoint displacement: carry=0 for theta>=0,
                # carry=1 for theta<0.
                physical_label = int(carry == (1 if cell[0] < 0 else 0))
                counts[f"constraining.label{label}"] += 1
                counts[f"physical.label{physical_label}"] += 1
                for name in SCHEMES:
                    state = states[name]
                    add_summary(state_summaries[name][state], value, label)
                    key = cell + (state,)
                    add_summary(cell_summaries[name][key], value, label)
                    add_summary(
                        physical_state_summaries[name][state],
                        value, physical_label)
                    add_summary(
                        physical_cell_summaries[name][key],
                        value, physical_label)
                    if label:
                        target_rows[name].append((row["op"], state, key, value))
                if counts["unique_rows"] % 100000 == 0:
                    print(
                        f"unique={counts['unique_rows']} "
                        f"targets={counts['constraining.label1']}", flush=True)

            try:
                next(selected_rows)
            except StopIteration:
                pass
            else:
                raise RuntimeError(f"extra selected rows in {selected_path}")
            try:
                next(label_rows)
            except StopIteration:
                pass
            else:
                raise RuntimeError(f"extra label rows in {labels_path}")
            counts[f"pair_rows.{selected_path.name}"] = pair_rows

    results = []
    diagnostics = {}
    for name in SCHEMES:
        state_groups = state_summaries[name]
        cell_groups = cell_summaries[name]
        state_mixed = sum(
            bool(summary[0] and summary[3]) for summary in state_groups.values())
        mixed = 0
        nonmonotone = 0
        fires_in_nonmonotone = 0
        for key, summary in cell_groups.items():
            if not summary[0] or not summary[3]:
                continue
            mixed += 1
            if not is_separable(key, summary):
                nonmonotone += 1
                fires_in_nonmonotone += int(summary[3])

        target_state_collisions = 0
        target_cell_collisions = 0
        target_nonmonotone = 0
        details = []
        for operand, state, key, value in target_rows[name]:
            state_summary = state_groups[state]
            cell_summary = cell_groups[key]
            state_collision = bool(state_summary[0])
            cell_collision = bool(cell_summary[0])
            nonmono = cell_collision and not is_separable(key, cell_summary)
            target_state_collisions += state_collision
            target_cell_collisions += cell_collision
            target_nonmonotone += nonmono
            details.append((
                operand, int(state_summary[0]), int(cell_summary[0]),
                int(nonmono), value, repr(state),
            ))
        diagnostics[name] = details
        results.append((
            target_nonmonotone,
            nonmonotone,
            target_cell_collisions,
            target_state_collisions,
            fires_in_nonmonotone,
            mixed,
            state_mixed,
            len(cell_groups),
            len(state_groups),
            name,
        ))
    results.sort()

    physical_results = []
    for name in SCHEMES:
        state_groups = physical_state_summaries[name]
        cell_groups = physical_cell_summaries[name]
        state_mixed = sum(
            bool(summary[0] and summary[3]) for summary in state_groups.values())
        mixed = 0
        nonmonotone = 0
        rows_in_nonmonotone = 0
        fires_in_nonmonotone = 0
        for key, summary in cell_groups.items():
            if not summary[0] or not summary[3]:
                continue
            mixed += 1
            if not is_separable(key, summary):
                nonmonotone += 1
                rows_in_nonmonotone += int(summary[0]) + int(summary[3])
                fires_in_nonmonotone += int(summary[3])
        physical_results.append((
            nonmonotone, rows_in_nonmonotone, fires_in_nonmonotone,
            mixed, state_mixed, len(cell_groups), len(state_groups), name,
        ))
    physical_results.sort()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        for index, (selected_path, labels_path) in enumerate(pairs):
            target.write(
                f"pair{index}_selected\t{selected_path}\t{digest(selected_path)}\n")
            target.write(
                f"pair{index}_labels\t{labels_path}\t{digest(labels_path)}\n")
        target.write("\n[counts]\n")
        for key, value in sorted(counts.items()):
            target.write(f"{key}\t{value}\n")
        target.write("unrepresented_operands\t" + ",".join(impossible) + "\n")
        target.write("\n[history collision and threshold audit]\n")
        target.write(
            "target_nonmonotone\tnonmonotone_groups\t"
            "target_cell_collisions\ttarget_state_collisions\t"
            "fires_in_nonmonotone\tmixed_cell_groups\tmixed_states\t"
            "cell_groups\tstates\tfeature\n")
        for result in results:
            target.write("\t".join(map(str, result)) + "\n")
        target.write("\n[physical carry/fire history audit]\n")
        target.write(
            "nonmonotone_groups\trows_in_nonmonotone\t"
            "fires_in_nonmonotone\tmixed_cell_groups\tmixed_states\t"
            "cell_groups\tstates\tfeature\n")
        for result in physical_results:
            target.write("\t".join(map(str, result)) + "\n")
        target.write("\n[target diagnostics]\n")
        target.write(
            "feature\top\tstate_controls\tcell_state_controls\t"
            "nonmonotone\tM\tstate\n")
        for result in results:
            name = result[-1]
            for detail in sorted(diagnostics[name]):
                target.write(name + "\t" + "\t".join(map(str, detail)) + "\n")

    best = results[0]
    print(
        f"wrote {args.report} unique={counts['unique_rows']} "
        f"targets={counts['constraining.label1']} "
        f"best_target_nonmonotone={best[0]} feature={best[-1]} "
        f"best_physical_nonmonotone={physical_results[0][0]} "
        f"physical_feature={physical_results[0][-1]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
