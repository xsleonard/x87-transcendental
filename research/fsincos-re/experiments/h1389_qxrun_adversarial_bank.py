#!/usr/bin/env python3
"""Freeze fresh endpoint-visible separators for the R1387 QX-run rule.

The scanner must be compiled from h491_scan3.c with QX_STATE=1 and a fixed
QX_MIN.  Selection reads only software model differences and cached operand
inventories; it neither executes x87 nor reads a new hardware label.
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


MODES = ("rn", "rd", "ru")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def parse_interval(text: str) -> tuple[int, int]:
    fields = text.split(":")
    if len(fields) != 2:
        raise argparse.ArgumentTypeError("interval must be START_HEX:COUNT")
    start = int(fields[0], 16)
    count = int(fields[1], 0)
    if count <= 0 or start < (1 << 63) or start + count > (1 << 64):
        raise argparse.ArgumentTypeError("interval leaves normalized binade")
    return start, count


def scan(scanner: Path, interval: tuple[int, int]) -> list[dict[str, str]]:
    start, count = interval
    process = subprocess.run(
        [str(scanner.resolve()), f"{start:016x}", str(count)],
        capture_output=True, text=True, check=True)
    result = []
    names = ("sig", "distance", "low3", "k", "rud", "t4hi12", "rdhi12",
             "retained", "ce", "theta", "s4", "tree_run")
    for line in process.stdout.splitlines():
        fields = line.split()
        if len(fields) != len(names):
            raise RuntimeError("bad QX_STATE scanner row: " + line)
        row = dict(zip(names, fields))
        row["op"] = "3ffc " + row["sig"].lower()
        row["interval_start"] = f"{start:016x}"
        row["interval_count"] = str(count)
        result.append(row)
    return result


def cached_pairs(paths: list[Path]) -> set[tuple[str, str]]:
    result = set()
    for path in paths:
        with path.open(newline="") as source:
            rows = csv.DictReader(source, delimiter="\t")
            if rows.fieldnames is None or "op" not in rows.fieldnames:
                continue
            for row in rows:
                mode = row.get("mode", "").lower()
                if mode in MODES:
                    result.add((mode, row["op"].lower()))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scanner", type=Path)
    parser.add_argument("current", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("output_prefix", type=Path)
    parser.add_argument("--interval", action="append", type=parse_interval,
                        required=True)
    parser.add_argument("--exclude", action="append", type=Path, default=[])
    parser.add_argument("--candidate-law",
                        default="corner_carry_xor_QX_run_ge_13")
    parser.add_argument("--run-name", default="qx_run")
    args = parser.parse_args()

    changes_path = args.output_prefix.with_name(args.output_prefix.name +
                                                "_changes.tsv")
    manifest_path = args.output_prefix.with_name(args.output_prefix.name +
                                                 "_manifest.tsv")
    report_path = args.output_prefix.with_name(args.output_prefix.name +
                                               "_report.txt")
    ops_paths = {mode: args.output_prefix.with_name(
        args.output_prefix.name + f"_{mode}_ops.txt") for mode in MODES}
    for path in (changes_path, manifest_path, report_path, *ops_paths.values()):
        if path.exists():
            raise SystemExit("refusing to overwrite " + str(path))

    scanned = {}
    with ThreadPoolExecutor(max_workers=min(4, len(args.interval))) as executor:
        scanned_intervals = list(executor.map(
            lambda interval: scan(args.scanner, interval), args.interval))
    interval_counts = []
    for rows in scanned_intervals:
        interval_counts.append(len(rows))
        for row in rows:
            row[args.run_name] = row.pop("tree_run")
            scanned[row["op"]] = row
    operands = sorted(scanned)
    if not operands:
        raise RuntimeError("scanner found no QX-run endpoint events")

    values = {}
    for mode in MODES:
        values[mode, "current"], _ = run(args.current, mode, operands)
        values[mode, "candidate"], _ = run(args.candidate, mode, operands)
    known = cached_pairs(args.exclude)
    changes = []
    for index, operand in enumerate(operands):
        for mode in MODES:
            current = values[mode, "current"][index]
            candidate = values[mode, "candidate"][index]
            if current == candidate:
                continue
            row = dict(scanned[operand])
            row.update({"mode": mode, "current": current,
                        "candidate": candidate,
                        "cached_pair": str(int((mode, operand) in known))})
            changes.append(row)
    fresh = [row for row in changes if row["cached_pair"] == "0"]
    if not fresh:
        raise RuntimeError("no fresh current/candidate separator pairs")

    unique_operands = sorted({row["op"] for row in fresh})
    _, stderr = run(args.current, "rn", unique_operands, dump=True)
    internals = {row["op"]: row for row in parse_dump(stderr, unique_operands)}
    for row in fresh:
        state = internals[row["op"]]
        row["branch"] = state.get("branch", "")
        row["side"] = state.get("side", "")
        row["rsh"] = state.get("rsh", "")
        row["b1"] = state.get("b1", "")
        row["b2"] = state.get("b2", "")
        if row["branch"] != "corner":
            raise RuntimeError("candidate changed outside corner: " + row["op"])

    fields = ("mode", "op", "current", "candidate", args.run_name, "theta",
              "low3", "distance", "k", "ce", "s4", "rsh", "side", "b1",
              "b2", "rud", "t4hi12", "rdhi12", "retained", "branch",
              "cached_pair", "interval_start", "interval_count")
    with changes_path.open("x", newline="") as target:
        writer = csv.DictWriter(target, fields, delimiter="\t",
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(changes)
    with manifest_path.open("x", newline="") as target:
        writer = csv.DictWriter(target, fields, delimiter="\t",
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(fresh)
    for mode, path in ops_paths.items():
        with path.open("x") as target:
            for operand in sorted({row["op"] for row in fresh
                                   if row["mode"] == mode}):
                target.write(operand + "\n")

    counts = Counter()
    counts["scanned_inputs"] = sum(count for _, count in args.interval)
    counts["scanner_events"] = len(scanned)
    counts["model_change_pairs"] = len(changes)
    counts["cached_change_pairs"] = len(changes) - len(fresh)
    counts["fresh_change_pairs"] = len(fresh)
    counts["fresh_operands"] = len({row["op"] for row in fresh})
    for row in fresh:
        counts["fresh_mode." + row["mode"]] += 1
        counts["fresh_" + args.run_name + "." + row[args.run_name]] += 1
        counts["fresh_theta." + row["theta"]] += 1
    with report_path.open("x") as target:
        target.write("selection_policy\tsoftware_only_no_x87_no_new_labels\n")
        target.write("candidate_law\t" + args.candidate_law + "\n")
        target.write("scanner_sha256\t" + digest(args.scanner) + "\n")
        target.write("current_sha256\t" + digest(args.current) + "\n")
        target.write("candidate_sha256\t" + digest(args.candidate) + "\n")
        for index, path in enumerate(args.exclude):
            target.write(f"exclude_sha256.{index}\t{digest(path)}\n")
        for index, ((start, count), events) in enumerate(
                zip(args.interval, interval_counts)):
            target.write(f"interval.{index}\t{start:016x}:{count}\t{events}\n")
        target.write("\n[counts]\n")
        for name, value in sorted(counts.items()):
            target.write(f"{name}\t{value}\n")
        target.write("\nmanifest_sha256\t" + digest(manifest_path) + "\n")
    print("scanned", counts["scanned_inputs"], "events", len(scanned),
          "changes", len(changes), "fresh", len(fresh))


if __name__ == "__main__":
    main()
