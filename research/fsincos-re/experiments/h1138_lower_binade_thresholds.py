#!/usr/bin/env python3
"""Test whether h1135's lower-binade response is an exact M threshold."""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path


CELL_FIELDS = (
    "theta", "ce", "s4", "side", "low3", "dist", "rsh", "b1", "b2"
)


def physical_state(row: dict[str, str]) -> str:
    theta = int(row["theta"])
    allowed = {int(value) for value in row["target_allowed"].split(",")}
    candidates = {-1, 0} if theta >= 0 else {0, 1}
    valid = allowed & candidates
    if not valid:
        raise RuntimeError(f"no physical endpoint for {row['op']}")
    if len(valid) == 2:
        return "neutral"
    return "fire" if next(iter(valid)) else "clean"


def threshold_errors(rows: list[dict[str, object]], low_fires: bool):
    """Return minimum errors and all exact-boundary extrema for coordinate x."""
    points = defaultdict(lambda: [0, 0])
    for row in rows:
        points[int(row["x"])][int(row["state"] == "fire")] += 1
    ordered = sorted(points.items())
    totals = [sum(counts[label] for _, counts in ordered) for label in (0, 1)]
    below = [0, 0]
    best = None
    best_index = None
    for index in range(len(ordered) + 1):
        if low_fires:
            errors = below[0] + totals[1] - below[1]
        else:
            errors = below[1] + totals[0] - below[0]
        candidate = (errors, index)
        if best is None or candidate < best:
            best = candidate
            best_index = index
        if index < len(ordered):
            below[0] += ordered[index][1][0]
            below[1] += ordered[index][1][1]
    assert best is not None and best_index is not None
    left = ordered[best_index - 1][0] if best_index else None
    right = ordered[best_index][0] if best_index < len(ordered) else None
    return best[0], left, right


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    with args.features.open(newline="") as source:
        source_rows = list(csv.DictReader(source, delimiter="\t"))
    rows = []
    states = Counter()
    for source in source_rows:
        state = physical_state(source)
        states[state] += 1
        if state == "neutral":
            continue
        row = dict(source)
        row["state"] = state
        row["x"] = int(source["mreg_signed"])
        rows.append(row)

    cells = defaultdict(list)
    for row in rows:
        cells[tuple(str(row[name]) for name in CELL_FIELDS)].append(row)
    errors = 0
    mixed = 0
    exact_mixed = 0
    pure = 0
    lines = []
    for key, group in sorted(cells.items()):
        labels = Counter(str(row["state"]) for row in group)
        if len(labels) == 1:
            pure += 1
        else:
            mixed += 1
        low_fires = int(key[0]) >= 0
        error, left, right = threshold_errors(group, low_fires)
        errors += error
        if len(labels) > 1 and error == 0:
            exact_mixed += 1
        lines.append((key, len(group), labels["fire"], labels["clean"],
                      error, left, right, int(low_fires)))

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("w") as target:
        target.write(f"source_rows\t{len(source_rows)}\n")
        target.write(f"constraining_rows\t{len(rows)}\n")
        target.write(f"states\t{dict(states)}\n")
        target.write(f"cells\t{len(cells)}\n")
        target.write(f"pure_cells\t{pure}\n")
        target.write(f"mixed_cells\t{mixed}\n")
        target.write(f"exact_mixed_cells\t{exact_mixed}\n")
        target.write(f"total_threshold_errors\t{errors}\n")
        target.write("\ncell\trows\tfire\tclean\terrors\tleft_mreg\t"
                     "right_mreg\tlow_fires\n")
        for key, count, fire, clean, error, left, right, low_fires in lines:
            target.write(
                "/".join(key)
                + f"\t{count}\t{fire}\t{clean}\t{error}\t"
                + ("" if left is None else str(left))
                + "\t"
                + ("" if right is None else str(right))
                + f"\t{low_fires}\n"
            )
    print(
        f"rows={len(source_rows)} constraining={len(rows)} states={dict(states)} "
        f"cells={len(cells)} pure={pure} mixed={mixed} "
        f"exact_mixed={exact_mixed} errors={errors}"
    )


if __name__ == "__main__":
    main()
