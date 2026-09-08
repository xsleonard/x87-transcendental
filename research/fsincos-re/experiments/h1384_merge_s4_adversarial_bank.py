#!/usr/bin/env python3
"""Freeze fresh adversaries for the R1270/R1272 s4 attachment.

The current R1270 datapath retains the killed low-block carry of a Booth
hard-3x multiple in the theta-zero/low3-three comparator state.  R1272 gates
that merge with a named upper level-2 carry.  The cached d800 repair has
fourth-product cut ``s4=67``; the later d0d0 counterexample has ``s4=66``.
The candidate tested here therefore attaches the merge only to ``s4=67``.

This generator scans deterministic neighborhoods around the surviving
ledger-free misses and the d800 repair without executing x87.  It keeps only
fresh exact-tie rows in the structural parent state, evaluates the current
and candidate C circuits in all nonredundant rounding modes, and freezes only
architectural separators.  Hardware labels are neither read nor used for
selection.  For positive FCOS results RZ is identical to RD, so RZ is not
captured as a duplicate physical experiment.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from h1210_stagea_residual_reframe import parse_dump, run
from h1241_r1237_adversarial_bank import stagea_members
from h1313_highq_tail_stratified_bank import merged_intervals
from h1351_power_mux_adversarial_bank import operands_in, prior_pairs


MODES = ("rn", "rd", "ru")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def anchor_values(
    paths: list[Path], explicit: list[str], strata: int
) -> list[int]:
    result = set()
    for path in paths:
        for operand in operands_in(path):
            sign_exponent, significand = operand.split()
            if sign_exponent == "3ffc":
                result.add(int(significand, 16))
    for operand in explicit:
        fields = operand.lower().replace(":", " ").split()
        if len(fields) == 1:
            result.add(int(fields[0], 16))
        elif len(fields) == 2 and fields[0] == "3ffc":
            result.add(int(fields[1], 16))
        else:
            raise RuntimeError(f"bad explicit anchor: {operand}")
    if strata:
        span = 1 << 63
        for index in range(strata):
            result.add((1 << 63) + ((2 * index + 1) * span) // (2 * strata))
    if not result:
        raise RuntimeError("no 3ffc anchors found")
    return sorted(result)


def nearest(value: int, anchors: list[int]) -> int:
    return min(anchors, key=lambda anchor: (abs(value - anchor), anchor))


def scan_interval(
    scanner: Path, interval: tuple[int, int], anchors: list[int]
) -> list[dict[str, object]]:
    first, last = interval
    process = subprocess.run(
        [str(scanner.resolve()), f"{first:016x}", str(last - first + 1)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    rows = []
    for line in process.stdout.splitlines():
        fields = line.split()
        if len(fields) != 11:
            raise RuntimeError(f"bad MERGE_STATE scanner row: {line}")
        (
            significand,
            distance,
            low3,
            k,
            rud,
            t4hi12,
            rdhi12,
            retained_correction,
            correction_exponent,
            theta,
            s4,
        ) = fields
        if theta != "0" or low3 != "3" or s4 not in ("66", "67"):
            continue
        value = int(significand, 16)
        anchor = nearest(value, anchors)
        rows.append(
            {
                "op": f"3ffc {significand.lower()}",
                "distance": int(distance),
                "low3": int(low3),
                "k": int(k),
                "rud": int(rud),
                "t4hi12": t4hi12.lower(),
                "rdhi12": rdhi12.lower(),
                "retained_correction": retained_correction.lower(),
                "ce": int(correction_exponent),
                "theta": int(theta),
                "s4": int(s4),
                "nearest_anchor": f"3ffc {anchor:016x}",
                "anchor_offset": value - anchor,
            }
        )
    return rows


def categories(row: dict[str, object]) -> set[str]:
    current_b2 = int(row["current_b2"])
    candidate_b2 = int(row["candidate_b2"])
    rsh = int(row["current_rsh"])
    s4 = int(row["s4"])
    distance = int(row["distance"])
    ce = int(row["ce"])
    side = int(row["current_side"])
    t4_top = str(row["t4hi12"])[0]
    rd_top = str(row["rdhi12"])[0]
    mreg_top = str(row["current_Mreg"])[-16:-15]
    mode_pattern = str(row["changed_modes"])
    return {
        f"attachment.s4.{s4}",
        f"normalization.s4.{s4}.rsh.{rsh}",
        f"terminal.s4.{s4}.dist.{distance}.ce.{ce}.side.{side}",
        f"response.b2.{current_b2}.to.{candidate_b2}",
        f"tail.t4top.{t4_top}.rdtop.{rd_top}",
        f"mreg.top.{mreg_top}",
        f"modes.{mode_pattern}",
        f"anchor.{str(row['nearest_anchor']).split()[1][:4]}",
    }


def select_cover(
    rows: list[dict[str, object]], maximum: int
) -> list[dict[str, object]]:
    for row in rows:
        row["categories"] = categories(row)
    uncovered = set().union(*(row["categories"] for row in rows))
    selected = []
    remaining = list(rows)
    while remaining and uncovered and len(selected) < maximum:
        remaining.sort(
            key=lambda row: (
                -len(row["categories"] & uncovered),
                abs(int(row["anchor_offset"])),
                str(row["op"]),
            )
        )
        chosen = remaining.pop(0)
        selected.append(chosen)
        uncovered.difference_update(chosen["categories"])

    # Set cover exercises state classes; add both geometric extremes so the
    # bank also challenges local interpolation around every populated anchor.
    selected_by_op = {str(row["op"]): row for row in selected}
    by_anchor: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        by_anchor.setdefault(str(row["nearest_anchor"]), []).append(row)
    for anchor_rows in by_anchor.values():
        ordered = sorted(anchor_rows, key=lambda row: int(row["anchor_offset"]))
        for row in (ordered[0], ordered[-1]):
            if len(selected_by_op) >= maximum:
                break
            selected_by_op.setdefault(str(row["op"]), row)
    return sorted(selected_by_op.values(), key=lambda row: str(row["op"]))


def rendered(row: dict[str, object]) -> dict[str, object]:
    result = dict(row)
    result["categories"] = ",".join(sorted(row["categories"]))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scanner", type=Path)
    parser.add_argument("current", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("output_prefix", type=Path)
    parser.add_argument("capture_directory", type=Path)
    parser.add_argument("--anchor-file", action="append", type=Path, default=[])
    parser.add_argument("--anchor", action="append", default=[])
    parser.add_argument("--strata", type=int, default=0)
    parser.add_argument("--label-bank", action="append", type=Path, default=[])
    parser.add_argument("--captured-dir", action="append", type=Path, default=[])
    parser.add_argument("--exclude", action="append", type=Path, default=[])
    parser.add_argument("--radius", type=int, default=50_000_000)
    parser.add_argument("--chunk-size", type=int, default=500_000_000)
    parser.add_argument("--max-operands", type=int, default=64)
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

    anchors = anchor_values(args.anchor_file, args.anchor, args.strata)
    intervals = merged_intervals(anchors, args.radius)
    chunks = []
    for first, last in intervals:
        chunk_first = first
        while chunk_first <= last:
            chunk_last = min(last, chunk_first + args.chunk_size - 1)
            chunks.append((chunk_first, chunk_last))
            chunk_first = chunk_last + 1
    with ThreadPoolExecutor(max_workers=min(4, len(chunks))) as executor:
        scanned_lists = list(
            executor.map(
                lambda interval: scan_interval(args.scanner, interval, anchors),
                chunks,
            )
        )
    scanned: dict[str, dict[str, object]] = {}
    for rows in scanned_lists:
        for row in rows:
            scanned[str(row["op"])] = row

    exclusion_sources = [
        *args.anchor_file,
        *args.label_bank,
        *args.captured_dir,
        *args.exclude,
    ]
    excluded_operands = set()
    for path in exclusion_sources:
        excluded_operands.update(operands_in(path))
    for value in anchors:
        excluded_operands.add(f"3ffc {value:016x}")
    candidate_operands = set(scanned)
    stagea = stagea_members(args.capture_root, candidate_operands)
    fresh_rows = [
        row
        for operand, row in scanned.items()
        if operand not in excluded_operands and operand not in stagea
    ]
    fresh_rows.sort(key=lambda row: str(row["op"]))
    if not fresh_rows:
        raise RuntimeError("no fresh structural events")

    operands = [str(row["op"]) for row in fresh_rows]
    outputs: dict[tuple[str, str], list[str]] = {}
    for mode in MODES:
        outputs[mode, "current"], _ = run(args.current, mode, operands)
        outputs[mode, "candidate"], _ = run(args.candidate, mode, operands)

    separators = []
    for index, source in enumerate(fresh_rows):
        changed_modes = [
            mode
            for mode in MODES
            if outputs[mode, "current"][index]
            != outputs[mode, "candidate"][index]
        ]
        if not changed_modes:
            continue
        row = dict(source)
        row["changed_modes"] = ",".join(changed_modes)
        for mode in MODES:
            row[f"{mode}_current"] = outputs[mode, "current"][index]
            row[f"{mode}_candidate"] = outputs[mode, "candidate"][index]
        separators.append(row)
    if not separators:
        raise RuntimeError("no architectural current/candidate separators")

    separator_operands = [str(row["op"]) for row in separators]
    _, current_stderr = run(args.current, "rn", separator_operands, dump=True)
    _, candidate_stderr = run(args.candidate, "rn", separator_operands, dump=True)
    current_dump = parse_dump(current_stderr, separator_operands)
    candidate_dump = parse_dump(candidate_stderr, separator_operands)
    fields = ("b1", "b2", "rsh", "side", "Mreg", "t4", "sqlow", "rd3")
    for row, current_row, candidate_row in zip(
        separators, current_dump, candidate_dump
    ):
        for field in fields:
            row[f"current_{field}"] = current_row[field]
            row[f"candidate_{field}"] = candidate_row[field]
        if int(current_row["s4"]) != int(row["s4"]):
            raise RuntimeError(f"scanner/model s4 disagreement at {row['op']}")

    known_pairs = prior_pairs(args.label_bank, args.captured_dir)
    eligible = []
    omitted_pairs = 0
    for row in separators:
        fresh_modes = [
            mode
            for mode in str(row["changed_modes"]).split(",")
            if (mode, str(row["op"])) not in known_pairs
        ]
        omitted_pairs += len(str(row["changed_modes"]).split(",")) - len(
            fresh_modes
        )
        if fresh_modes:
            row["changed_modes"] = ",".join(fresh_modes)
            eligible.append(row)
    if not eligible:
        raise RuntimeError("no uncaptured architectural separator pairs")

    selected = select_cover(eligible, args.max_operands)
    changes = []
    metadata = (
        "distance",
        "low3",
        "k",
        "rud",
        "t4hi12",
        "rdhi12",
        "retained_correction",
        "ce",
        "theta",
        "s4",
        "nearest_anchor",
        "anchor_offset",
        "current_b1",
        "current_b2",
        "candidate_b1",
        "candidate_b2",
        "current_rsh",
        "current_side",
        "current_Mreg",
        "current_t4",
        "current_sqlow",
        "current_rd3",
        "candidate_rd3",
        "categories",
    )
    for row in selected:
        for mode in str(row["changed_modes"]).split(","):
            changes.append(
                {
                    "mode": mode,
                    "op": row["op"],
                    **{name: row[name] for name in metadata},
                    "current": row[f"{mode}_current"],
                    "candidate": row[f"{mode}_candidate"],
                }
            )
    changes.sort(key=lambda row: (MODES.index(str(row["mode"])), row["op"]))
    keys = [(str(row["mode"]), str(row["op"])) for row in changes]
    if len(keys) != len(set(keys)):
        raise RuntimeError("duplicate frozen capture pair")
    if set(keys) & known_pairs:
        raise RuntimeError("a previously captured pair survived exclusion")

    manifest_columns = (
        "op",
        *metadata[:-1],
        "categories",
        "changed_modes",
        "rn_current",
        "rn_candidate",
        "rd_current",
        "rd_candidate",
        "ru_current",
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
        path = args.capture_directory / f"{mode}_inputs.txt"
        with path.open("x") as target:
            for row in changes:
                if row["mode"] == mode:
                    target.write(str(row["op"]) + "\n")

    counts = Counter()
    for row in scanned.values():
        counts[f"events.s4.{row['s4']}"] += 1
    for row in separators:
        counts[f"separators.s4.{row['s4']}.modes.{row['changed_modes']}"] += 1
    for row in selected:
        counts[f"selected.anchor.{str(row['nearest_anchor']).split()[1][:4]}"] += 1
        counts[f"selected.b2.{row['current_b2']}.to.{row['candidate_b2']}"] += 1
    for row in changes:
        counts[f"capture.mode.{row['mode']}"] += 1

    with report_path.open("x") as output:
        output.write(f"scanner_sha256\t{digest(args.scanner)}\n")
        output.write(f"current_sha256\t{digest(args.current)}\n")
        output.write(f"candidate_sha256\t{digest(args.candidate)}\n")
        output.write("candidate\tR1270/R1272 merge only when s4==67\n")
        output.write("selection_policy\tsoftware_only_structural_cover_plus_anchor_extremes\n")
        output.write("repeat_policy\tprior_operands_and_exact_mode_pairs_omitted\n")
        output.write("rz_policy\tpositive_fcos_rz_equals_rd_no_duplicate_capture\n")
        output.write("hardware_execution\tnone\n")
        output.write(f"radius\t{args.radius}\n")
        output.write(f"anchors\t{len(anchors)}\n")
        output.write(f"merged_intervals\t{len(intervals)}\n")
        output.write(f"scanner_chunks\t{len(chunks)}\n")
        output.write(
            "scanner_input_significands\t"
            f"{sum(last - first + 1 for first, last in intervals)}\n"
        )
        output.write(f"structural_events\t{len(scanned)}\n")
        output.write(f"explicit_excluded\t{len(candidate_operands & excluded_operands)}\n")
        output.write(f"stagea_excluded\t{len(stagea)}\n")
        output.write(f"fresh_structural_events\t{len(fresh_rows)}\n")
        output.write(f"architectural_separators\t{len(separators)}\n")
        output.write(f"known_capture_pairs\t{len(known_pairs)}\n")
        output.write(f"omitted_prior_separator_legs\t{omitted_pairs}\n")
        output.write(f"eligible_separator_operands\t{len(eligible)}\n")
        output.write(f"selected_operands\t{len(selected)}\n")
        output.write(f"frozen_capture_legs\t{len(changes)}\n")
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
