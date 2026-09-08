#!/usr/bin/env python3
"""Mine two-wire arithmetic relations for the six R1237 residuals.

R1237 became structural when a fitted decision reduced to equality between
an exact halfway-distance bit and a selected multiplier-CPA bit.  This pass
asks the analogous, deliberately narrower question at the terminal FSUB:
does a named circuit wire differ from a natural terminal-coordinate bit on
exactly the six required carry flips?

Only XOR/XNOR relations between different feature families are admitted.
The result is a localization aid, not a correction rule; any survivor still
requires an arithmetic interpretation and a complete dense-wall test.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import defaultdict
from pathlib import Path

from h1201_post_r1186_structural_partition import structural_features
from h1178_round_history_state_audit import signed128


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def bit(value: int, position: int) -> int:
    if position < 0:
        return 0
    return (value >> position) & 1


def coordinate_features(row: dict[str, str]) -> dict[str, int]:
    values: dict[str, int] = {}
    cut = int(row["k"])
    unsigned = {
        "S": int(row["S"], 16),
        "B": int(row["B"], 16),
        "SxorB": int(row["S"], 16) ^ int(row["B"], 16),
        "umag": int(row["umag"], 16),
        "t4": int(row["t4"], 16),
        "sqlow": int(row["sqlow"], 16),
        "rd3": int(row["rd3"], 16),
    }
    for name in ("S", "B", "SxorB", "umag"):
        for offset in range(-32, 33):
            values[f"coord.{name}.cut{offset:+d}"] = bit(
                unsigned[name], cut + offset)
    for name in ("t4", "sqlow", "rd3"):
        for position in range(48, 76):
            values[f"coord.{name}.abs{position}"] = bit(
                unsigned[name], position)

    mreg = signed128(row["Mreg"])
    # Two's-complement bits of M at and around the natural R60 radix point.
    for position in range(48, 76):
        values[f"coord.Mreg.abs{position}"] = bit(mreg, position)
    fields = {
        "low3": (int(row["low3"]), 3),
        "payload": (int(row["payload"]), 4),
        "b1": (int(row["b1"]), 1),
        "b2": (int(row["b2"]), 1),
        "theta": (int(row["theta"]) & 3, 2),
    }
    for name, (value, width) in fields.items():
        for position in range(width):
            values[f"coord.{name}.bit{position}"] = bit(value, position)
    return values


def family(name: str) -> str:
    return name.split(".", 1)[0]


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
    if not rows:
        raise SystemExit("no constraining rows")

    columns: dict[str, int] = defaultdict(int)
    target_mask = 0
    schema = None
    for index, row in enumerate(rows):
        circuit = structural_features(row)
        coordinate = coordinate_features(row)
        features = {**circuit, **coordinate}
        if schema is None:
            schema = set(features)
        elif set(features) != schema:
            raise RuntimeError("feature schema changed")
        for name, value in features.items():
            columns[name] |= int(bool(value)) << index
        target_mask |= int(row["label"] == "POS") << index
        if (index + 1) % 50 == 0:
            print(f"features {index + 1}/{len(rows)}", flush=True)

    all_mask = (1 << len(rows)) - 1
    by_pattern: dict[int, list[str]] = defaultdict(list)
    for name, pattern in columns.items():
        by_pattern[pattern].append(name)

    matches = []
    seen = set()
    for left, left_pattern in columns.items():
        for relation, wanted in (
            ("xor", left_pattern ^ target_mask),
            ("xnor", left_pattern ^ (all_mask ^ target_mask)),
        ):
            for right in by_pattern.get(wanted, ()):
                if family(left) == family(right):
                    continue
                pair = tuple(sorted((left, right))) + (relation,)
                if pair in seen:
                    continue
                seen.add(pair)
                left_ones = columns[left].bit_count()
                right_ones = columns[right].bit_count()
                balance = min(
                    left_ones, len(rows) - left_ones,
                    right_ones, len(rows) - right_ones,
                )
                # Prefer informative wires and coordinate/circuit relations.
                cross_coordinate = int(
                    (left.startswith("coord."))
                    != (right.startswith("coord.")))
                matches.append((
                    -cross_coordinate, -balance,
                    len(left) + len(right), relation, left, right,
                    left_ones, right_ones,
                ))
    matches.sort()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"rows_sha256\t{digest(args.rows)}\n")
        target.write(f"rows\t{len(rows)}\n")
        target.write(f"targets\t{target_mask.bit_count()}\n")
        target.write(f"features\t{len(columns)}\n")
        target.write(f"unique_patterns\t{len(by_pattern)}\n")
        target.write(f"exact_cross_family_relations\t{len(matches)}\n")
        target.write("\n[ranking]\n")
        target.write(
            "cross_coordinate\tbalance\trelation\tleft\tright\t"
            "left_ones\tright_ones\n")
        for (negative_cross, negative_balance, _, relation, left, right,
             left_ones, right_ones) in matches[:2000]:
            target.write("\t".join(map(str, (
                -negative_cross, -negative_balance, relation, left, right,
                left_ones, right_ones,
            ))) + "\n")

    print(
        f"wrote {args.report} rows={len(rows)} features={len(columns)} "
        f"exact_relations={len(matches)}", flush=True)


if __name__ == "__main__":
    main()
