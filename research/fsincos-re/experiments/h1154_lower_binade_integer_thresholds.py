#!/usr/bin/env python3
"""Reduce h1135 labels to exact integer-M threshold constraints.

This is a synthesis aid, not a candidate model.  For every occupied digit
cell it reports the complete interval of integer thresholds F for which

    theta >= 0: fire iff Mreg <  F * 2^66
    theta <  0: fire iff Mreg >= F * 2^66.

The report also records the old R59 u-floor value when that branch emitted
one, making it possible to distinguish a wrong coarse digit threshold from
the later block-start/return policy.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path


ONE = 1 << 66
CELL = ("theta", "ce", "s4", "side", "low3", "dist", "rsh", "b1", "b2")


def physical_label(row: dict[str, str]) -> int | None:
    theta = int(row["theta"])
    allowed = {int(value) for value in row["target_allowed"].split(",")}
    endpoints = {-1, 0} if theta >= 0 else {0, 1}
    physical = allowed & endpoints
    if len(physical) == 2:
        return None
    if len(physical) != 1:
        raise RuntimeError(f"bad endpoint set for {row['op']}: {physical}")
    return int(next(iter(physical)) != 0)


def floor_div(value: int) -> int:
    return value // ONE


def threshold_interval(rows: list[tuple[int, int]]) -> tuple[int, int]:
    """Return inclusive integer bounds, using +/-999 as open sentinels."""
    theta = rows[0][0]
    values = defaultdict(list)
    for _, label, mreg in rows:
        values[label].append(mreg)
    if theta >= 0:
        # fire: M < F*ONE; clean: M >= F*ONE.
        lower = floor_div(max(values[1])) + 1 if values[1] else -999
        upper = floor_div(min(values[0])) if values[0] else 999
    else:
        # clean: M < F*ONE; fire: M >= F*ONE.
        lower = floor_div(max(values[0])) + 1 if values[0] else -999
        upper = floor_div(min(values[1])) if values[1] else 999
    return lower, upper


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    groups = defaultdict(list)
    with args.features.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            label = physical_label(row)
            if label is None:
                continue
            key = tuple(int(row[field]) for field in CELL)
            groups[key].append((
                int(row["theta"]), label, int(row["mreg_signed"]),
                row.get("br_uu", ""), row.get("br_u0", ""),
                row.get("branch", ""),
            ))

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("w", newline="") as target:
        writer = csv.writer(target, delimiter="\t")
        writer.writerow((*CELL, "rows", "fire", "clean", "F_low", "F_high",
                         "old_u", "old_u0", "branches"))
        for key, rows in sorted(groups.items()):
            compact = [(theta, label, mreg) for theta, label, mreg, *_ in rows]
            low, high = threshold_interval(compact)
            labels = Counter(label for _, label, *_ in rows)
            old_u = sorted({int(u) for *_, u, _, _ in rows if u})
            old_u0 = sorted({int(u) for *_, u, _ in rows if u})
            branches = sorted({branch or "fallthrough" for *_, branch in rows})
            writer.writerow((*key, len(rows), labels[1], labels[0], low, high,
                             ",".join(map(str, old_u)),
                             ",".join(map(str, old_u0)),
                             ",".join(branches)))

    exact = sum(1 for rows in groups.values()
                if threshold_interval([(a, b, c) for a, b, c, *_ in rows])[0]
                == threshold_interval([(a, b, c) for a, b, c, *_ in rows])[1])
    print(f"cells={len(groups)} singleton_threshold={exact} report={args.report}")


if __name__ == "__main__":
    main()
