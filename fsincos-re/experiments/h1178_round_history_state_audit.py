#!/usr/bin/env python3
"""Audit patent-motivated finite rounding-history states at the R59 FSUB.

US5612909 names three kinds of metadata that may accompany an intermediate:
rounding direction, relation of discarded bits to half, and the all-ones
discard case.  This script reconstructs those states for every operation in
the six-term cosine schedule, verifies the reconstructed materialized values,
and asks whether any small history state makes the signed R60 coordinate
monotone inside every discrete digit cell.

The states are fixed before labels are read.  This is a cached-label analysis;
it does not capture hardware and it deliberately does not enumerate arbitrary
remainder prefixes that could become a lookup table in another notation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import defaultdict
from pathlib import Path


CELL = ("theta", "ce", "s4", "side", "low3", "dist", "rsh", "b1", "b2")
STAGES = (
    "square", "fourth", "odd_p1", "odd_a1", "odd_p2", "odd_a2",
    "even_p1", "even_a1", "even_p2", "even_a2", "left", "right",
)
CONSTANTS = {
    1: (1, -68, (7 << 64) | 0xFFFFFFFFFFFFFFFE),
    2: (0, -71, (5 << 64) | 0x5555555555554277),
    3: (1, -76, (5 << 64) | 0xB05B05B05A18A1BA),
    4: (0, -82, (6 << 64) | 0x80680675B559F2CF),
    5: (1, -88, (4 << 64) | 0x9F93AF61F5349300),
    6: (0, -95, (4 << 64) | 0x7A4F2483514C1AF8),
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def signed128(text: str) -> int:
    value = int(text, 16)
    return value - (1 << 128) if value >> 127 else value


def history_class(remainder: int, shift: int) -> str:
    if not remainder:
        return "exact"
    denominator = 1 << shift
    if remainder == denominator - 1:
        return "all1"
    doubled = 2 * remainder
    if doubled < denominator:
        return "low"
    if doubled == denominator:
        return "half"
    return "high"


def round_word(sign: int, magnitude: int, scale: int, bits: int,
               nearest: bool) -> tuple[tuple[int, int, int], dict[str, object]]:
    shift = max(0, magnitude.bit_length() - bits)
    round_shift = shift
    top = magnitude >> shift
    remainder = magnitude & ((1 << shift) - 1) if shift else 0
    increment = False
    if nearest and shift:
        half = 1 << (shift - 1)
        increment = remainder > half or (remainder == half and bool(top & 1))
    if increment:
        top += 1
        if top == 1 << bits:
            top >>= 1
            shift += 1
    direction = 0 if not remainder else (1 if increment else -1)
    if sign:
        direction = -direction
    state = {
        # Classify against the cut at which this operation rounded.  A carry
        # out of the retained word changes the result scale, but it does not
        # change the denominator of the already-discarded fraction.
        "class": (history_class(remainder, round_shift)
                  if round_shift else "exact"),
        "direction": direction,
        "shift": round_shift,
        "remainder": remainder,
    }
    return (sign, scale + shift, top), state


def multiply(left: tuple[int, int, int], right: tuple[int, int, int],
             bits: int = 67, nearest: bool = False
             ) -> tuple[tuple[int, int, int], dict[str, object]]:
    return round_word(left[0] ^ right[0], left[2] * right[2],
                      left[1] + right[1], bits, nearest)


def add_same_sign(left: tuple[int, int, int], right: tuple[int, int, int],
                  bits: int = 64
                  ) -> tuple[tuple[int, int, int], dict[str, object]]:
    if left[0] != right[0]:
        raise AssertionError("expected same-sign Horner addition")
    scale = min(left[1], right[1])
    magnitude = ((left[2] << (left[1] - scale))
                 + (right[2] << (right[1] - scale)))
    return round_word(left[0], magnitude, scale, bits, True)


def feature_value(row: dict[str, str], name: str) -> tuple[int, int, int]:
    return (int(row[f"tc_{name}_sign"]), int(row[f"tc_{name}_exp"]),
            int(row[f"tc_{name}_sig"], 16))


def compare_scaled(a: int, ae: int, b: int, be: int) -> int:
    common = min(ae, be)
    difference = (a << (ae - common)) - (b << (be - common))
    return (difference > 0) - (difference < 0)


def row_states(row: dict[str, str]) -> dict[str, object]:
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
    odd_2, odd_2_history = add_same_sign(CONSTANTS[1], odd_2_product)
    even_1_product, even_1_product_history = multiply(fourth, CONSTANTS[6])
    even_1, even_1_history = add_same_sign(CONSTANTS[4], even_1_product)
    even_2_product, even_2_product_history = multiply(fourth, even_1)
    even_2, even_2_history = add_same_sign(CONSTANTS[2], even_2_product)
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

    histories = {
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
    states: dict[str, object] = {}
    for name, history in histories.items():
        states[f"{name}.class"] = history["class"]
        states[f"{name}.direction"] = history["direction"]

    ordered_names = STAGES
    states["schedule.class_tuple"] = tuple(
        histories[name]["class"] for name in ordered_names)
    states["schedule.direction_tuple"] = tuple(
        histories[name]["direction"] for name in ordered_names)
    horner_names = tuple(name for name in ordered_names
                         if name.startswith("odd_") or name.startswith("even_"))
    states["horner.class_tuple"] = tuple(
        histories[name]["class"] for name in horner_names)
    states["horner.direction_tuple"] = tuple(
        histories[name]["direction"] for name in horner_names)

    states["terminal.class_pair"] = (
        left_history["class"], right_history["class"])
    states["terminal.direction_pair"] = (
        left_history["direction"], right_history["direction"])
    states["factor.class_pair"] = (
        odd_2_history["class"], even_2_history["class"])
    states["factor.direction_pair"] = (
        odd_2_history["direction"], even_2_history["direction"])
    states["terminal.any_all1"] = (
        left_history["class"] == "all1" or right_history["class"] == "all1")
    states["terminal.any_half"] = (
        left_history["class"] == "half" or right_history["class"] == "half")

    # Compare the discarded fractions as a dimensionless precision state.
    lrem, lshift = left_history["remainder"], left_history["shift"]
    rrem, rshift = right_history["remainder"], right_history["shift"]
    states["terminal.fraction_order"] = compare_scaled(
        lrem, -lshift, rrem, -rshift)

    # Compare their actual signed contributions to the final exact correction.
    # Left is negative and right positive, so the chopped-value errors oppose.
    left_base = square[1] + odd_2[1]
    right_base = fourth[1] + even_2[1]
    states["terminal.physical_error_order"] = compare_scaled(
        lrem, left_base, rrem, right_base)
    states["terminal.class_and_fraction_order"] = (
        left_history["class"], right_history["class"],
        states["terminal.fraction_order"])
    states["terminal.class_and_physical_order"] = (
        left_history["class"], right_history["class"],
        states["terminal.physical_error_order"])
    return states


def monotonicity(groups: dict[tuple[object, ...], list[tuple[int, int]]]
                 ) -> tuple[int, int, int]:
    mixed = 0
    nonmonotone = 0
    rows_in_nonmonotone = 0
    for key, entries in groups.items():
        fires = [value for value, label in entries if label]
        cleans = [value for value, label in entries if not label]
        if not fires or not cleans:
            continue
        mixed += 1
        theta = int(key[0])
        separable = (max(fires) < min(cleans) if theta >= 0
                     else max(cleans) < min(fires))
        if not separable:
            nonmonotone += 1
            rows_in_nonmonotone += len(entries)
    return mixed, nonmonotone, rows_in_nonmonotone


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("physical_rows", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    with args.features.open(newline="") as source:
        features = {(row["mode"], row["op"]): row for row in
                    csv.DictReader(source, delimiter="\t")}
    records = []
    with args.physical_rows.open(newline="") as source:
        for physical in csv.DictReader(source, delimiter="\t"):
            if physical["physical_status"] != "constraining":
                continue
            row = features[(physical["mode"], physical["op"])]
            key = tuple(int(physical[field]) for field in CELL)
            records.append((key, signed128(physical["Mreg"]),
                            int(physical["physical_label"]), row_states(row)))

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

    # A separator after partitioning by several local half-side states must
    # distinguish every reversed fire/clean pair.  Each conflict therefore
    # supplies a bit mask of stages whose history differs; the minimum valid
    # subset is the exact minimum hitting set over the twelve stage bits.
    conflict_groups = defaultdict(list)
    for key, value, label, row_state in records:
        signature = tuple(row_state[f"{name}.class"] for name in STAGES)
        conflict_groups[key].append((value, label, signature))
    conflict_masks = set()
    conflict_pairs = 0
    for key, entries in conflict_groups.items():
        fires = [entry for entry in entries if entry[1]]
        cleans = [entry for entry in entries if not entry[1]]
        for fire in fires:
            for clean in cleans:
                reversed_pair = (fire[0] >= clean[0] if key[0] >= 0
                                 else clean[0] >= fire[0])
                if not reversed_pair:
                    continue
                conflict_pairs += 1
                conflict_masks.add(sum(
                    (fire[2][index] != clean[2][index]) << index
                    for index in range(len(STAGES))))
    minimum_subsets = []
    if 0 not in conflict_masks:
        for subset in range(1, 1 << len(STAGES)):
            if all(subset & mask for mask in conflict_masks):
                count = subset.bit_count()
                if not minimum_subsets or count < minimum_subsets[0][0]:
                    minimum_subsets = [(count, subset)]
                elif count == minimum_subsets[0][0]:
                    minimum_subsets.append((count, subset))

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("w") as target:
        target.write(f"features_sha256\t{digest(args.features)}\n")
        target.write(f"physical_rows_sha256\t{digest(args.physical_rows)}\n")
        target.write(f"constraining_rows\t{len(records)}\n")
        target.write("\n[history-state monotonicity]\n")
        target.write("nonmonotone\trows_in_nonmonotone\tmixed\tgroups\tstates\tfeature\n")
        for (mixed, nonmonotone, bad_rows), group_count, state_count, name in results:
            target.write(f"{nonmonotone}\t{bad_rows}\t{mixed}\t{group_count}\t"
                         f"{state_count}\t{name}\n")
        target.write("\n[minimum local-history hitting set]\n")
        target.write(f"conflict_pairs\t{conflict_pairs}\n")
        target.write(f"distinct_conflict_masks\t{len(conflict_masks)}\n")
        target.write(f"zero_difference_conflicts\t{int(0 in conflict_masks)}\n")
        if minimum_subsets:
            target.write(f"minimum_stage_count\t{minimum_subsets[0][0]}\n")
            target.write(f"minimum_subset_count\t{len(minimum_subsets)}\n")
            for _, subset in minimum_subsets:
                target.write("stages\t" + ",".join(
                    STAGES[index] for index in range(len(STAGES))
                    if subset & (1 << index)) + "\n")

    best = results[0]
    print(f"rows={len(records)} baseline_nonmonotone=23 "
          f"best_nonmonotone={best[0][1]} feature={best[3]} "
          f"report={args.report}")


if __name__ == "__main__":
    main()
