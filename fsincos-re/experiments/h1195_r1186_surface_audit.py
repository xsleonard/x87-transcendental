#!/usr/bin/env python3
"""Audit terminal carry geometry in the R1186-corrected coordinate frame."""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path


CELL = ("theta", "ce", "s4", "side", "low3", "dist", "rsh", "b1", "b2")
ONE = 1 << 66


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def signed128(text: str) -> int:
    value = int(text, 16)
    return value - (1 << 128) if value >> 127 else value


def physical_deviation(row: dict[str, str]) -> tuple[int, int, int]:
    k = int(row["k"])
    mask = (1 << k) - 1
    borrow = int((int(row["S"], 16) & mask) < (int(row["B"], 16) & mask))
    carry = int(row["physical_label"])
    delta = borrow - 1 + carry
    if delta not in (-1, 0, 1):
        raise AssertionError(delta)
    return int(delta != 0), delta, borrow


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rows", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    groups = defaultdict(list)
    counts = Counter()
    targets = []
    with args.rows.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            counts["rows"] += 1
            counts[f"status.{row['physical_status']}"] += 1
            if row["physical_status"] != "constraining":
                continue
            deviation, delta, borrow = physical_deviation(row)
            theta = int(row["theta"])
            expected_sign = 1 if theta < 0 else -1
            counts[f"deviation.{deviation}"] += 1
            counts[f"delta.{delta}"] += 1
            counts[f"borrow.{borrow}"] += 1
            if deviation and delta != expected_sign:
                counts["unexpected_delta_orientation"] += 1
            key = tuple(int(row[field]) for field in CELL)
            groups[key].append((signed128(row["Mreg"]), deviation, row))
            if row["label"] == "POS":
                targets.append((row, deviation, delta, borrow))

    mixed = []
    nonmonotone = []
    for key, entries in sorted(groups.items()):
        fires = [entry for entry in entries if entry[1]]
        cleans = [entry for entry in entries if not entry[1]]
        if not fires or not cleans:
            continue
        theta = key[0]
        if theta >= 0:
            fire_edge = max(fires, key=lambda entry: entry[0])
            clean_edge = min(cleans, key=lambda entry: entry[0])
            separable = fire_edge[0] < clean_edge[0]
        else:
            clean_edge = max(cleans, key=lambda entry: entry[0])
            fire_edge = min(fires, key=lambda entry: entry[0])
            separable = clean_edge[0] < fire_edge[0]
        item = (key, len(entries), len(fires), len(cleans), separable,
                fire_edge, clean_edge)
        mixed.append(item)
        if not separable:
            nonmonotone.append(item)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"rows_sha256\t{digest(args.rows)}\n")
        target.write("\n[counts]\n")
        for name, value in sorted(counts.items()):
            target.write(f"{name}\t{value}\n")
        target.write(f"cells\t{len(groups)}\n")
        target.write(f"mixed_cells\t{len(mixed)}\n")
        target.write(f"nonmonotone_cells\t{len(nonmonotone)}\n")

        target.write("\n[nonmonotone]\n")
        target.write(
            "cell\trows\tfire\tclean\tfire_M\tfire_op\tclean_M\tclean_op\n")
        for key, rows, fires, cleans, _, fire_edge, clean_edge in nonmonotone:
            target.write(
                f"{'/'.join(map(str, key))}\t{rows}\t{fires}\t{cleans}\t"
                f"{fire_edge[0]}\t{fire_edge[2]['op']}\t"
                f"{clean_edge[0]}\t{clean_edge[2]['op']}\n")

        target.write("\n[remaining targets]\n")
        target.write(
            "mode\top\tbranch\ttheta\tcell\tMreg\tdeviation\tdelta\t"
            "borrow\tcarry\n")
        for row, deviation, delta, borrow in sorted(targets,
                                                    key=lambda item: item[0]["op"]):
            key = tuple(row[field] for field in CELL)
            target.write(
                f"{row['mode']}\t{row['op']}\t{row.get('branch', '')}\t"
                f"{row['theta']}\t{'/'.join(key)}\t{signed128(row['Mreg'])}\t"
                f"{deviation}\t{delta}\t{borrow}\t{row['physical_label']}\n")

    print(
        f"wrote {args.report} rows={counts['rows']} cells={len(groups)} "
        f"mixed={len(mixed)} nonmonotone={len(nonmonotone)} "
        f"targets={len(targets)}", flush=True)


if __name__ == "__main__":
    main()
