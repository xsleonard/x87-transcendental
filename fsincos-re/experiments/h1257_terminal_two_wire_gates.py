#!/usr/bin/env python3
"""Localize the six residual carry errors with fixed two-wire gates.

This is deliberately a localization audit, not a promoted selector.  It asks
whether the six incumbent carry flips, or the physical carry itself, is one
AND/OR/XOR-family function of two named circuit or patent-history wires.
The complete two-input Boolean class is covered by allowing complemented
literals.  Exact discoveries must still receive an arithmetic interpretation
and survive the full 559,867-row dense wall before they can be considered.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import defaultdict
from pathlib import Path

from h1201_post_r1186_structural_partition import structural_features
from h1248_terminal_wire_relation_mine import coordinate_features
from h1254_terminal_redundant_carry import row_features as redundant_features
from h1256_terminal_round_history_tags import row_features as history_features


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def banked(row: dict[str, str]) -> dict[str, int]:
    banks = (
        ("known", {**structural_features(row), **coordinate_features(row)}),
        ("redundant", redundant_features(row)),
        ("history", history_features(row)),
    )
    return {
        f"{bank}.{name}": int(bool(value))
        for bank, values in banks
        for name, value in values.items()
    }


def representative(names: list[str]) -> str:
    return min(names, key=lambda name: (len(name), name))


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
    schema = None
    flip_truth = 0
    carry_truth = 0
    for index, row in enumerate(rows):
        features = banked(row)
        if schema is None:
            schema = set(features)
        elif set(features) != schema:
            raise RuntimeError("feature schema changed")
        for name, value in features.items():
            columns[name] |= value << index
        flip_truth |= int(row["label"] == "POS") << index
        carry_truth |= int(row["physical_label"]) << index
        if (index + 1) % 25 == 0:
            print(f"features {index + 1}/{len(rows)}", flush=True)

    all_mask = (1 << len(rows)) - 1
    patterns: dict[int, list[str]] = defaultdict(list)
    for name, pattern in columns.items():
        patterns[pattern].append(name)

    # A literal may be a named wire or its complement.  Merge equivalent
    # literal patterns before searching so the Boolean audit is exhaustive
    # without quadratic duplication from identical wires.
    literals: dict[int, list[str]] = defaultdict(list)
    for pattern, names in patterns.items():
        for name in names:
            literals[pattern].append(name)
            literals[pattern ^ all_mask].append("!" + name)
    literal_patterns = sorted(literals)

    def search(truth: int):
        matches = set()
        supersets = [p for p in literal_patterns if p & truth == truth]
        subsets = [p for p in literal_patterns if p & ~truth & all_mask == 0]

        for left_index, left in enumerate(supersets):
            for right in supersets[left_index:]:
                if left & right == truth:
                    matches.add(("and", left, right))
        for left_index, left in enumerate(subsets):
            for right in subsets[left_index:]:
                if left | right == truth:
                    matches.add(("or", left, right))
        literal_set = set(literal_patterns)
        for left in literal_patterns:
            right = left ^ truth
            if right in literal_set and left <= right:
                matches.add(("xor", left, right))

        ranked = []
        for gate, left_pattern, right_pattern in matches:
            left = representative(literals[left_pattern])
            right = representative(literals[right_pattern])
            left_bank = left.lstrip("!").split(".", 1)[0]
            right_bank = right.lstrip("!").split(".", 1)[0]
            cross_bank = int(left_bank != right_bank)
            left_balance = min(
                left_pattern.bit_count(), len(rows) - left_pattern.bit_count()
            )
            right_balance = min(
                right_pattern.bit_count(), len(rows) - right_pattern.bit_count()
            )
            ranked.append((
                -cross_bank, -min(left_balance, right_balance),
                len(left) + len(right), gate, left, right,
                len(literals[left_pattern]), len(literals[right_pattern]),
            ))
        ranked.sort()
        return supersets, subsets, ranked

    flip_super, flip_sub, flip_matches = search(flip_truth)
    carry_super, carry_sub, carry_matches = search(carry_truth)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"rows_sha256\t{digest(args.rows)}\n")
        target.write(f"rows\t{len(rows)}\n")
        target.write(f"flip_ones\t{flip_truth.bit_count()}\n")
        target.write(f"carry_ones\t{carry_truth.bit_count()}\n")
        target.write(f"features\t{len(columns)}\n")
        target.write(f"wire_patterns\t{len(patterns)}\n")
        target.write(f"literal_patterns\t{len(literal_patterns)}\n")
        target.write(f"flip_supersets\t{len(flip_super)}\n")
        target.write(f"flip_subsets\t{len(flip_sub)}\n")
        target.write(f"exact_flip_gates\t{len(flip_matches)}\n")
        target.write(f"carry_supersets\t{len(carry_super)}\n")
        target.write(f"carry_subsets\t{len(carry_sub)}\n")
        target.write(f"exact_carry_gates\t{len(carry_matches)}\n")
        target.write("hardware_policy\tcached_labels_only_no_x87_execution\n")
        for title, matches in (
            ("exact flip gates", flip_matches),
            ("exact physical-carry gates", carry_matches),
        ):
            target.write(f"\n[{title}]\n")
            target.write(
                "cross_bank\tbalance\tgate\tleft\tright\t"
                "left_equivalents\tright_equivalents\n"
            )
            for (negative_cross, negative_balance, _, gate, left, right,
                 left_count, right_count) in matches[:5000]:
                target.write("\t".join(map(str, (
                    -negative_cross, -negative_balance, gate, left, right,
                    left_count, right_count,
                ))) + "\n")

    print(
        f"wrote {args.report} features={len(columns)} "
        f"patterns={len(patterns)} literals={len(literal_patterns)} "
        f"flip_exact={len(flip_matches)} carry_exact={len(carry_matches)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
