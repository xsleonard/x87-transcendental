#!/usr/bin/env python3
"""Search a table-free payload/M composite coordinate for h1135."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


CELL = ("theta", "ce", "s4", "side", "dist", "rsh", "b1", "b2")


def state(row: dict[str, str]) -> int | None:
    theta = int(row["theta"])
    allowed = {int(value) for value in row["target_allowed"].split(",")}
    physical = allowed & ({-1, 0} if theta >= 0 else {0, 1})
    if len(physical) == 2:
        return None
    if not physical:
        raise RuntimeError(f"no physical endpoint for {row['op']}")
    return int(next(iter(physical)) != 0)


def threshold_errors(points: list[tuple[int, int]], low_fires: bool) -> int:
    grouped = defaultdict(lambda: [0, 0])
    for coordinate, label in points:
        grouped[coordinate][label] += 1
    ordered = sorted(grouped.items())
    total_clean = sum(counts[0] for _, counts in ordered)
    total_fire = sum(counts[1] for _, counts in ordered)
    below_clean = below_fire = 0
    best = len(points)
    for _, counts in ordered:
        errors = (
            below_clean + total_fire - below_fire
            if low_fires
            else below_fire + total_clean - below_clean
        )
        best = min(best, errors)
        below_clean += counts[0]
        below_fire += counts[1]
    errors = (
        below_clean + total_fire - below_fire
        if low_fires
        else below_fire + total_clean - below_clean
    )
    return min(best, errors)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--maximum", type=int, default=512)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    rows = []
    with args.features.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            label = state(row)
            if label is None:
                continue
            rows.append({
                "cell": tuple(row[name] for name in CELL),
                "theta": int(row["theta"]),
                "low3": int(row["low3"]),
                "mreg": int(row["mreg_signed"]),
                "label": label,
            })
    unit = 1 << 66
    scores = []
    for numerator in range(args.maximum + 1):
        cells = defaultdict(list)
        for row in rows:
            coordinate = 128 * row["mreg"] - numerator * row["low3"] * unit
            cells[row["cell"]].append((coordinate, row["label"]))
        errors = sum(
            threshold_errors(group, int(cell[0]) >= 0)
            for cell, group in cells.items()
        )
        scores.append((errors, numerator))
    scores.sort()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("w") as target:
        target.write(f"constraining_rows\t{len(rows)}\n")
        target.write(f"cells\t{len({row['cell'] for row in rows})}\n")
        target.write("errors\tslope_numerator_over_128\n")
        for errors, numerator in scores[:64]:
            target.write(f"{errors}\t{numerator}\n")
    print(
        f"rows={len(rows)} cells={len({row['cell'] for row in rows})} "
        f"best_errors={scores[0][0]} slope={scores[0][1]}/128"
    )


if __name__ == "__main__":
    main()
