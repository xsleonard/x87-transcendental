#!/usr/bin/env python3
"""Localize the final dcc carry miss in named structural wires.

This is a diagnostic over the cached R1237 collision neighborhoods.  Exact
single literals and two-literal gates are reported only as hypotheses for an
arithmetic interpretation; this local population is not promotion evidence.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import defaultdict
from pathlib import Path

from h1257_terminal_two_wire_gates import banked, representative


TARGET = "3ffc dcc000000d24fdf2"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


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
    columns: dict[str, int] = defaultdict(int)
    truth = 0
    for index, row in enumerate(rows):
        for name, value in banked(row).items():
            columns[name] |= int(bool(value)) << index
        truth |= int(row["op"] == TARGET) << index
        if (index + 1) % 25 == 0:
            print(f"features {index + 1}/{len(rows)}", flush=True)

    all_mask = (1 << len(rows)) - 1
    patterns: dict[int, list[str]] = defaultdict(list)
    for name, pattern in columns.items():
        patterns[pattern].append(name)
    literals: dict[int, list[str]] = defaultdict(list)
    for pattern, names in patterns.items():
        for name in names:
            literals[pattern].append(name)
            literals[pattern ^ all_mask].append("!" + name)
    literal_patterns = sorted(literals)
    singles = sorted(literals.get(truth, []),
                     key=lambda name: (len(name), name))

    matches = set()
    supersets = [pattern for pattern in literal_patterns
                 if pattern & truth == truth]
    subsets = [pattern for pattern in literal_patterns
               if pattern & ~truth & all_mask == 0]
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
        balance = min(
            left_pattern.bit_count(), len(rows) - left_pattern.bit_count(),
            right_pattern.bit_count(), len(rows) - right_pattern.bit_count())
        ranked.append((
            -int(left_bank != right_bank), -balance,
            len(left) + len(right), gate, left, right,
            len(literals[left_pattern]), len(literals[right_pattern])))
    ranked.sort()

    near = sorted(
        ((pattern.bit_count() - 1, representative(literals[pattern]),
          len(literals[pattern])) for pattern in supersets),
        key=lambda item: (item[0], len(item[1]), item[1]))

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"rows_sha256\t{digest(args.rows)}\n")
        target.write(f"rows\t{len(rows)}\n")
        target.write(f"features\t{len(columns)}\n")
        target.write(f"wire_patterns\t{len(patterns)}\n")
        target.write(f"literal_patterns\t{len(literal_patterns)}\n")
        target.write(f"exact_single_literals\t{len(singles)}\n")
        target.write(f"exact_two_wire_gates\t{len(ranked)}\n")
        target.write("hardware_policy\tcached_labels_only_no_x87_execution\n")
        target.write("\n[exact single literals]\n")
        for name in singles:
            target.write(name + "\n")
        target.write("\n[closest target-superset literals]\n")
        target.write("false_positives\tliteral\tequivalents\n")
        for item in near[:500]:
            target.write("\t".join(map(str, item)) + "\n")
        target.write("\n[exact two-wire gates]\n")
        target.write(
            "cross_bank\tbalance\tgate\tleft\tright\t"
            "left_equivalents\tright_equivalents\n")
        for (negative_cross, negative_balance, _, gate, left, right,
             left_count, right_count) in ranked[:5000]:
            target.write("\t".join(map(str, (
                -negative_cross, -negative_balance, gate, left, right,
                left_count, right_count))) + "\n")

    print(
        f"wrote {args.report} rows={len(rows)} features={len(columns)} "
        f"singles={len(singles)} exact_gates={len(ranked)}", flush=True)


if __name__ == "__main__":
    main()
