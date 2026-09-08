#!/usr/bin/env python3
"""Score the frozen h1351 FCOS bank against the h1350 mux candidate."""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

from h1315_score_tail_stratified_blind import CAPTURE_MODES, load_capture


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("changes", type=Path)
    parser.add_argument("capture_directory", type=Path)
    parser.add_argument("freeze_report", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    labels_path = args.report.with_name(args.report.stem + "_labels.tsv")
    for output_path in (args.report, labels_path):
        if output_path.exists():
            raise SystemExit(f"refusing to overwrite {output_path}")

    with args.changes.open(newline="") as source:
        changes = list(csv.DictReader(source, delimiter="\t"))
    captured = load_capture(args.capture_directory)
    expected = {(row["mode"], row["op"].lower()) for row in changes}
    if set(captured) != expected:
        raise RuntimeError(
            f"capture mismatch: missing={expected-set(captured)} "
            f"extra={set(captured)-expected}")

    counts = Counter()
    labels = []
    actual_by_operand: dict[str, set[str]] = defaultdict(set)
    mismatch_rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    predictors = (
        ("term_a", "term_a"),
        ("term_a_alias", "term_a_alias"),
        ("term_b", "term_b"),
        ("mux_union", "mux_union"),
        ("mux_union_alias", "mux_union_alias"),
    )
    for row in changes:
        key = row["mode"], row["op"].lower()
        hardware = captured[key]
        if hardware == row["predecessor"].lower():
            actual = "predecessor"
        elif hardware == row["wide"].lower():
            actual = "wide"
        else:
            actual = "neither"
        counts[f"actual.{actual}"] += 1
        counts[f"mode.{row['mode']}.actual.{actual}"] += 1
        counts[f"q.{row['q']}.cut.{row['cut']}.actual.{actual}"] += 1
        counts[
            f"state.l{row['low69']}.c{row['square_cin29']}."
            f"a{row['square_generate47']}.g{row['fourth_generate5']}."
            f"actual.{actual}"
        ] += 1
        actual_by_operand[row["op"].lower()].add(actual)
        scored = dict(row)
        scored.update({"hardware": hardware, "actual_verdict": actual})
        for name, field in predictors:
            predicted = "wide" if int(row[field]) else "predecessor"
            correct = predicted == actual
            outcome = (
                "tp" if predicted == "wide" and actual == "wide" else
                "fp" if predicted == "wide" else
                "tn" if actual == "predecessor" else "fn"
            )
            counts[f"predictor.{name}.{outcome}"] += 1
            counts[f"predictor.{name}.correct.{int(correct)}"] += 1
            scored[f"{name}_predicted"] = predicted
            scored[f"{name}_correct"] = int(correct)
            if not correct:
                mismatch_rows[name].append(scored)
        labels.append(scored)

    inconsistent = {
        operand: verdicts
        for operand, verdicts in actual_by_operand.items()
        if len(verdicts) != 1 or "neither" in verdicts
    }
    if inconsistent:
        raise RuntimeError(f"inconsistent causal verdicts: {inconsistent}")

    columns = tuple(labels[0])
    with labels_path.open("x", newline="") as target:
        writer = csv.DictWriter(target, columns, delimiter="\t")
        writer.writeheader()
        writer.writerows(labels)
    with args.report.open("x") as target:
        target.write(f"changes_sha256\t{digest(args.changes)}\n")
        target.write(f"freeze_report_sha256\t{digest(args.freeze_report)}\n")
        for mode in CAPTURE_MODES:
            target.write(
                f"inputs_sha256.{mode}\t"
                f"{digest(args.capture_directory / f'{mode}_inputs.txt')}\n")
            target.write(
                f"hardware_sha256.{mode}\t"
                f"{digest(args.capture_directory / f'{mode}_hardware.txt')}\n")
        target.write("hardware_policy\tone_capture_per_mode_operand_pair\n")
        target.write("capture_processor\tIntel_Core_i7-6700\n")
        target.write(f"separator_legs\t{len(labels)}\n")
        target.write(f"separator_operands\t{len(actual_by_operand)}\n")
        target.write(f"labels_sha256\t{digest(labels_path)}\n")
        target.write("\n[counts]\n")
        for name, count in sorted(counts.items()):
            target.write(f"{name}\t{count}\n")
        for name, _ in predictors:
            target.write(f"\n[mismatches.{name}]\n")
            for row in mismatch_rows[name]:
                target.write(
                    f"{row['mode']}\t{row['op']}\tq={row['q']}\t"
                    f"cut={row['cut']}\tstate={row['low69']}"
                    f"{row['square_cin29']}{row['square_generate47']}"
                    f"{row['fourth_generate5']}\tactual="
                    f"{row['actual_verdict']}\n")

    print(
        f"wrote {args.report}: legs={len(labels)} "
        f"wide={counts['actual.wide']} "
        f"mux_errors={counts['predictor.mux_union.correct.0']} "
        f"alias_errors={counts['predictor.mux_union_alias.correct.0']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
