#!/usr/bin/env python3
"""Reconstruct the branch-independent redundant carry for terminal R59.

The post-R1237 collision rows do not carry the old ``br_uu`` threshold,
which made h1201 silently omit every h1129 redundant-comparator feature.
The arithmetic feeding that comparator is nevertheless fully determined:

    M = low3 * (mu - 2**66) - (mu*mu mod 2**s4).

This audit keeps the square residue in the literal P5 multiplier's redundant
sum/carry form and subtracts those two rows without first propagating them.
It scores fixed CSA and block-carry signals against the observed exception
carry

    physical_terminal_carry XOR bit1(low3).

No operand boundary, learned threshold, or live x87 execution is used.
An exact result would still be a mechanism candidate requiring whole-cache
regression and software-only adversarial testing before promotion.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import defaultdict
from pathlib import Path

from h1100_p5_multiplier_tree import TREE_MASK, multiplier_tree
from h1129_r60_redundant_comparator_mine import (
    CUT,
    MASK,
    WIDTH,
    bit,
    carry_between,
    merge_low_digit,
    negate_rows,
    reduce_balanced,
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def carry_features(prefix: str, rows: list[int]) -> dict[str, int]:
    """Expose fixed two-row CSA and local-carry interpretations."""
    sum_vector, carry_vector = reduce_balanced(rows)
    exact_total = sum(rows) & MASK
    if ((sum_vector + carry_vector) & MASK) != exact_total:
        raise AssertionError("redundant subtraction changed modular value")

    values: dict[str, int] = {}
    exact_carries = {}
    for position in range(48, 76):
        incoming = carry_between(sum_vector, carry_vector, 0, position, 0)
        exact_carries[position] = incoming
        values[f"{prefix}.cpa.in.abs{position}"] = incoming
        values[f"{prefix}.sum.abs{position}"] = bit(sum_vector, position)
        values[f"{prefix}.carry.abs{position}"] = bit(carry_vector, position)
        values[f"{prefix}.prop.abs{position}"] = (
            bit(sum_vector, position) ^ bit(carry_vector, position)
        )
        values[f"{prefix}.gen.abs{position}"] = (
            bit(sum_vector, position) & bit(carry_vector, position)
        )
        values[f"{prefix}.value.abs{position}"] = bit(exact_total, position)

    for end in range(CUT - 2, CUT + 3):
        exact = exact_carries[end]
        for width in (2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24, 32):
            start = end - width
            for assumed in (0, 1):
                local = carry_between(
                    sum_vector, carry_vector, start, end, assumed
                )
                stem = f"{prefix}.rel{width:02d}.end{end}.c{assumed}"
                values[f"{stem}.carry"] = local
                values[f"{stem}.mismatch"] = local ^ exact
        for block_width in (4, 8, 16, 32):
            start = end - (end % block_width)
            for assumed in (0, 1):
                local = carry_between(
                    sum_vector, carry_vector, start, end, assumed
                )
                stem = f"{prefix}.abs{block_width:02d}.end{end}.c{assumed}"
                values[f"{stem}.carry"] = local
                values[f"{stem}.mismatch"] = local ^ exact
    return values


def row_features(row: dict[str, str]) -> dict[str, int]:
    multiplier = int(row["tc_mul_sig"], 16)
    low3 = int(row["low3"])
    sqlow = multiplier - (1 << 66)
    low_product = low3 * sqlow
    s4 = int(row["s4"])
    residue_mask = (1 << s4) - 1
    exact_t4 = int(row["t4"], 16)
    exact_m = int(row["Mreg"], 16)
    if exact_m >> 127:
        exact_m -= 1 << 128
    if low_product - exact_t4 != exact_m:
        raise AssertionError("terminal M identity failed")

    values = carry_features(
        "exact", [low_product, (-exact_t4) & MASK]
    )
    for inner_slot in range(4):
        state = multiplier_tree(
            multiplier, multiplier >> 3, d_slot=inner_slot
        )
        for merge_slot in ("csa3", 0, 1, 2, 3):
            square_sum, square_carry = merge_low_digit(
                state, multiplier, merge_slot
            )
            square = multiplier * multiplier
            if ((square_sum + square_carry) & ((1 << 134) - 1)) != square:
                raise AssertionError("square reconstruction mismatch")
            sum_residue = square_sum & residue_mask
            carry_residue = square_carry & residue_mask
            residue_total = sum_residue + carry_residue
            if (residue_total & residue_mask) != exact_t4:
                raise AssertionError("square residue mismatch")
            overflow = residue_total >> s4
            tag = f"inner{inner_slot}.merge{merge_slot}"

            raw_rows = [low_product]
            raw_rows.extend(negate_rows([sum_residue, carry_residue]))
            values.update(carry_features(f"{tag}.raw", raw_rows))

            corrected_rows = list(raw_rows)
            if overflow:
                corrected_rows.append(overflow << s4)
            values.update(carry_features(f"{tag}.mod", corrected_rows))

            for name, vector in (
                ("square_sum", square_sum),
                ("square_carry", square_carry),
                ("sum_residue", sum_residue),
                ("carry_residue", carry_residue),
            ):
                for position in range(48, 76):
                    values[f"{tag}.{name}.abs{position}"] = bit(
                        vector, position
                    )
            values[f"{tag}.overflow.bit0"] = overflow & 1
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rows", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    with args.rows.open(newline="") as source:
        rows = [
            row for row in csv.DictReader(source, delimiter="\t")
            if row["physical_status"] == "constraining"
        ]

    columns: dict[str, int] = defaultdict(int)
    truth = 0
    schema = None
    for index, row in enumerate(rows):
        features = row_features(row)
        if schema is None:
            schema = set(features)
        elif set(features) != schema:
            raise RuntimeError("feature schema changed")
        for name, value in features.items():
            columns[name] |= int(bool(value)) << index
        exception = (
            int(row["physical_label"]) ^ ((int(row["low3"]) >> 1) & 1)
        )
        truth |= exception << index
        if (index + 1) % 25 == 0:
            print(f"features {index + 1}/{len(rows)}", flush=True)

    all_mask = (1 << len(rows)) - 1
    by_pattern: dict[int, list[str]] = defaultdict(list)
    for name, pattern in columns.items():
        by_pattern[pattern].append(name)

    ranking = []
    exact = []
    for pattern, names in by_pattern.items():
        representative = min(names, key=lambda name: (len(name), name))
        for orientation, predicted in (
            ("direct", pattern),
            ("inverse", pattern ^ all_mask),
        ):
            errors = (predicted ^ truth).bit_count()
            exception_miss = (truth & ~predicted & all_mask).bit_count()
            control_fire = ((~truth) & predicted & all_mask).bit_count()
            score = (
                errors, exception_miss, control_fire, orientation,
                representative, len(names),
            )
            ranking.append(score)
            if errors == 0:
                exact.append(score)
    ranking.sort()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"rows_sha256\t{digest(args.rows)}\n")
        target.write(f"rows\t{len(rows)}\n")
        target.write(f"exception_carry_ones\t{truth.bit_count()}\n")
        target.write(f"features\t{len(columns)}\n")
        target.write(f"unique_patterns\t{len(by_pattern)}\n")
        target.write(f"exact_features\t{len(exact)}\n")
        target.write("hardware_policy\tcached_labels_only_no_x87_execution\n")
        target.write("\n[ranking]\n")
        target.write(
            "errors\texception_miss\tcontrol_fire\torientation\t"
            "feature\tequivalent_features\n"
        )
        for score in ranking[:3000]:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[exact features]\n")
        for score in exact:
            target.write("\t".join(map(str, score)) + "\n")

    print(
        f"wrote {args.report} rows={len(rows)} features={len(columns)} "
        f"patterns={len(by_pattern)} exact={len(exact)} "
        f"best={ranking[0]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
