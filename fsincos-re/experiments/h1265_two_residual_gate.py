#!/usr/bin/env python3
"""Search fixed two-wire gates for the two post-R1263 residuals.

R1263 resolves the four exact truncated-thirds equality cases with a fixed
right-product carry/kill gate.  The remaining d800 and dcc rows are not the
same mechanism: d800 requires the upper thirds tap and dcc is invariant under
all four tap settings.  This cached-only localization pass asks whether the
pair is nevertheless one Boolean function of two already reconstructed
circuit/history wires.  A hit is diagnostic, not sufficient for promotion.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import defaultdict
from pathlib import Path

from h1257_terminal_two_wire_gates import banked, representative


TARGETS = {
    "3ffc d80000000b15da62",
    "3ffc dcc000000d24fdf2",
}


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
        rows = [
            row for row in csv.DictReader(source, delimiter="\t")
            if row["physical_status"] == "constraining"
        ]
    columns: dict[str, int] = defaultdict(int)
    truth = 0
    for index, row in enumerate(rows):
        for name, value in banked(row).items():
            columns[name] |= int(bool(value)) << index
        truth |= int(row["op"] in TARGETS) << index
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
        balance = min(
            left_pattern.bit_count(), len(rows) - left_pattern.bit_count(),
            right_pattern.bit_count(), len(rows) - right_pattern.bit_count(),
        )
        ranked.append((
            -cross_bank, -balance, len(left) + len(right), gate, left, right,
            len(literals[left_pattern]), len(literals[right_pattern]),
        ))
    ranked.sort()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"rows_sha256\t{digest(args.rows)}\n")
        target.write(f"rows\t{len(rows)}\n")
        target.write(f"targets\t{truth.bit_count()}\n")
        target.write(f"features\t{len(columns)}\n")
        target.write(f"wire_patterns\t{len(patterns)}\n")
        target.write(f"literal_patterns\t{len(literal_patterns)}\n")
        target.write(f"exact_two_wire_gates\t{len(ranked)}\n")
        target.write("hardware_policy\tcached_labels_only_no_x87_execution\n")
        target.write("\n[exact two-wire gates]\n")
        target.write(
            "cross_bank\tbalance\tgate\tleft\tright\t"
            "left_equivalents\tright_equivalents\n"
        )
        for (negative_cross, negative_balance, _, gate, left, right,
             left_count, right_count) in ranked[:5000]:
            target.write("\t".join(map(str, (
                -negative_cross, -negative_balance, gate, left, right,
                left_count, right_count,
            ))) + "\n")

    print(
        f"wrote {args.report} rows={len(rows)} features={len(columns)} "
        f"exact_gates={len(ranked)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
