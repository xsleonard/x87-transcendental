#!/usr/bin/env python3
"""Render exact terminal-coordinate geometry for the six R1237 residuals.

This is a diagnostic, not a candidate selector.  Rows are grouped only by
the already-defined R59 digit cell, sorted by the signed R60 coordinate, and
compressed into physical-deviation runs.  Target ranks and their immediate
neighbors make scalar nonmonotonicity explicit before testing a different
arithmetic representation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import defaultdict
from pathlib import Path

from h1178_round_history_state_audit import CELL, signed128
from h1196_reframed_history_partition import physical_deviation


ONE = 1 << 66


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def floor_scaled(value: int, scale: int) -> int:
    return (scale * value) // ONE


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rows", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    groups: dict[tuple[int, ...], list[dict[str, str]]] = defaultdict(list)
    with args.rows.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            if row["physical_status"] != "constraining":
                continue
            groups[tuple(int(row[field]) for field in CELL)].append(row)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"rows_sha256\t{digest(args.rows)}\n")
        target.write(f"groups\t{len(groups)}\n")
        target.write(f"rows\t{sum(map(len, groups.values()))}\n")
        target.write("\n[group summaries]\n")
        target.write(
            "group\tcell\trows\ttargets\tdeviation_runs\t"
            "min_m128\tmax_m128\n")
        for number, (key, rows) in enumerate(sorted(groups.items()), 1):
            ordered = sorted(rows, key=lambda row: (
                signed128(row["Mreg"]), row["op"]))
            runs = []
            for row in ordered:
                label = physical_deviation(row)
                if not runs or runs[-1][0] != label:
                    runs.append([label, 1])
                else:
                    runs[-1][1] += 1
            values = [signed128(row["Mreg"]) for row in ordered]
            target.write(
                f"{number}\t"
                + ",".join(f"{name}={value}" for name, value in zip(CELL, key))
                + f"\t{len(rows)}\t"
                + ",".join(row["op"] for row in ordered
                           if row["label"] == "POS")
                + "\t" + ",".join(f"{label}:{count}" for label, count in runs)
                + f"\t{floor_scaled(min(values), 128)}"
                + f"\t{floor_scaled(max(values), 128)}\n")

        target.write("\n[target neighborhoods]\n")
        target.write(
            "group\trank\top\ttarget\tphysical_carry\tdeviation\t"
            "m_floor\tm16\tm128\tborrow\ts_low\tb_low\n")
        for number, (key, rows) in enumerate(sorted(groups.items()), 1):
            ordered = sorted(rows, key=lambda row: (
                signed128(row["Mreg"]), row["op"]))
            target_indices = [
                index for index, row in enumerate(ordered)
                if row["label"] == "POS"
            ]
            selected = set()
            for index in target_indices:
                selected.update(range(max(0, index - 3),
                                      min(len(ordered), index + 4)))
            for index in sorted(selected):
                row = ordered[index]
                value = signed128(row["Mreg"])
                cut = int(row["k"])
                mask = (1 << cut) - 1
                s_low = int(row["S"], 16) & mask
                b_low = int(row["B"], 16) & mask
                borrow = int(s_low < b_low)
                # The exact S + ~B + 1 carry is the complement of borrow.
                physical_carry = 1 - borrow
                target.write("\t".join(map(str, (
                    number, index, row["op"],
                    int(row["label"] == "POS"), physical_carry,
                    physical_deviation(row), value // ONE,
                    floor_scaled(value, 16), floor_scaled(value, 128),
                    borrow, f"{s_low:x}", f"{b_low:x}",
                ))) + "\n")

    print(
        f"wrote {args.report} groups={len(groups)} "
        f"rows={sum(map(len, groups.values()))}", flush=True)


if __name__ == "__main__":
    main()
