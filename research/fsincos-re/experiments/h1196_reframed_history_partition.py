#!/usr/bin/env python3
"""Test finite history states after applying the R1186 factor recurrence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
from collections import defaultdict
from pathlib import Path

from h1178_round_history_state_audit import (
    CELL,
    CONSTANTS,
    STAGES,
    add_same_sign,
    compare_scaled,
    feature_value,
    monotonicity,
    multiply,
    signed128,
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def r1186_add(left, right, include_exact: bool):
    value, history = add_same_sign(left, right)
    scale = min(left[1], right[1])
    magnitude = ((left[2] << (left[1] - scale))
                 + (right[2] << (right[1] - scale)))
    shift = max(0, magnitude.bit_length() - 64)
    fires = False
    if shift:
        remainder = magnitude & ((1 << shift) - 1)
        half = 1 << (shift - 1)
        fires = ((include_exact and remainder == half)
                 or (half < remainder <= half + 4))
    if fires:
        value = (value[0], value[1], value[2] - 1)
        # Record actual numerical direction of the modified representative.
        history = dict(history)
        history["direction"] = 1 if value[0] else -1
        history["r1186"] = True
    else:
        history = dict(history)
        history["r1186"] = False
    return value, history


def row_histories(row: dict[str, str]) -> dict[str, dict[str, object]]:
    magnitude = feature_value(row, "mag")
    square, square_history = multiply(magnitude, magnitude)
    fourth, fourth_history = multiply(square, square)
    if square != feature_value(row, "mul"):
        raise AssertionError("square reconstruction mismatch for " + row["op"])
    if fourth != feature_value(row, "f4"):
        raise AssertionError("fourth reconstruction mismatch for " + row["op"])

    odd_1_product, odd_1_product_history = multiply(fourth, CONSTANTS[5])
    odd_1, odd_1_history = add_same_sign(CONSTANTS[3], odd_1_product)
    odd_2_product, odd_2_product_history = multiply(fourth, odd_1)
    odd_2, odd_2_history = r1186_add(CONSTANTS[1], odd_2_product, True)
    even_1_product, even_1_product_history = multiply(fourth, CONSTANTS[6])
    even_1, even_1_history = add_same_sign(CONSTANTS[4], even_1_product)
    even_2_product, even_2_product_history = multiply(fourth, even_1)
    even_2, even_2_history = r1186_add(CONSTANTS[2], even_2_product, False)
    if odd_2 != feature_value(row, "lf"):
        raise AssertionError("odd factor reconstruction mismatch for " + row["op"])
    if even_2 != feature_value(row, "rf"):
        raise AssertionError("even factor reconstruction mismatch for " + row["op"])

    left, left_history = multiply(square, odd_2)
    right, right_history = multiply(fourth, even_2)
    if left != feature_value(row, "left"):
        raise AssertionError("left product reconstruction mismatch for " + row["op"])
    if right != feature_value(row, "right"):
        raise AssertionError("right product reconstruction mismatch for " + row["op"])

    return {
        "square": square_history,
        "fourth": fourth_history,
        "odd_p1": odd_1_product_history,
        "odd_a1": odd_1_history,
        "odd_p2": odd_2_product_history,
        "odd_a2": odd_2_history,
        "even_p1": even_1_product_history,
        "even_a1": even_1_history,
        "even_p2": even_2_product_history,
        "even_a2": even_2_history,
        "left": left_history,
        "right": right_history,
    }


def row_states(row: dict[str, str]) -> dict[str, object]:
    histories = row_histories(row)
    states: dict[str, object] = {}
    for name, history in histories.items():
        states[f"{name}.class"] = history["class"]
        states[f"{name}.direction"] = history["direction"]
    states["odd_a2.r1186"] = histories["odd_a2"]["r1186"]
    states["even_a2.r1186"] = histories["even_a2"]["r1186"]
    states["factor.r1186_pair"] = (
        histories["odd_a2"]["r1186"], histories["even_a2"]["r1186"])
    states["schedule.class_tuple"] = tuple(
        histories[name]["class"] for name in STAGES)
    states["schedule.direction_tuple"] = tuple(
        histories[name]["direction"] for name in STAGES)
    horner = tuple(name for name in STAGES
                   if name.startswith("odd_") or name.startswith("even_"))
    states["horner.class_tuple"] = tuple(
        histories[name]["class"] for name in horner)
    states["horner.direction_tuple"] = tuple(
        histories[name]["direction"] for name in horner)
    states["terminal.class_pair"] = (
        histories["left"]["class"], histories["right"]["class"])
    states["terminal.direction_pair"] = (
        histories["left"]["direction"], histories["right"]["direction"])
    states["factor.class_pair"] = (
        histories["odd_a2"]["class"], histories["even_a2"]["class"])
    states["factor.direction_pair"] = (
        histories["odd_a2"]["direction"], histories["even_a2"]["direction"])

    lrem = int(histories["left"]["remainder"])
    lshift = int(histories["left"]["shift"])
    rrem = int(histories["right"]["remainder"])
    rshift = int(histories["right"]["shift"])
    states["terminal.fraction_order"] = compare_scaled(
        lrem, -lshift, rrem, -rshift)
    left_base = feature_value(row, "mul")[1] + feature_value(row, "lf")[1]
    right_base = feature_value(row, "f4")[1] + feature_value(row, "rf")[1]
    states["terminal.physical_error_order"] = compare_scaled(
        lrem, left_base, rrem, right_base)
    states["terminal.class_and_fraction_order"] = (
        histories["left"]["class"], histories["right"]["class"],
        states["terminal.fraction_order"])
    states["terminal.class_and_physical_order"] = (
        histories["left"]["class"], histories["right"]["class"],
        states["terminal.physical_error_order"])
    return states


def physical_deviation(row: dict[str, str]) -> int:
    k = int(row["k"])
    mask = (1 << k) - 1
    borrow = int((int(row["S"], 16) & mask) < (int(row["B"], 16) & mask))
    delta = borrow - 1 + int(row["physical_label"])
    return int(delta != 0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rows", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    records = []
    with args.rows.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            if row["physical_status"] != "constraining":
                continue
            key = tuple(int(row[field]) for field in CELL)
            records.append((key, signed128(row["Mreg"]),
                            physical_deviation(row), row_states(row)))

    names = sorted(records[0][3])
    results = []
    base_groups = defaultdict(list)
    for key, value, label, _ in records:
        base_groups[key].append((value, label))
    results.append((monotonicity(base_groups), len(base_groups), 1, "M only"))
    for name in names:
        groups = defaultdict(list)
        states = set()
        for key, value, label, row_state in records:
            state = row_state[name]
            states.add(state)
            groups[key + (state,)].append((value, label))
        results.append((monotonicity(groups), len(groups), len(states), name))
    results.sort(key=lambda item: (item[0][1], item[0][2], item[2], item[3]))

    horner = tuple(name for name in STAGES
                   if name.startswith("odd_") or name.startswith("even_"))
    subset_results = []
    for kind in ("class", "direction"):
        for count in range(1, len(horner) + 1):
            found_zero = False
            for subset in itertools.combinations(horner, count):
                groups = defaultdict(list)
                for key, value, label, row_state in records:
                    state = tuple(row_state[f"{stage}.{kind}"] for stage in subset)
                    groups[key + (state,)].append((value, label))
                score = monotonicity(groups)
                subset_results.append((score, kind, subset, len(groups)))
                found_zero |= score[1] == 0
            if found_zero:
                break
    subset_results.sort(key=lambda item: (
        item[0][1], len(item[2]), item[0][2], item[1], item[2]))

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"rows_sha256\t{digest(args.rows)}\n")
        target.write(f"constraining_rows\t{len(records)}\n")
        target.write("\n[history-state monotonicity]\n")
        target.write(
            "nonmonotone\trows_in_nonmonotone\tmixed\tgroups\tstates\tfeature\n")
        for (mixed, nonmonotone, bad_rows), groups, state_count, name in results:
            target.write(
                f"{nonmonotone}\t{bad_rows}\t{mixed}\t{groups}\t"
                f"{state_count}\t{name}\n")
        target.write("\n[minimal Horner subsets]\n")
        target.write(
            "nonmonotone\trows_in_nonmonotone\tmixed\tstage_count\t"
            "kind\tstages\tgroups\n")
        for (mixed, nonmonotone, bad_rows), kind, subset, groups in subset_results[:100]:
            target.write(
                f"{nonmonotone}\t{bad_rows}\t{mixed}\t{len(subset)}\t"
                f"{kind}\t{','.join(subset)}\t{groups}\n")

    print(
        f"wrote {args.report} rows={len(records)} "
        f"baseline_nonmonotone={next(item for item in results if item[3] == 'M only')[0][1]} "
        f"best_nonmonotone={results[0][0][1]} feature={results[0][3]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
