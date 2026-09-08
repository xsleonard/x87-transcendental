#!/usr/bin/env python3
"""Test word-level product-CPA relations on the six R1237 residuals.

Single circuit bits and two-wire XOR/XNOR relations do not isolate the
remaining terminal carry flips.  This pass keeps the complete four-bit
conditional words of the patented P5 product CPA.  It tests fixed unsigned
word relations between the two terminal products, the shared square, and
natural radix projections of the R60 coordinate.  These are arithmetic
relations, not learned operand thresholds.

An exact discovery result is still only a mechanism candidate; promotion
requires reconstruction as a circuit recurrence and a complete dense wall.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from itertools import combinations
from pathlib import Path

from h1100_p5_multiplier_tree import TREE_MASK, csa3, multiplier_tree
from h1172_p5_cpa_predictor_mine import add_cpa_features, product_state
from h1178_round_history_state_audit import signed128


ONE = 1 << 66
PREFIXES = ("L", "R", "Q", "QX")
ALIGNMENTS = ("p5", "abs", "cut")
RELATIVES = tuple(range(-4, 5))
FORMS = ("sum0", "sum1", "selected")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def word(values: dict[str, int], stem: str, assumed: int) -> int:
    return sum(values[f"{stem}.sum{assumed}.b{offset}"] << offset
               for offset in range(4))


def product_words(row: dict[str, str]) -> dict[str, int]:
    multiplier = int(row["tc_mul_sig"], 16)
    left_factor = int(row["tc_lf_sig"], 16)
    fourth = int(row["tc_f4_sig"], 16)
    right_factor = int(row["tc_rf_sig"], 16)
    states = {
        "L": product_state(multiplier, left_factor),
        "R": product_state(fourth, right_factor),
        "Q": product_state(multiplier, multiplier >> 3),
    }
    qstate = multiplier_tree(multiplier, multiplier >> 3)
    square_sum, square_carry = csa3(
        (qstate["sum"] << 3) & TREE_MASK,
        (qstate["carry"] << 3) & TREE_MASK,
        multiplier * (multiplier & 7),
    )
    square = multiplier * multiplier
    if ((square_sum + square_carry) & ((1 << 134) - 1)) != square:
        raise AssertionError("full-square reconstruction mismatch")
    states["QX"] = (square_sum, square_carry, square.bit_length() - 67)

    result = {}
    for prefix, (sum_vector, carry_vector, cut) in states.items():
        values: dict[str, int] = {}
        add_cpa_features(values, prefix, sum_vector, carry_vector, cut)
        for alignment in ALIGNMENTS:
            for relative in RELATIVES:
                stem = f"{prefix}.{alignment}.w04.rel{relative:+d}"
                sum0 = word(values, stem, 0)
                sum1 = word(values, stem, 1)
                cin = values[f"{stem}.cin"]
                result[f"{stem}.sum0"] = sum0
                result[f"{stem}.sum1"] = sum1
                result[f"{stem}.selected"] = sum1 if cin else sum0
    return result


def coordinate_words(row: dict[str, str]) -> dict[str, int]:
    mreg = signed128(row["Mreg"])
    low3 = int(row["low3"])
    b1 = int(row["b1"])
    b2 = int(row["b2"])
    theta = int(row["theta"])
    values = {
        "coord.low3": low3,
        "coord.payload": int(row["payload"]) & 15,
        "coord.thirds": b1 + 2 * b2,
        "coord.digit": (low3 + b1 + b2) & 15,
        "coord.double_digit": (2 * low3 + b1 + b2) & 15,
        "coord.theta": theta & 15,
        "coord.m_floor": (mreg // ONE) & 15,
        "coord.m16": ((16 * mreg) // ONE) & 15,
        "coord.m128": ((128 * mreg) // ONE) & 15,
    }
    for name in ("Mreg", "t4", "sqlow", "rd3"):
        raw = mreg if name == "Mreg" else int(row[name], 16)
        for start in range(48, 73, 4):
            values[f"coord.{name}.nibble{start}"] = (raw >> start) & 15
    return values


def relations(left: int, right: int) -> dict[str, int]:
    return {
        "eq": int(left == right),
        "ne": int(left != right),
        "lt": int(left < right),
        "le": int(left <= right),
        "gt": int(left > right),
        "ge": int(left >= right),
        "carry_add": int(left + right >= 16),
        "borrow_sub": int(left < right),
        "carry_add_complement": int(left + (right ^ 15) >= 16),
        "msb_equal": int(((left >> 3) & 1) == ((right >> 3) & 1)),
        "parity_equal": int((left & 1) == (right & 1)),
    }


def compatible_pairs(words: dict[str, int], coordinates: dict[str, int]):
    by_layout = {}
    for name in words:
        prefix, alignment, width, relative, form = name.split(".")
        by_layout.setdefault((alignment, width, relative, form), []).append(name)
    for layout, names in sorted(by_layout.items()):
        for left, right in combinations(sorted(names), 2):
            yield f"product_pair.{layout}", left, right
    for word_name in sorted(words):
        for coordinate_name in sorted(coordinates):
            yield "product_coordinate", word_name, coordinate_name


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rows", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    with args.rows.open(newline="") as source:
        rows = [row for row in csv.DictReader(source, delimiter="\t")
                if row["physical_status"] == "constraining"]
    records = []
    for index, row in enumerate(rows, 1):
        records.append((
            row, product_words(row), coordinate_words(row),
            int(row["label"] == "POS"),
        ))
        if index % 50 == 0:
            print(f"words {index}/{len(rows)}", flush=True)

    first_words, first_coordinates = records[0][1:3]
    candidates = list(compatible_pairs(first_words, first_coordinates))
    ranking = []
    exact = []
    for family, left_name, right_name in candidates:
        for relation_name in relations(0, 0):
            target_miss = 0
            control_fire = 0
            target_fire = 0
            for _, words, coordinates, target in records:
                values = {**words, **coordinates}
                prediction = relations(
                    values[left_name], values[right_name])[relation_name]
                target_miss += target and not prediction
                control_fire += not target and prediction
                target_fire += target and prediction
            score = (
                target_miss + control_fire, target_miss, control_fire,
                -target_fire, family, relation_name, left_name, right_name,
            )
            ranking.append(score)
            if target_miss == 0 and control_fire == 0:
                exact.append(score)
    ranking.sort()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"rows_sha256\t{digest(args.rows)}\n")
        target.write(f"rows\t{len(rows)}\n")
        target.write(f"targets\t{sum(record[3] for record in records)}\n")
        target.write(f"product_words\t{len(first_words)}\n")
        target.write(f"coordinate_words\t{len(first_coordinates)}\n")
        target.write(f"word_pairs\t{len(candidates)}\n")
        target.write(f"relations\t{len(relations(0, 0))}\n")
        target.write(f"exact_relations\t{len(exact)}\n")
        target.write("hardware_policy\tcached_labels_only_no_x87_execution\n")
        target.write("\n[ranking]\n")
        target.write(
            "errors\ttarget_miss\tcontrol_fire\ttarget_fire\tfamily\t"
            "relation\tleft\tright\n")
        for score in ranking[:3000]:
            rendered = (*score[:3], -score[3], *score[4:])
            target.write("\t".join(map(str, rendered)) + "\n")

    print(
        f"wrote {args.report} rows={len(rows)} words={len(first_words)} "
        f"pairs={len(candidates)} exact={len(exact)} best={ranking[0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
