#!/usr/bin/env python3
"""Freeze a no-repeat adversarial bank for the h1350 power-tree mux.

The h1350 expression was discovered on all 189 labels in the first complete
high-q separator wall, so its one-error score is not validation.  This pass
scans wider deterministic neighborhoods, retains only fresh architectural
predecessor-versus-wide separators, and covers the candidate's complete
observable truth-table state:

* current q and terminal product cut;
* fourth-power external low-product bit 69;
* square final carry-in 29 and its training-equivalent generate-47 alias;
* fourth full-tree generate bit 5;
* the two component terms and their union; and
* a uniform top-nibble partition of the exact second-Horner-product tail.

Selection is a greedy set cover over those predeclared software categories.
It never reads a hardware label.  Previously captured mode/operand pairs are
removed exactly, and stage-A operands are excluded conservatively.  The
resulting model endpoints and capture inputs are frozen before hardware use.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from h1210_stagea_residual_reframe import parse_dump, run
from h1241_r1237_adversarial_bank import stagea_members
from h1313_highq_tail_stratified_bank import (
    MODES,
    merged_intervals,
    scan_interval,
)
from h1346_highq_power_tree_wire_audit import power_features
from h1350_highq_power_mux_candidate import (
    FOURTH_GENERATE,
    LOW,
    SQUARE_CARRY,
    SQUARE_GENERATE,
    predictions,
)


OPERAND = re.compile(r"\b([0-9a-fA-F]{4})[ :\t]+([0-9a-fA-F]{16})\b")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def direct_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    if not rows or "op" not in rows[0]:
        raise RuntimeError(f"direct label bank has no op column: {path}")
    return rows


def prior_pairs(
        label_banks: list[Path], capture_directories: list[Path]
        ) -> set[tuple[str, str]]:
    result = set()
    for path in label_banks:
        for row in direct_rows(path):
            if row.get("mode") in MODES:
                result.add((row["mode"], row["op"].lower()))
    for directory in capture_directories:
        for mode in MODES:
            path = directory / f"{mode}_inputs.txt"
            if not path.exists():
                continue
            for line in path.read_text().splitlines():
                operand = " ".join(line.lower().split())
                if operand:
                    result.add((mode, operand))
    return result


def anchors(label_banks: list[Path]) -> list[int]:
    values = set()
    for path in label_banks:
        for row in direct_rows(path):
            sign_exponent, significand = row["op"].lower().split()
            if sign_exponent != "3ffc":
                raise RuntimeError(f"unexpected high-q exponent: {row['op']}")
            values.add(int(significand, 16))
    return sorted(values)


def operands_in(path: Path) -> set[str]:
    result = set()
    paths = sorted(path.glob("*_inputs.txt")) if path.is_dir() else [path]
    for source in paths:
        for match in OPERAND.finditer(source.read_text()):
            result.add(f"{match.group(1).lower()} {match.group(2).lower()}")
    return result


def categories(row: dict[str, object]) -> set[str]:
    q = int(row["q"])
    cut = int(row["cut"])
    low = int(row["low69"])
    carry = int(row["square_cin29"])
    alias = int(row["square_generate47"])
    generate = int(row["fourth_generate5"])
    term_a = int(row["term_a"])
    term_b = int(row["term_b"])
    union = int(row["mux_union"])
    top4 = int(row["tail_top4"])
    result = {
        f"state.q{q}.cut{cut}.l{low}.c{carry}.a{alias}.g{generate}",
        f"route.q{q}.cut{cut}.A{term_a}.B{term_b}",
        f"candidate.q{q}.cut{cut}.union{union}",
        f"tail.q{q}.cut{cut}.top4.{top4:x}",
        f"alias.q{q}.cut{cut}.{'same' if carry == alias else 'different'}",
    }
    if cut == 63 and low == 0 and carry == 0 and generate == 0:
        result.add(f"dcc_like.q{q}")
    if term_a != term_b:
        result.add(f"route_disagreement.q{q}.cut{cut}")
    if carry != alias:
        result.add(f"training_alias_disagreement.q{q}.cut{cut}")
    return result


def tail_center_distance(row: dict[str, object]) -> int:
    cut = int(row["cut"])
    top4 = int(row["tail_top4"])
    remainder = int(row["remainder"])
    return abs((remainder << 5) - (2 * top4 + 1) * (1 << cut))


def select_cover(
        rows: list[dict[str, object]], maximum: int
        ) -> list[dict[str, object]]:
    for row in rows:
        row["categories"] = categories(row)
    uncovered = set().union(*(row["categories"] for row in rows))
    selected = []
    remaining = list(rows)
    while remaining and uncovered and len(selected) < maximum:
        remaining.sort(key=lambda row: (
            -len(row["categories"] & uncovered),
            tail_center_distance(row),
            str(row["op"]),
        ))
        chosen = remaining.pop(0)
        selected.append(chosen)
        uncovered.difference_update(chosen["categories"])
    return sorted(selected, key=lambda row: str(row["op"]))


def rendered(row: dict[str, object]) -> dict[str, object]:
    result = dict(row)
    result["remainder"] = f"{int(row['remainder']):016x}"
    result["tail_top4"] = f"{int(row['tail_top4']):x}"
    result["tail_top8"] = f"{int(row['tail_top8']):02x}"
    result["categories"] = ",".join(sorted(row["categories"]))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scanner", type=Path)
    parser.add_argument("predecessor", type=Path)
    parser.add_argument("wide", type=Path)
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("output_prefix", type=Path)
    parser.add_argument("capture_directory", type=Path)
    parser.add_argument(
        "--label-bank", action="append", type=Path, required=True)
    parser.add_argument(
        "--captured-dir", action="append", type=Path, default=[])
    parser.add_argument("--exclude", action="append", type=Path, default=[])
    parser.add_argument("--radius", type=int, default=100_000_000)
    parser.add_argument("--max-operands", type=int, default=128)
    args = parser.parse_args()

    manifest_path = args.output_prefix.with_name(
        args.output_prefix.name + "_manifest.tsv")
    changes_path = args.output_prefix.with_name(
        args.output_prefix.name + "_changes.tsv")
    report_path = args.output_prefix.with_name(
        args.output_prefix.name + "_report.txt")
    for path in (manifest_path, changes_path, report_path):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")
    if args.capture_directory.exists():
        raise SystemExit(
            f"refusing to use existing capture directory "
            f"{args.capture_directory}")

    anchor_values = anchors(args.label_bank)
    intervals = merged_intervals(anchor_values, args.radius)
    with ThreadPoolExecutor(max_workers=min(4, len(intervals))) as executor:
        scanned_lists = list(executor.map(
            lambda interval: scan_interval(args.scanner, interval), intervals))
    scanned = {}
    for rows in scanned_lists:
        for row in rows:
            scanned[str(row["op"])] = row

    excluded_operands = set()
    for path in [*args.label_bank, *args.exclude, *args.captured_dir]:
        excluded_operands.update(operands_in(path))
    candidates = set(scanned)
    stagea = stagea_members(args.capture_root, candidates)
    fresh_rows = [
        row for operand, row in scanned.items()
        if operand not in excluded_operands and operand not in stagea
    ]
    fresh_rows.sort(key=lambda row: str(row["op"]))

    operands = [str(row["op"]) for row in fresh_rows]
    outputs: dict[tuple[str, str], list[str]] = {}
    for mode in MODES:
        outputs[mode, "predecessor"], _ = run(
            args.predecessor, mode, operands)
        outputs[mode, "wide"], _ = run(args.wide, mode, operands)

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

    separator_operands = [str(row["op"]) for row in separators]
    _, stderr = run(args.predecessor, "rn", separator_operands, dump=True)
    dump_rows = parse_dump(stderr, separator_operands)
    if len(dump_rows) != len(separators):
        raise RuntimeError("separator dump length mismatch")
    for row, dump_row in zip(separators, dump_rows):
        values = power_features(dump_row)
        candidate = predictions(values, int(row["cut"]))
        row.update({
            "low69": values[LOW],
            "square_cin29": values[SQUARE_CARRY],
            "square_generate47": values[SQUARE_GENERATE],
            "fourth_generate5": values[FOURTH_GENERATE],
            **candidate,
            "candidate_verdict": (
                "wide" if candidate["mux_union"] else "predecessor"),
        })

    known_pairs = prior_pairs(args.label_bank, args.captured_dir)
    eligible = []
    omitted_pairs = 0
    for row in separators:
        fresh_modes = [
            mode for mode in str(row["changed_modes"]).split(",")
            if (mode, str(row["op"])) not in known_pairs
        ]
        omitted_pairs += len(str(row["changed_modes"]).split(",")) - len(
            fresh_modes)
        if fresh_modes:
            row["changed_modes"] = ",".join(fresh_modes)
            eligible.append(row)
    if not eligible:
        raise RuntimeError("no uncaptured architectural separators")

    selected = select_cover(eligible, args.max_operands)
    changes = []
    metadata = (
        "q", "cut", "retained_lsb", "product_bit65", "r1237_fire",
        "word", "remainder", "tail_top4", "tail_top8",
        "tail_leading_zeros", "low69", "square_cin29",
        "square_generate47", "fourth_generate5", "term_a",
        "term_a_alias", "term_b", "mux_union", "mux_union_alias",
        "candidate_verdict", "categories",
    )
    for row in selected:
        for mode in str(row["changed_modes"]).split(","):
            changes.append({
                "mode": mode,
                "op": row["op"],
                **{name: row[name] for name in metadata},
                "predecessor": row[f"{mode}_predecessor"],
                "wide": row[f"{mode}_wide"],
            })
    changes.sort(key=lambda row: (MODES.index(str(row["mode"])), row["op"]))
    keys = [(str(row["mode"]), str(row["op"])) for row in changes]
    if len(keys) != len(set(keys)):
        raise RuntimeError("duplicate selected capture pair")
    overlap = set(keys) & known_pairs
    if overlap:
        raise RuntimeError(f"known capture pairs survived exclusion: {overlap}")

    manifest_columns = (
        "op", "q", "cut", "retained_lsb", "product_bit65",
        "r1237_fire", "word", "remainder", "tail_top4", "tail_top8",
        "tail_leading_zeros", "low69", "square_cin29",
        "square_generate47", "fourth_generate5", "term_a",
        "term_a_alias", "term_b", "mux_union", "mux_union_alias",
        "candidate_verdict", "categories", "changed_modes",
        "rn_predecessor", "rn_wide", "rd_predecessor", "rd_wide",
        "ru_predecessor", "ru_wide",
    )
    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("x", newline="") as target:
        writer = csv.DictWriter(target, manifest_columns, delimiter="\t")
        writer.writeheader()
        for row in selected:
            writer.writerow(rendered(row))
    with changes_path.open("x", newline="") as target:
        writer = csv.DictWriter(target, tuple(changes[0]), delimiter="\t")
        writer.writeheader()
        for row in changes:
            writer.writerow(rendered(row))

    args.capture_directory.mkdir(parents=True)
    for mode in MODES:
        path = args.capture_directory / f"{mode}_inputs.txt"
        with path.open("x") as target:
            for row in changes:
                if row["mode"] == mode:
                    target.write(str(row["op"]) + "\n")

    counts = Counter()
    for row in separators:
        counts[f"separators.q.{row['q']}.cut.{row['cut']}"] += 1
    for row in eligible:
        counts[f"eligible.candidate.{row['candidate_verdict']}"] += 1
    for row in selected:
        counts[f"selected.candidate.{row['candidate_verdict']}"] += 1
        counts[f"selected.q.{row['q']}.cut.{row['cut']}"] += 1
    for row in changes:
        counts[f"capture.mode.{row['mode']}"] += 1

    with report_path.open("x") as output:
        output.write(f"scanner_sha256\t{digest(args.scanner)}\n")
        output.write(f"predecessor_sha256\t{digest(args.predecessor)}\n")
        output.write(f"wide_sha256\t{digest(args.wide)}\n")
        for index, path in enumerate(args.label_bank):
            output.write(f"label_bank_sha256.{index}\t{digest(path)}\n")
        output.write("selection_policy\tgreedy_cover_of_predeclared_power_mux_states\n")
        output.write("repeat_policy\texact_mode_operand_pairs_omitted\n")
        output.write("hardware_execution\tnone\n")
        output.write(f"radius\t{args.radius}\n")
        output.write(f"anchors\t{len(anchor_values)}\n")
        output.write(f"merged_intervals\t{len(intervals)}\n")
        output.write(
            "scanner_input_significands\t"
            f"{sum(last-first+1 for first, last in intervals)}\n")
        output.write(f"high_events\t{len(scanned)}\n")
        output.write(f"explicit_excluded\t{len(candidates & excluded_operands)}\n")
        output.write(f"stagea_excluded\t{len(stagea)}\n")
        output.write(f"fresh_high_events\t{len(fresh_rows)}\n")
        output.write(f"architectural_separators\t{len(separators)}\n")
        output.write(f"known_capture_pairs\t{len(known_pairs)}\n")
        output.write(f"omitted_prior_separator_legs\t{omitted_pairs}\n")
        output.write(f"eligible_separator_operands\t{len(eligible)}\n")
        output.write(f"selected_operands\t{len(selected)}\n")
        output.write(f"frozen_capture_legs\t{len(changes)}\n")
        output.write(
            "covered_categories\t"
            f"{len(set().union(*(row['categories'] for row in selected)))}\n")
        output.write(
            "available_categories\t"
            f"{len(set().union(*(categories(row) for row in eligible)))}\n")
        output.write(f"manifest_sha256\t{digest(manifest_path)}\n")
        output.write(f"changes_sha256\t{digest(changes_path)}\n")
        for mode in MODES:
            path = args.capture_directory / f"{mode}_inputs.txt"
            output.write(f"inputs_sha256.{mode}\t{digest(path)}\n")
        output.write("\n[counts]\n")
        for name, count in sorted(counts.items()):
            output.write(f"{name}\t{count}\n")

    print(
        f"wrote {report_path}: scanned="
        f"{sum(last-first+1 for first,last in intervals)} "
        f"events={len(scanned)} separators={len(separators)} "
        f"eligible={len(eligible)} selected={len(selected)} "
        f"legs={len(changes)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
