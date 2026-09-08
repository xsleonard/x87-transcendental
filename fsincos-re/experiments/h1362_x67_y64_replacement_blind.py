#!/usr/bin/env python3
"""Freeze fresh separators for the X67/Y64 odd-chain replacement.

The candidate is a fixed arithmetic program: build the odd/negative cosine
Horner chain from ``chop67(square * chop64(square))`` and remove the three
older endpoint gates R1237, R1263, and R1272.  Its exact score on the existing
direct-label population is discovery evidence, not validation.

This pass scans deterministic neighborhoods without executing x87, removes
every prior operand and every cached stage-A operand, and retains only
architectural baseline-versus-candidate separators.  Selection covers a
predeclared cross-section of the exact Horner-product tail, the square's
discarded three-bit Y-port field, the old R1237 response, and the observed
baseline-to-candidate factor displacement.  Hardware labels are not inputs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from h1210_stagea_residual_reframe import parse_dump, run
from h1241_r1237_adversarial_bank import stagea_members
from h1313_highq_tail_stratified_bank import MODES, merged_intervals, scan_interval
from h1351_power_mux_adversarial_bank import anchors, operands_in, prior_pairs


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def signed_sig_delta(candidate: dict[str, str], baseline: dict[str, str]) -> int:
    fields = ("tc_lf_sign", "tc_lf_exp")
    if any(candidate[field] != baseline[field] for field in fields):
        raise RuntimeError(
            f"factor sign/exponent changed for {baseline['op']}: "
            f"{baseline['tc_lf_sign']}:{baseline['tc_lf_exp']} -> "
            f"{candidate['tc_lf_sign']}:{candidate['tc_lf_exp']}"
        )
    sign = -1 if int(baseline["tc_lf_sign"]) else 1
    return sign * (
        int(candidate["tc_lf_sig"], 16) - int(baseline["tc_lf_sig"], 16)
    )


def categories(row: dict[str, object]) -> set[str]:
    q = int(row["q"])
    cut = int(row["cut"])
    top4 = int(row["tail_top4"])
    square_low3 = int(row["square_low3"])
    r1237 = int(row["r1237_fire"])
    factor_delta = int(row["factor_delta"])
    mode_pattern = str(row["changed_modes"])
    direction = str(row["candidate_direction"])
    return {
        f"tail.q{q}.cut{cut}.top4.{top4:x}",
        f"port.q{q}.cut{cut}.square_low3.{square_low3}",
        f"replacement.q{q}.cut{cut}.r1237.{r1237}.fd.{factor_delta:+d}",
        f"modes.{mode_pattern}",
        f"endpoint.q{q}.cut{cut}.{direction}",
        f"joint.q{q}.cut{cut}.s{square_low3}.r{r1237}.fd{factor_delta:+d}",
    }


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
    selected: list[dict[str, object]] = []
    remaining = list(rows)
    while remaining and uncovered and len(selected) < maximum:
        remaining.sort(
            key=lambda row: (
                -len(row["categories"] & uncovered),
                tail_center_distance(row),
                str(row["op"]),
            )
        )
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
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("output_prefix", type=Path)
    parser.add_argument("capture_directory", type=Path)
    parser.add_argument("--label-bank", action="append", type=Path, required=True)
    parser.add_argument("--captured-dir", action="append", type=Path, default=[])
    parser.add_argument("--exclude", action="append", type=Path, default=[])
    parser.add_argument("--radius", type=int, default=100_000_000)
    parser.add_argument("--max-operands", type=int, default=128)
    args = parser.parse_args()

    manifest_path = args.output_prefix.with_name(
        args.output_prefix.name + "_manifest.tsv"
    )
    changes_path = args.output_prefix.with_name(
        args.output_prefix.name + "_changes.tsv"
    )
    report_path = args.output_prefix.with_name(
        args.output_prefix.name + "_report.txt"
    )
    for path in (manifest_path, changes_path, report_path):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")
    if args.capture_directory.exists():
        raise SystemExit(f"refusing to use existing {args.capture_directory}")

    anchor_values = anchors(args.label_bank)
    intervals = merged_intervals(anchor_values, args.radius)
    with ThreadPoolExecutor(max_workers=min(4, len(intervals))) as executor:
        scanned_lists = list(
            executor.map(lambda interval: scan_interval(args.scanner, interval), intervals)
        )
    scanned: dict[str, dict[str, object]] = {}
    for rows in scanned_lists:
        for row in rows:
            scanned[str(row["op"])] = row

    excluded_operands: set[str] = set()
    for path in [*args.label_bank, *args.exclude, *args.captured_dir]:
        excluded_operands.update(operands_in(path))
    candidates = set(scanned)
    stagea = stagea_members(args.capture_root, candidates)
    fresh_rows = [
        row
        for operand, row in scanned.items()
        if operand not in excluded_operands and operand not in stagea
    ]
    fresh_rows.sort(key=lambda row: str(row["op"]))

    operands = [str(row["op"]) for row in fresh_rows]
    outputs: dict[tuple[str, str], list[str]] = {}
    for mode in MODES:
        outputs[mode, "baseline"], _ = run(args.baseline, mode, operands)
        outputs[mode, "candidate"], _ = run(args.candidate, mode, operands)

    separators: list[dict[str, object]] = []
    for index, source in enumerate(fresh_rows):
        changed_modes = [
            mode
            for mode in MODES
            if outputs[mode, "baseline"][index]
            != outputs[mode, "candidate"][index]
        ]
        if not changed_modes:
            continue
        row = dict(source)
        row["changed_modes"] = ",".join(changed_modes)
        for mode in MODES:
            row[f"{mode}_baseline"] = outputs[mode, "baseline"][index]
            row[f"{mode}_candidate"] = outputs[mode, "candidate"][index]
        first_mode = changed_modes[0]
        row["candidate_direction"] = (
            "up"
            if outputs[first_mode, "candidate"][index]
            > outputs[first_mode, "baseline"][index]
            else "down"
        )
        separators.append(row)

    separator_operands = [str(row["op"]) for row in separators]
    _, baseline_stderr = run(args.baseline, "rn", separator_operands, dump=True)
    _, candidate_stderr = run(args.candidate, "rn", separator_operands, dump=True)
    baseline_dump = parse_dump(baseline_stderr, separator_operands)
    candidate_dump = parse_dump(candidate_stderr, separator_operands)
    for row, baseline_row, candidate_row in zip(
        separators, baseline_dump, candidate_dump
    ):
        row["square_low3"] = int(baseline_row["tc_mul_sig"], 16) & 7
        row["fourth_low3"] = int(baseline_row["tc_f4_sig"], 16) & 7
        row["factor_delta"] = signed_sig_delta(candidate_row, baseline_row)

    known_pairs = prior_pairs(args.label_bank, args.captured_dir)
    eligible: list[dict[str, object]] = []
    omitted_pairs = 0
    for row in separators:
        modes = str(row["changed_modes"]).split(",")
        fresh_modes = [
            mode
            for mode in modes
            if (mode, str(row["op"])) not in known_pairs
        ]
        omitted_pairs += len(modes) - len(fresh_modes)
        if fresh_modes:
            row["changed_modes"] = ",".join(fresh_modes)
            eligible.append(row)
    if not eligible:
        raise RuntimeError("no uncaptured architectural separators")

    selected = select_cover(eligible, args.max_operands)
    metadata = (
        "q",
        "cut",
        "retained_lsb",
        "product_bit65",
        "r1237_fire",
        "word",
        "remainder",
        "tail_top4",
        "tail_top8",
        "tail_leading_zeros",
        "square_low3",
        "fourth_low3",
        "factor_delta",
        "candidate_direction",
        "categories",
    )
    changes: list[dict[str, object]] = []
    for row in selected:
        for mode in str(row["changed_modes"]).split(","):
            changes.append(
                {
                    "mode": mode,
                    "op": row["op"],
                    **{name: row[name] for name in metadata},
                    "baseline": row[f"{mode}_baseline"],
                    "candidate": row[f"{mode}_candidate"],
                }
            )
    changes.sort(key=lambda row: (MODES.index(str(row["mode"])), row["op"]))
    keys = [(str(row["mode"]), str(row["op"])) for row in changes]
    if len(keys) != len(set(keys)):
        raise RuntimeError("duplicate selected capture pair")
    if set(keys) & known_pairs:
        raise RuntimeError("a previously captured pair survived exclusion")

    manifest_columns = (
        "op",
        *metadata,
        "changed_modes",
        "rn_baseline",
        "rn_candidate",
        "rd_baseline",
        "rd_candidate",
        "ru_baseline",
        "ru_candidate",
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
        with (args.capture_directory / f"{mode}_inputs.txt").open("x") as target:
            for row in changes:
                if row["mode"] == mode:
                    target.write(str(row["op"]) + "\n")

    counts = Counter()
    for row in separators:
        counts[f"separator.q.{row['q']}.cut.{row['cut']}"] += 1
        counts[f"separator.factor_delta.{int(row['factor_delta']):+d}"] += 1
    for row in selected:
        counts[f"selected.q.{row['q']}.cut.{row['cut']}"] += 1
        counts[f"selected.square_low3.{row['square_low3']}"] += 1
        counts[f"selected.factor_delta.{int(row['factor_delta']):+d}"] += 1
    for row in changes:
        counts[f"capture.mode.{row['mode']}"] += 1

    available_categories = set().union(*(categories(row) for row in eligible))
    covered_categories = set().union(*(row["categories"] for row in selected))
    with report_path.open("x") as output:
        output.write(f"scanner_sha256\t{digest(args.scanner)}\n")
        output.write(f"baseline_sha256\t{digest(args.baseline)}\n")
        output.write(f"candidate_sha256\t{digest(args.candidate)}\n")
        for index, path in enumerate(args.label_bank):
            output.write(f"label_bank_sha256.{index}\t{digest(path)}\n")
        output.write("selection_policy\tgreedy_predeclared_recurrence_state_cover\n")
        output.write("repeat_policy\tprior_operands_and_exact_pairs_omitted\n")
        output.write("hardware_execution\tnone\n")
        output.write(f"radius\t{args.radius}\n")
        output.write(f"anchors\t{len(anchor_values)}\n")
        output.write(f"merged_intervals\t{len(intervals)}\n")
        output.write(
            "scanner_input_significands\t"
            f"{sum(last-first+1 for first, last in intervals)}\n"
        )
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
        output.write(f"covered_categories\t{len(covered_categories)}\n")
        output.write(f"available_categories\t{len(available_categories)}\n")
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
