#!/usr/bin/env python3
"""Test fixed sources and recurrences for the final-FMUL history tag.

The final Horner multiply always chops toward zero, so a history tag derived
only from that operation makes R1200 fire on all 24 causal boundary cases.
This audit tests whether a small attached state is instead forwarded or
combined from the multiply's inputs: the first Horner add and fourth power.
The predicates are fixed algebraic relations on signed direction and the
patent-motivated exact/low/half/high/all-ones classes; no bit thresholds or
operand identities are fitted.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

from h1178_round_history_state_audit import row_states
from h1210_stagea_residual_reframe import parse_dump, run
from h1222_r1200_enable_state import scalar_schedule


TARGETS = {
    "3ffc d180000005ada2ba",
    "3ffc dfc00000079c9cb7",
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def read_classifications(path: Path) -> dict[str, str]:
    values = {}
    with path.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            operand = row["op"].lower()
            classification = row["classification"]
            previous = values.setdefault(operand, classification)
            if previous != classification:
                raise RuntimeError(f"classification conflict for {operand}")
    return values


def is_toward_zero(direction: int, negative: bool) -> int:
    return int(direction == (1 if negative else -1))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("changes", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    classifications = read_classifications(args.changes)
    operands = sorted(classifications)
    _, stderr = run(args.model, "rn", operands, dump=True)
    rows = parse_dump(stderr, operands)

    records = []
    for row in rows:
        operand = row["op"]
        positive_label = classifications[operand] == "fix"
        _, adds = scalar_schedule(row, True)
        firing = [stage for stage, fields in adds.items() if fields["fires"]]
        if len(firing) != 1:
            raise RuntimeError(f"expected one firing add for {operand}: {firing}")
        negative = firing[0].startswith("negative")
        prefix = "odd" if negative else "even"
        states = row_states(row)
        directions = {
            name: int(states[f"{stage}.direction"])
            for name, stage in (
                ("square", "square"), ("fourth", "fourth"),
                ("p1", f"{prefix}_p1"), ("a1", f"{prefix}_a1"),
                ("p2", f"{prefix}_p2"), ("a2", f"{prefix}_a2"),
            )
        }
        classes = {
            name: str(states[f"{stage}.class"])
            for name, stage in (
                ("square", "square"), ("fourth", "fourth"),
                ("p1", f"{prefix}_p1"), ("a1", f"{prefix}_a1"),
                ("p2", f"{prefix}_p2"), ("a2", f"{prefix}_a2"),
            )
        }
        toward = {
            name: is_toward_zero(direction, negative)
            for name, direction in directions.items()
        }
        predicates = {
            "a1.toward_zero": toward["a1"],
            "a1.away_zero": int(bool(directions["a1"]) and not toward["a1"]),
            "a1.exact": int(directions["a1"] == 0),
            "a1.same_as_p2": int(directions["a1"] == directions["p2"]),
            "a1.not_opposed_p2": int(directions["a1"] != -directions["p2"]),
            "a1_or_p1.toward_zero": toward["a1"] | toward["p1"],
            "a1_and_p1.toward_zero": toward["a1"] & toward["p1"],
            "a1_xor_p1.toward_zero": toward["a1"] ^ toward["p1"],
            "a1_or_fourth.toward_zero": toward["a1"] | toward["fourth"],
            "a1_and_fourth.toward_zero": toward["a1"] & toward["fourth"],
            "a1_xor_fourth.toward_zero": toward["a1"] ^ toward["fourth"],
            "p1.class.low": int(classes["p1"] == "low"),
            "p1.class.high": int(classes["p1"] in ("high", "all1")),
            "a1.class.low": int(classes["a1"] == "low"),
            "a1.class.high": int(classes["a1"] in ("high", "all1")),
            "p2.class.low": int(classes["p2"] == "low"),
            "p2.class.high": int(classes["p2"] in ("high", "all1")),
            "a1_p2.same_class": int(classes["a1"] == classes["p2"]),
            "p1_p2.same_class": int(classes["p1"] == classes["p2"]),
            "a1_p2.both_low": int(
                classes["a1"] == "low" and classes["p2"] == "low"),
            "a1_p2.both_high": int(
                classes["a1"] in ("high", "all1")
                and classes["p2"] in ("high", "all1")),
            "a1_p2.opposite_side": int(
                {classes["a1"], classes["p2"]} == {"low", "high"}),
        }
        categorical = {
            "direction_sequence": tuple(directions.values()),
            "class_sequence": tuple(classes.values()),
            "a1_p2.direction_pair": (directions["a1"], directions["p2"]),
            "a1_p2.class_pair": (classes["a1"], classes["p2"]),
            "p1_a1_p2.class_tuple": (
                classes["p1"], classes["a1"], classes["p2"]),
        }
        records.append((
            operand, positive_label, firing[0], predicates, categorical,
            directions, classes,
        ))

    scores = []
    for name in sorted(records[0][3]):
        for invert in (0, 1):
            errors = sum(
                (record[3][name] ^ invert) != record[1]
                for record in records)
            target_errors = sum(
                record[0] in TARGETS
                and (record[3][name] ^ invert) != record[1]
                for record in records)
            regression_errors = sum(
                not record[1] and bool(record[3][name] ^ invert)
                for record in records)
            fix_errors = sum(
                record[1] and not bool(record[3][name] ^ invert)
                for record in records)
            scores.append((
                errors, target_errors, regression_errors, fix_errors,
                invert, name,
            ))
    scores.sort()

    partitions = []
    for name in sorted(records[0][4]):
        groups = defaultdict(Counter)
        for record in records:
            groups[record[4][name]]["fix" if record[1] else "regression"] += 1
        mixed = sum(group["fix"] and group["regression"]
                    for group in groups.values())
        rows_mixed = sum(sum(group.values()) for group in groups.values()
                         if group["fix"] and group["regression"])
        partitions.append((mixed, rows_mixed, len(groups), name, groups))
    partitions.sort(key=lambda item: (item[0], item[1], item[2], item[3]))

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"model_sha256\t{digest(args.model)}\n")
        target.write(f"changes_sha256\t{digest(args.changes)}\n")
        target.write("hardware_policy\tcached_causal_labels_no_x87_execution\n")
        target.write(f"operands\t{len(records)}\n")
        target.write("\n[fixed predicate ranking]\n")
        target.write(
            "errors\ttarget_errors\tregression_errors\tfix_errors\t"
            "invert\tpredicate\n")
        for score in scores:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[categorical collision audit]\n")
        target.write("mixed_states\trows_in_mixed\tstates\tfeature\n")
        for mixed, rows_mixed, state_count, name, _ in partitions:
            target.write(f"{mixed}\t{rows_mixed}\t{state_count}\t{name}\n")
        target.write("\n[categorical states]\n")
        target.write("feature\tstate\tfix\tregression\n")
        for _, _, _, name, groups in partitions:
            for state, group in sorted(groups.items(), key=lambda item: str(item[0])):
                target.write(
                    f"{name}\t{state}\t{group['fix']}\t{group['regression']}\n")
        target.write("\n[diagnostics]\n")
        target.write(
            "op\tclassification\tstage\tdirections\tclasses\t"
            "best_prediction\n")
        best = scores[0]
        for record in records:
            target.write("\t".join(map(str, (
                record[0], "fix" if record[1] else "regression", record[2],
                tuple(record[5].values()), tuple(record[6].values()),
                record[3][best[5]] ^ best[4],
            ))) + "\n")

    print(
        f"wrote {args.report} operands={len(records)} best={scores[0]} "
        f"best_partition={partitions[0][:4]}", flush=True)


if __name__ == "__main__":
    main()
