#!/usr/bin/env python3
"""Score arithmetic interpretations of the dcc carry miss on its dense cell.

The input is the complete cached stage-A extraction.  Only the fixed
theta=0, ce=-72, s4=67, upper-side, distance-8, right-cut-63 cell is read.
The candidate predicates are named wires suggested by h1274, plus the
explicit overflow from merging the square's upper radix-8 product with its
external low digit.  Hardware is never executed.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

from h1100_p5_multiplier_tree import TREE_MASK, csa3, multiplier_tree
from h1129_r60_redundant_comparator_mine import (
    MASK, carry_between, merge_low_digit, negate_rows, reduce_balanced,
)
from h1172_p5_cpa_predictor_mine import group_state


TARGET = "3ffc dcc000000d24fdf2"
SCOPE = {
    "theta": "0", "ce": "-72", "s4": "67", "side": "1",
    "dist": "8", "rsh": "63",
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def bit(value: int, position: int) -> int:
    return (value >> position) & 1


def row_predicates(row: dict[str, str]) -> dict[str, int]:
    multiplier = int(row["tc_mul_sig"], 16)
    low3 = int(row["low3"])
    s4 = int(row["s4"])
    residue_mask = (1 << s4) - 1

    default = multiplier_tree(multiplier, multiplier >> 3)
    q_cut = (multiplier * (multiplier >> 3)).bit_length() - 67
    qx_sum, qx_carry = csa3(
        (default["sum"] << 3) & TREE_MASK,
        (default["carry"] << 3) & TREE_MASK,
        multiplier * low3,
    )

    alternate = multiplier_tree(multiplier, multiplier >> 3, d_slot=3)
    alt3_sum, alt3_carry = merge_low_digit(alternate, multiplier, 3)
    alt2_sum, alt2_carry = merge_low_digit(alternate, multiplier, 2)

    sqlow = multiplier - (1 << 66)
    low_product = low3 * sqlow
    sum_residue = alt3_sum & residue_mask
    carry_residue = alt3_carry & residue_mask
    overflow = (sum_residue + carry_residue) >> s4
    comparator_rows = [low_product]
    comparator_rows.extend(negate_rows([sum_residue, carry_residue]))
    if overflow:
        comparator_rows.append(overflow << s4)
    comp_sum, comp_carry = reduce_balanced(comparator_rows)

    base8 = 2 + ((q_cut - 2) // 8) * 8
    q_group_low = group_state(
        default["sum"], default["carry"], base8 - 32, base8 - 24)[0]
    base4 = 2 + ((q_cut - 2) // 4) * 4
    left_state = multiplier_tree(
        int(row["tc_mul_sig"], 16), int(row["tc_lf_sig"], 16))
    left_low_propagate = group_state(
        left_state["sum"], left_state["carry"],
        base4 - 12, base4 - 8,
    )[1]

    upper_base = (multiplier * (multiplier >> 3) << 3) & residue_mask
    external = (multiplier * low3) & residue_mask
    radix_merge_overflow = (upper_base + external) >> s4

    values = {
        "radix_merge_overflow": radix_merge_overflow,
        "qx_gen61_and_alt3_sum61":
            bit(qx_sum & qx_carry, 61) & bit(alt3_sum, 61),
        "q_gen_cutm7_and_alt2_carry61":
            bit(default["sum"] & default["carry"], q_cut - 7)
            & bit(alt2_carry, 61),
        "alt3_comp_gen61_and_q_group_low_g":
            bit(comp_sum & comp_carry, 61) & q_group_low,
        "left_p5_w4_relm3_propagate": left_low_propagate,
    }
    default_raw_sum = 0
    default_raw_carry = 0
    for inner_slot in range(4):
        state = multiplier_tree(
            multiplier, multiplier >> 3, d_slot=inner_slot)
        for merge_slot in ("csa3", 0, 1, 2, 3):
            square_sum, square_carry = merge_low_digit(
                state, multiplier, merge_slot)
            sum_residue = square_sum & residue_mask
            carry_residue = square_carry & residue_mask
            residue_overflow = (sum_residue + carry_residue) >> s4
            raw_rows = [low_product]
            raw_rows.extend(negate_rows([sum_residue, carry_residue]))
            corrected_rows = list(raw_rows)
            if residue_overflow:
                corrected_rows.append(residue_overflow << s4)
            for form, comparator_rows in (
                    ("raw", raw_rows), ("mod", corrected_rows)):
                pair_sum, pair_carry = reduce_balanced(comparator_rows)
                if inner_slot == 0 and merge_slot == "csa3" and form == "raw":
                    default_raw_sum = pair_sum
                    default_raw_carry = pair_carry
                exact_carry = carry_between(
                    pair_sum, pair_carry, 0, 68, 0)
                local_carry = carry_between(
                    pair_sum, pair_carry, 66, 68, 0)
                tag = f"inner{inner_slot}.merge{merge_slot}.{form}"
                values[tag + ".rel02.end68.c0.mismatch"] = (
                    exact_carry ^ local_carry)
                values[tag + ".rel02.end68.c0.carry"] = local_carry
    qx_generate39 = bit(qx_sum & qx_carry, 39)
    qx_group32_39 = group_state(qx_sum, qx_carry, 32, 40)
    values.update({
        "default_raw_gen61_and_qx_gen39":
            bit(default_raw_sum & default_raw_carry, 61) & qx_generate39,
        "default_raw_carry61_and_qx_gen39":
            bit(default_raw_carry, 61) & qx_generate39,
        "default_raw_gen61_and_qx_group32_39_g":
            bit(default_raw_sum & default_raw_carry, 61)
            & qx_group32_39[0],
        "default_raw_gen61_and_qx_group32_39_c1":
            bit(default_raw_sum & default_raw_carry, 61)
            & qx_group32_39[3],
        "default_raw_gen61_and_qx_cin40":
            bit(default_raw_sum & default_raw_carry, 61)
            & qx_group32_39[5],
    })
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("labels", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    with args.labels.open(newline="") as source:
        labels = {(row["corpus"], row["index"]): row
                  for row in csv.DictReader(source, delimiter="\t")}

    counts: dict[str, Counter] = defaultdict(Counter)
    examples: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    rows = 0
    with gzip.open(args.features, "rt", newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            if not all(row[name] == value for name, value in SCOPE.items()):
                continue
            label = labels[(row["corpus"], row["index"])]
            if label["selector_status"] != "constraining":
                continue
            rows += 1
            desired = int(label["allowed_carry"])
            current = int(label["current_carry"])
            target = int(row["op"] == TARGET)
            low3 = int(row["low3"])
            b1 = int(row["b1"])
            b2 = int(row["b2"])
            base0 = (2 * low3 + 2 * b1 + 3 * b2
                     - 3 * (low3 & 1) - 6)
            u0 = 2 * (base0 // 8) + (low3 & 1)
            mreg = int(row["Mreg"], 16)
            predicates = row_predicates(row)
            threshold_predictions = {
                "threshold_plus1." + name:
                    int(not (mreg < (u0 + predicate) * (1 << 66)))
                for name, predicate in predicates.items()
            }
            flip_predictions = {
                "force_flip." + name: current ^ predicate
                for name, predicate in predicates.items()
            }
            for name, predicted in {
                    **threshold_predictions, **flip_predictions}.items():
                predicate = predicted != current
                counts[name]["fires"] += predicate
                counts[name]["errors"] += predicted != desired
                counts[name]["target_miss"] += target and not predicate
                counts[name]["control_fire"] += predicate and not target
                if predicate and len(examples[name]) < 20:
                    examples[name].append(
                        (row["op"], str(desired), str(current)))
            if rows % 10000 == 0:
                print(f"features {rows}", flush=True)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"features_sha256\t{digest(args.features)}\n")
        target.write(f"labels_sha256\t{digest(args.labels)}\n")
        target.write(f"rows\t{rows}\n")
        target.write("hardware_policy\tcached_labels_only_no_x87_execution\n")
        target.write("\n[scores]\n")
        target.write(
            "errors\ttarget_miss\tcontrol_fire\tfires\tpredicate\n")
        ranking = sorted(
            (value["errors"], value["target_miss"],
             value["control_fire"], value["fires"], name)
            for name, value in counts.items())
        for score in ranking:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[fire examples]\n")
        for _, _, _, _, name in ranking:
            target.write(f"{name}\n")
            for example in examples[name]:
                target.write("\t" + "\t".join(example) + "\n")

    print(f"wrote {args.report} rows={rows} best={ranking[0]}", flush=True)


if __name__ == "__main__":
    main()
