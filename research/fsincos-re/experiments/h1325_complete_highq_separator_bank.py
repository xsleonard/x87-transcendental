#!/usr/bin/env python3
"""Freeze every still-uncaptured high-q separator in the h1313 scan wall.

The h1313 bank deliberately selected only one operand per occupied
(q, product cut, tail-top-four-bits) stratum.  That was useful as a first
adversarial bank, but it left most of the architectural predecessor-versus-
wide separators in the already committed 1.15-billion-significand scan
unlabelled.  This pass repeats the same software-only scan and eligibility
filter, retains every separator, and removes exact (mode, operand) pairs that
have already been captured.  It therefore grows the label population without
repeating deterministic hardware measurements.

No x87 instruction is executed by this program.  Model outputs and capture
inputs are frozen before the hardware capture.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from h1210_stagea_residual_reframe import run
from h1241_r1237_adversarial_bank import stagea_members
from h1313_highq_tail_stratified_bank import (
    MODES,
    anchors,
    digest,
    merged_intervals,
    operands_in,
    scan_interval,
)


def captured_pairs(directory: Path) -> set[tuple[str, str]]:
    """Read exact mode/operand pairs from a prior capture directory."""

    result: set[tuple[str, str]] = set()
    for mode in MODES:
        path = directory / f"{mode}_inputs.txt"
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            operand = " ".join(line.lower().split())
            if operand:
                result.add((mode, operand))
    return result


def rendered_row(row: dict[str, object]) -> dict[str, object]:
    result = dict(row)
    result["remainder"] = f"{int(row['remainder']):016x}"
    result["tail_top4"] = f"{int(row['tail_top4']):x}"
    result["tail_top8"] = f"{int(row['tail_top8']):02x}"
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scanner", type=Path)
    parser.add_argument("predecessor", type=Path)
    parser.add_argument("wide", type=Path)
    parser.add_argument("causal_legs", type=Path)
    parser.add_argument("sibling_labels", type=Path)
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("output_prefix", type=Path)
    parser.add_argument("capture_directory", type=Path)
    parser.add_argument("--exclude", action="append", type=Path, default=[])
    parser.add_argument(
        "--captured-dir", action="append", type=Path, default=[])
    parser.add_argument("--radius", type=int, default=50_000_000)
    args = parser.parse_args()

    manifest_path = args.output_prefix.with_name(
        args.output_prefix.name + "_manifest.tsv")
    changes_path = args.output_prefix.with_name(
        args.output_prefix.name + "_changes.tsv")
    report_path = args.output_prefix.with_name(
        args.output_prefix.name + "_report.txt")
    for output_path in (manifest_path, changes_path, report_path):
        if output_path.exists():
            raise SystemExit(f"refusing to overwrite {output_path}")
    if args.capture_directory.exists():
        raise SystemExit(
            f"refusing to use existing capture directory "
            f"{args.capture_directory}")

    anchor_values = anchors(args.causal_legs, args.sibling_labels)
    intervals = merged_intervals(anchor_values, args.radius)
    with ThreadPoolExecutor(max_workers=min(4, len(intervals))) as executor:
        scanned_lists = list(executor.map(
            lambda interval: scan_interval(args.scanner, interval), intervals))
    scanned: dict[str, dict[str, object]] = {}
    for rows in scanned_lists:
        for row in rows:
            scanned[str(row["op"])] = row
    candidates = set(scanned)

    excluded_operands: set[str] = set()
    for path in args.exclude:
        excluded_operands.update(operands_in(path))
    stagea = stagea_members(args.capture_root, candidates)
    fresh_rows = [
        row for operand, row in scanned.items()
        if operand not in excluded_operands and operand not in stagea
    ]
    fresh_rows.sort(key=lambda row: str(row["op"]))

    operands = [str(row["op"]) for row in fresh_rows]
    outputs: dict[tuple[str, str], list[str]] = {}
    for mode in MODES:
        predecessor_values, _ = run(args.predecessor, mode, operands)
        wide_values, _ = run(args.wide, mode, operands)
        outputs[mode, "predecessor"] = predecessor_values
        outputs[mode, "wide"] = wide_values

    separators = []
    for index, source_row in enumerate(fresh_rows):
        changed_modes = [
            mode for mode in MODES
            if outputs[mode, "predecessor"][index]
            != outputs[mode, "wide"][index]
        ]
        if not changed_modes:
            continue
        row = dict(source_row)
        row["changed_modes"] = ",".join(changed_modes)
        for mode in MODES:
            row[f"{mode}_predecessor"] = outputs[mode, "predecessor"][index]
            row[f"{mode}_wide"] = outputs[mode, "wide"][index]
        separators.append(row)
    separators.sort(key=lambda row: (
        int(row["q"]), int(row["cut"]), int(row["tail_top4"]),
        str(row["op"]),
    ))
    if not separators:
        raise RuntimeError("no fresh architectural separators")

    prior_pairs: set[tuple[str, str]] = set()
    for directory in args.captured_dir:
        prior_pairs.update(captured_pairs(directory))

    changes = []
    omitted_prior = []
    metadata = (
        "q", "cut", "retained_lsb", "product_bit65", "r1237_fire",
        "word", "remainder", "tail_top4", "tail_top8",
        "tail_leading_zeros",
    )
    for row in separators:
        for mode in str(row["changed_modes"]).split(","):
            change = {
                "mode": mode,
                "op": str(row["op"]),
                **{name: row[name] for name in metadata},
                "predecessor": row[f"{mode}_predecessor"],
                "wide": row[f"{mode}_wide"],
            }
            if (mode, str(row["op"])) in prior_pairs:
                omitted_prior.append(change)
            else:
                changes.append(change)
    changes.sort(key=lambda row: (
        MODES.index(str(row["mode"])), str(row["op"])))
    if not changes:
        raise RuntimeError("no uncaptured separator legs")
    keys = [(str(row["mode"]), str(row["op"])) for row in changes]
    if len(keys) != len(set(keys)):
        raise RuntimeError("duplicate fresh capture pair")
    overlap = set(keys) & prior_pairs
    if overlap:
        raise RuntimeError(f"prior capture pairs survived exclusion: {overlap}")

    manifest_columns = (
        "op", "q", "cut", "retained_lsb", "product_bit65",
        "r1237_fire", "word", "remainder", "tail_top4", "tail_top8",
        "tail_leading_zeros", "changed_modes",
        "rn_predecessor", "rn_wide", "rd_predecessor", "rd_wide",
        "ru_predecessor", "ru_wide",
    )
    change_columns = tuple(changes[0])
    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("x", newline="") as target:
        writer = csv.DictWriter(target, manifest_columns, delimiter="\t")
        writer.writeheader()
        for row in separators:
            writer.writerow(rendered_row(row))
    with changes_path.open("x", newline="") as target:
        writer = csv.DictWriter(target, change_columns, delimiter="\t")
        writer.writeheader()
        for row in changes:
            writer.writerow(rendered_row(row))

    args.capture_directory.mkdir(parents=True)
    for mode in MODES:
        input_path = args.capture_directory / f"{mode}_inputs.txt"
        with input_path.open("x") as target:
            for row in changes:
                if row["mode"] == mode:
                    target.write(str(row["op"]) + "\n")

    counts = Counter()
    for row in separators:
        counts[f"separator.q.{row['q']}.cut.{row['cut']}"] += 1
        for mode in str(row["changed_modes"]).split(","):
            counts[f"separator.mode.{mode}"] += 1
    for row in omitted_prior:
        counts[f"omitted_prior.mode.{row['mode']}"] += 1
    for row in changes:
        counts[f"capture.mode.{row['mode']}"] += 1
        counts[f"capture.q.{row['q']}.cut.{row['cut']}"] += 1

    with report_path.open("x") as target:
        target.write(f"scanner_sha256\t{digest(args.scanner)}\n")
        target.write(f"predecessor_sha256\t{digest(args.predecessor)}\n")
        target.write(f"wide_sha256\t{digest(args.wide)}\n")
        target.write(f"causal_legs_sha256\t{digest(args.causal_legs)}\n")
        target.write(f"sibling_labels_sha256\t{digest(args.sibling_labels)}\n")
        target.write("selection_policy\tall_architectural_separators\n")
        target.write("repeat_policy\texact_mode_operand_pairs_omitted\n")
        target.write("rz_policy\tomitted_positive_result_duplicate_of_rd\n")
        target.write("hardware_execution\tnone\n")
        target.write(f"radius\t{args.radius}\n")
        target.write(f"anchors\t{len(anchor_values)}\n")
        target.write(f"merged_intervals\t{len(intervals)}\n")
        target.write(
            f"scanner_input_significands\t"
            f"{sum(last-first+1 for first, last in intervals)}\n")
        target.write(f"high_events\t{len(scanned)}\n")
        target.write(
            f"explicit_excluded\t{len(candidates & excluded_operands)}\n")
        target.write(f"stagea_excluded\t{len(stagea)}\n")
        target.write(f"fresh_high_events\t{len(fresh_rows)}\n")
        target.write(f"architectural_separators\t{len(separators)}\n")
        target.write(
            f"architectural_separator_legs\t"
            f"{sum(len(str(row['changed_modes']).split(',')) for row in separators)}\n")
        target.write(f"known_capture_pairs\t{len(prior_pairs)}\n")
        target.write(f"omitted_prior_separator_legs\t{len(omitted_prior)}\n")
        target.write(f"frozen_capture_legs\t{len(changes)}\n")
        target.write(
            f"frozen_capture_operands\t"
            f"{len({str(row['op']) for row in changes})}\n")
        target.write(f"manifest_sha256\t{digest(manifest_path)}\n")
        target.write(f"changes_sha256\t{digest(changes_path)}\n")
        for mode in MODES:
            input_path = args.capture_directory / f"{mode}_inputs.txt"
            target.write(f"inputs_sha256.{mode}\t{digest(input_path)}\n")
        target.write("\n[counts]\n")
        for name, count in sorted(counts.items()):
            target.write(f"{name}\t{count}\n")

    print(
        f"wrote {report_path}: scanned="
        f"{sum(last-first+1 for first,last in intervals)} "
        f"events={len(scanned)} separators={len(separators)} "
        f"prior_legs={len(omitted_prior)} capture_legs={len(changes)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
