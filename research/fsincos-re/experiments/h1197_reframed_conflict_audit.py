#!/usr/bin/env python3
"""Expose the remaining R1186 terminal conflicts and test scalar histories.

The R1186-corrected upper surface has five nonmonotone digit cells.  This
cached-row audit reports every order-reversing fire/clean pair in those cells
and scores small, fixed arithmetic summaries of the Horner rounding history.
It does not execute hardware and does not synthesize a categorical lookup.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import defaultdict
from pathlib import Path

from h1178_round_history_state_audit import CELL, monotonicity, signed128
from h1196_reframed_history_partition import (
    physical_deviation,
    row_histories,
    row_states,
)


HORNER = (
    "odd_p1", "even_p1", "odd_a1", "even_a1",
    "odd_p2", "even_p2", "odd_a2", "even_a2",
)
ADDS = ("odd_a1", "even_a1", "odd_a2", "even_a2")
CLASS_CODE = {"exact": 0, "low": -1, "half": 0, "high": 1, "all1": 2}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def class_symbol(value: str) -> str:
    return {
        "exact": "E", "low": "L", "half": "T", "high": "H",
        "all1": "A",
    }[value]


def history_text(histories: dict[str, dict[str, object]]) -> tuple[str, str]:
    classes = "".join(class_symbol(str(histories[name]["class"]))
                      for name in HORNER)
    directions = "".join({-1: "-", 0: "0", 1: "+"}[
        int(histories[name]["direction"])] for name in HORNER)
    return classes, directions


def scalar_states(histories: dict[str, dict[str, object]]) -> dict[str, int]:
    directions = [int(histories[name]["direction"]) for name in ADDS]
    classes = [CLASS_CODE[str(histories[name]["class"])] for name in ADDS]
    odd_directions = directions[0::2]
    even_directions = directions[1::2]
    odd_classes = classes[0::2]
    even_classes = classes[1::2]
    states = {
        "add.direction_sum": sum(directions),
        "add.direction_alt_sum": sum(
            value if index % 2 == 0 else -value
            for index, value in enumerate(directions)),
        "add.direction_late2": sum(
            value << index for index, value in enumerate(directions)),
        "add.class_sum": sum(classes),
        "add.class_alt_sum": sum(
            value if index % 2 == 0 else -value
            for index, value in enumerate(classes)),
        "branch.direction_sum_difference": (
            sum(odd_directions) - sum(even_directions)),
        "branch.class_sum_difference": sum(odd_classes) - sum(even_classes),
    }
    for name in ADDS:
        history = histories[name]
        shift = int(history["shift"])
        remainder = int(history["remainder"])
        if not shift:
            centered_q16 = 0
            centered_q66 = 0
        else:
            centered_q16 = ((2 * remainder - (1 << shift)) << 16) // (1 << shift)
            centered_q66 = ((2 * remainder - (1 << shift)) << 66) // (1 << shift)
        states[f"{name}.centered_q16"] = centered_q16
        states[f"{name}.centered_q66"] = centered_q66
    states["add.centered_q16_sum"] = sum(
        states[f"{name}.centered_q16"] for name in ADDS)
    states["branch.centered_q16_difference"] = (
        states["odd_a1.centered_q16"] + states["odd_a2.centered_q16"]
        - states["even_a1.centered_q16"] - states["even_a2.centered_q16"])
    states["add.centered_q66_sum"] = sum(
        states[f"{name}.centered_q66"] for name in ADDS)
    states["branch.centered_q66_difference"] = (
        states["odd_a1.centered_q66"] + states["odd_a2.centered_q66"]
        - states["even_a1.centered_q66"] - states["even_a2.centered_q66"])
    return states


def is_reversed(theta: int, fire_m: int, clean_m: int) -> bool:
    return fire_m >= clean_m if theta >= 0 else clean_m >= fire_m


def scale_integer(value: int, shift: int) -> int:
    return value << shift if shift >= 0 else value // (1 << -shift)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rows", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    records = []
    groups = defaultdict(list)
    with args.rows.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            if row["physical_status"] != "constraining":
                continue
            key = tuple(int(row[field]) for field in CELL)
            histories = row_histories(row)
            states = row_states(row)
            states.update(scalar_states(histories))
            item = {
                "key": key,
                "M": signed128(row["Mreg"]),
                "deviation": physical_deviation(row),
                "row": row,
                "histories": histories,
                "states": states,
            }
            records.append(item)
            groups[key].append(item)

    bad_groups = {}
    reversed_pairs = []
    for key, entries in groups.items():
        fires = [entry for entry in entries if entry["deviation"]]
        cleans = [entry for entry in entries if not entry["deviation"]]
        if not fires or not cleans:
            continue
        pairs = [(fire, clean) for fire in fires for clean in cleans
                 if is_reversed(key[0], fire["M"], clean["M"])]
        if pairs:
            bad_groups[key] = entries
            reversed_pairs.extend((key, fire, clean) for fire, clean in pairs)

    scalar_names = sorted(
        name for name in records[0]["states"]
        if name.startswith("add.") or name.startswith("branch."))
    scores = []
    for name in scalar_names:
        partitioned = defaultdict(list)
        for item in records:
            partitioned[item["key"] + (item["states"][name],)].append(
                (item["M"], item["deviation"]))
        score = monotonicity(partitioned)
        scores.append((score[1], score[2], score[0], name,
                       len({item["states"][name] for item in records})))
    scores.sort()

    coordinate_features = [
        *(f"{name}.centered_q66" for name in ADDS),
        "add.centered_q66_sum",
        "branch.centered_q66_difference",
    ]
    coordinate_scores = []
    for name in coordinate_features:
        for coefficient in range(-32, 33):
            for shift in range(-6, 7):
                corrected = defaultdict(list)
                for item in records:
                    value = item["M"] + coefficient * scale_integer(
                        int(item["states"][name]), shift)
                    corrected[item["key"]].append((value, item["deviation"]))
                score = monotonicity(corrected)
                coordinate_scores.append((
                    score[1], score[2], score[0], abs(coefficient),
                    abs(shift), name, coefficient, shift,
                ))
    coordinate_scores.sort()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"rows_sha256\t{digest(args.rows)}\n")
        target.write(f"constraining_rows\t{len(records)}\n")
        target.write(f"nonmonotone_cells\t{len(bad_groups)}\n")
        target.write(f"reversed_pairs\t{len(reversed_pairs)}\n")

        target.write("\n[scalar history partitions]\n")
        target.write("nonmonotone\trows_in_nonmonotone\tmixed\tstates\tfeature\n")
        for nonmonotone, bad_rows, mixed, name, state_count in scores:
            target.write(
                f"{nonmonotone}\t{bad_rows}\t{mixed}\t{state_count}\t{name}\n")

        target.write("\n[corrected M coordinate search]\n")
        target.write(
            "nonmonotone\trows_in_nonmonotone\tmixed\tfeature\t"
            "coefficient\tshift\n")
        for (nonmonotone, bad_rows, mixed, _, _, name, coefficient,
             shift) in coordinate_scores[:100]:
            target.write(
                f"{nonmonotone}\t{bad_rows}\t{mixed}\t{name}\t"
                f"{coefficient}\t{shift}\n")

        target.write("\n[conflict cells]\n")
        target.write(
            "cell\tmode\top\tmodel_target\tdeviation\tM\tclasses\t"
            "directions\tadd_dir_sum\tadd_dir_alt\tbranch_dir_diff\t"
            "add_class_sum\tadd_class_alt\tbranch_class_diff\t"
            "centered_sum\tcentered_branch_diff\n")
        for key, entries in sorted(bad_groups.items()):
            for item in sorted(entries, key=lambda entry: entry["M"]):
                row = item["row"]
                states = item["states"]
                classes, directions = history_text(item["histories"])
                target.write(
                    f"{'/'.join(map(str, key))}\t{row['mode']}\t{row['op']}\t"
                    f"{int(row['label'] == 'POS')}\t{item['deviation']}\t"
                    f"{item['M']}\t{classes}\t{directions}\t"
                    f"{states['add.direction_sum']}\t"
                    f"{states['add.direction_alt_sum']}\t"
                    f"{states['branch.direction_sum_difference']}\t"
                    f"{states['add.class_sum']}\t"
                    f"{states['add.class_alt_sum']}\t"
                    f"{states['branch.class_sum_difference']}\t"
                    f"{states['add.centered_q16_sum']}\t"
                    f"{states['branch.centered_q16_difference']}\n")

        target.write("\n[reversed pairs]\n")
        target.write(
            "cell\tfire_op\tfire_M\tfire_target\tfire_classes\t"
            "fire_directions\tclean_op\tclean_M\tclean_target\t"
            "clean_classes\tclean_directions\n")
        for key, fire, clean in sorted(
                reversed_pairs,
                key=lambda item: (item[0], item[1]["M"], item[2]["M"])):
            fire_classes, fire_directions = history_text(fire["histories"])
            clean_classes, clean_directions = history_text(clean["histories"])
            target.write(
                f"{'/'.join(map(str, key))}\t{fire['row']['op']}\t"
                f"{fire['M']}\t{int(fire['row']['label'] == 'POS')}\t"
                f"{fire_classes}\t{fire_directions}\t{clean['row']['op']}\t"
                f"{clean['M']}\t{int(clean['row']['label'] == 'POS')}\t"
                f"{clean_classes}\t{clean_directions}\n")

    print(
        f"wrote {args.report} cells={len(bad_groups)} "
        f"reversed_pairs={len(reversed_pairs)} "
        f"best_coordinate={coordinate_scores[0][5]} "
        f"nonmonotone={coordinate_scores[0][0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
