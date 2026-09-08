#!/usr/bin/env python3
"""Exhaust fixed two-wire gates on the current branch-local R59 banks.

This is a representation audit, not a selector fit for promotion.  Only rows
whose cached all-mode endpoint intersection fixes one physical carry value
are constraints; rows allowing either carry are omitted.  Candidate inputs
are named wires from the documented P5 multiplier trees and the fixed-width
terminal prefix network.  Both the physical carry and the complement of the
incumbent carry are searched.  Any exact expression still requires a causal
placement argument and a frozen endpoint-visible challenge.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
from collections import defaultdict
from pathlib import Path

from h1101_p5_tree_mine import row_features as product_features
from h1106_terminal_prefix_mine import terminal_features
from h1110_carry_gate_mine import allmode_allowed, extract_carry_state
from h1172_p5_cpa_predictor_mine import row_features as p5_cpa_features


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        return list(csv.DictReader(source, delimiter="\t"))


def named_features(row: dict[str, str]) -> dict[str, int]:
    values = {
        "terminal." + name: int(bool(value))
        for name, value in terminal_features(row).items()
    }
    values.update({
        "product." + name: int(bool(value))
        for name, value in product_features(row).items()
    })
    values.update({
        "p5cpa." + name: int(bool(value))
        for name, value in p5_cpa_features(row).items()
    })
    return values


def source_family(name: str) -> tuple[str, str]:
    bare = name.lstrip("!")
    fields = bare.split(".")
    family = fields[0]
    if family in ("product", "p5cpa") and len(fields) > 1:
        return family, ".".join(fields[:2])
    return family, family


def offset(name: str) -> int | None:
    match = re.search(r"\.([+-]\d+)$", name)
    return int(match.group(1)) if match else None


def representative(names: list[str]) -> str:
    return min(names, key=lambda name: (len(name), name))


def expression_rank(gate: str, left: str, right: str) -> tuple:
    left_family, left_source = source_family(left)
    right_family, right_source = source_family(right)
    placement = (0 if left_source == right_source else
                 1 if left_family == right_family else 2)
    left_offset = offset(left)
    right_offset = offset(right)
    separation = (abs(left_offset - right_offset)
                  if left_offset is not None and right_offset is not None
                  else 999)
    complements = int(left.startswith("!")) + int(right.startswith("!"))
    return placement, separation, complements, len(left) + len(right), gate


def search_truth(
        truth: int, all_mask: int,
        literals: dict[int, list[str]]) -> list[tuple]:
    patterns = sorted(literals)
    pattern_set = set(patterns)
    matches = set()

    supersets = [pattern for pattern in patterns
                 if pattern & truth == truth]
    for left_index, left in enumerate(supersets):
        for right in supersets[left_index:]:
            if left & right == truth:
                matches.add(("and", left, right))

    subsets = [pattern for pattern in patterns
               if pattern & (all_mask ^ truth) == 0]
    for left_index, left in enumerate(subsets):
        for right in subsets[left_index:]:
            if left | right == truth:
                matches.add(("or", left, right))

    for left in patterns:
        right = left ^ truth
        if right in pattern_set and left <= right:
            matches.add(("xor", left, right))

    ranked = []
    for gate, left_pattern, right_pattern in matches:
        left = representative(literals[left_pattern])
        right = representative(literals[right_pattern])
        ranked.append((
            *expression_rank(gate, left, right),
            gate, left, right,
            len(literals[left_pattern]), len(literals[right_pattern]),
        ))
    ranked.sort()
    return ranked


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("positive_allmode", type=Path)
    parser.add_argument("control_allmode", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit("refusing to overwrite " + str(args.report))

    positive = allmode_allowed(args.positive_allmode)
    controls = allmode_allowed(args.control_allmode)
    source_rows = read_rows(args.features)
    constrained = []
    schema = None
    for row in source_rows:
        allowed_delta = (positive if row["label"] == "POS" else controls)[
            row["op"]]
        state = extract_carry_state(row, allowed_delta)
        if len(state[3]) != 1:
            continue
        features = named_features(row)
        if schema is None:
            schema = sorted(features)
        elif set(features) != set(schema):
            raise RuntimeError("feature schema changed")
        constrained.append((row, state, features))
        if len(constrained) % 5000 == 0:
            print("features", len(constrained), flush=True)
    if not constrained or schema is None:
        raise RuntimeError("no carry-constraining rows")

    columns: dict[str, int] = defaultdict(int)
    carry_truth = 0
    flip_truth = 0
    for index, (_, state, features) in enumerate(constrained):
        physical = next(iter(state[3]))
        carry_truth |= physical << index
        flip_truth |= (physical ^ state[2]) << index
        for name, value in features.items():
            columns[name] |= value << index

    all_mask = (1 << len(constrained)) - 1
    columns["state.borrow"] = sum(
        state[0] << index
        for index, (_, state, _) in enumerate(constrained))
    columns["state.current_carry"] = sum(
        state[2] << index
        for index, (_, state, _) in enumerate(constrained))

    literals: dict[int, list[str]] = defaultdict(list)
    for name, pattern in columns.items():
        literals[pattern].append(name)
        literals[pattern ^ all_mask].append("!" + name)

    carry_matches = search_truth(carry_truth, all_mask, literals)
    flip_matches = search_truth(flip_truth, all_mask, literals)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write("features_sha256\t" + digest(args.features) + "\n")
        target.write("source_rows\t%d\n" % len(source_rows))
        target.write("constrained_rows\t%d\n" % len(constrained))
        target.write("neutral_rows\t%d\n" %
                     (len(source_rows) - len(constrained)))
        target.write("features\t%d\n" % len(columns))
        target.write("literal_patterns\t%d\n" % len(literals))
        target.write("carry_ones\t%d\n" % carry_truth.bit_count())
        target.write("flip_ones\t%d\n" % flip_truth.bit_count())
        target.write("exact_carry_gates\t%d\n" % len(carry_matches))
        target.write("exact_flip_gates\t%d\n" % len(flip_matches))
        target.write("hardware_policy\tcached_labels_only_no_x87_execution\n")
        for title, matches in (
                ("exact physical-carry gates", carry_matches),
                ("exact incumbent-flip gates", flip_matches)):
            target.write("\n[" + title + "]\n")
            target.write("placement\tseparation\tcomplements\tgate\tleft"
                         "\tright\tleft_equivalents\tright_equivalents\n")
            for (placement, separation, complements, _, _, gate, left,
                 right, left_count, right_count) in matches[:5000]:
                target.write("\t".join(map(str, (
                    placement, separation, complements, gate, left, right,
                    left_count, right_count))) + "\n")

    print("wrote", args.report, "rows", len(constrained),
          "features", len(columns), "patterns", len(literals),
          "carry_exact", len(carry_matches),
          "flip_exact", len(flip_matches), flush=True)


if __name__ == "__main__":
    main()
