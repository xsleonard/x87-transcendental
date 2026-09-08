#!/usr/bin/env python3
"""Synthesize compact radix-floor formulas for h1135 threshold cells."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def state(row: dict[str, str]) -> int | None:
    theta = int(row["theta"])
    allowed = {int(value) for value in row["target_allowed"].split(",")}
    physical = allowed & ({-1, 0} if theta >= 0 else {0, 1})
    if len(physical) == 2:
        return None
    if not physical:
        raise RuntimeError(f"no physical endpoint for {row['op']}")
    return int(next(iter(physical)) != 0)


def cell_intervals(rows, low_fires: bool):
    cells = defaultdict(lambda: {0: [], 1: []})
    for row in rows:
        cells[(row["payload"], row["b1"], row["b2"])][row["label"]].append(
            row["q"]
        )
    result = []
    infinity = 10**9
    for key, labels in sorted(cells.items()):
        if low_fires:
            lower = max(labels[1]) + 1 if labels[1] else -infinity
            upper = min(labels[0]) if labels[0] else infinity
        else:
            lower = max(labels[0]) + 1 if labels[0] else -infinity
            upper = min(labels[1]) if labels[1] else infinity
        if lower > upper:
            raise RuntimeError(f"non-threshold cell {key}: {lower}>{upper}")
        result.append((key, lower, upper, len(labels[1]), len(labels[0])))
    return result


def formulas(cells, limit: int):
    found = []
    for denominator in (1, 2, 4, 8):
        for a_payload in range(0, 6 * denominator + 1):
            for c_b1 in range(-2 * denominator, 2 * denominator + 1):
                for d_b2 in range(-2 * denominator, 2 * denominator + 1):
                    for residue in range(denominator):
                        lower = -10**9
                        upper = 10**9
                        for (payload, b1, b2), lo, hi, _, _ in cells:
                            base = (
                                a_payload * payload + c_b1 * b1
                                + d_b2 * b2 + residue
                            ) // denominator
                            lower = max(lower, lo - base)
                            upper = min(upper, hi - base)
                            if lower > upper:
                                break
                        if lower <= upper:
                            intercept = 0 if lower <= 0 <= upper \
                                else lower if lower > 0 else upper
                            complexity = (
                                denominator + abs(a_payload) + abs(c_b1)
                                + abs(d_b2) + abs(intercept)
                            )
                            found.append((
                                complexity,
                                denominator,
                                a_payload,
                                c_b1,
                                d_b2,
                                residue,
                                intercept,
                                lower,
                                upper,
                            ))
    found.sort()
    return found[:limit]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--limit", type=int, default=12)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    groups = defaultdict(list)
    with args.features.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            label = state(row)
            if label is None:
                continue
            theta = int(row["theta"])
            outer = (row["ce"], row["s4"], row["side"], row["dist"], row["rsh"])
            groups[(outer, theta)].append({
                "payload": int(row["payload"]),
                "b1": int(row["b1"]),
                "b2": int(row["b2"]),
                "q": int(row["mreg_signed"]) // (1 << 66),
                "label": label,
            })

    args.report.parent.mkdir(parents=True, exist_ok=True)
    missing = []
    with args.report.open("w") as target:
        target.write(
            "outer\ttheta\tcells\tformula_rank\tcomplexity\tdenominator\t"
            "a_payload\tc_b1\td_b2\tresidue\tintercept\tF_low\tF_high\n"
        )
        for (outer, theta), rows in sorted(groups.items()):
            cells = cell_intervals(rows, theta >= 0)
            candidates = formulas(cells, args.limit)
            if not candidates:
                missing.append((outer, theta))
                continue
            for rank, candidate in enumerate(candidates, 1):
                target.write(
                    f"{'/'.join(outer)}\t{theta}\t{len(cells)}\t{rank}\t"
                    + "\t".join(str(value) for value in candidate)
                    + "\n"
                )
    print(f"groups={len(groups)} missing={len(missing)} report={args.report}")
    for outer, theta in missing:
        print(f"NO_FORMULA outer={'/'.join(outer)} theta={theta}")


if __name__ == "__main__":
    main()
