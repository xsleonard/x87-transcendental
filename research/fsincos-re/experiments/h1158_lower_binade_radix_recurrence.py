#!/usr/bin/env python3
"""Check a factored five-state radix recurrence on h1135 intervals.

The formula was synthesized from the phase cube, not from operand identities.
This first version reports its exact interval violations and the remaining
free intercept interval for theta=-2.  It is an analysis candidate until the
recurrence is complete and survives a disjoint frozen bank.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path


INF = 10**6


def phase(row: dict[str, str]) -> tuple[int, int, int]:
    return -int(row["ce"]) - 74, int(row["s4"]) - 66, int(row["rsh"]) - 63


def components(row: dict[str, str]):
    e, a, h = phase(row)
    theta = int(row["theta"])
    payload = int(row["low3"]) + 8 - int(row["dist"])
    b1, b2 = int(row["b1"]), int(row["b2"])
    slope = 2 + 3 * a + h * (1 - a)
    intercept0 = -1 - a - (1 - e) * (h + 2 * a)
    if theta == -2:
        tap1 = (
            2 * a * (1 - e * (1 - h))
            + (1 - e) * h * (1 - a)
        )
        tap2 = 0
        intercept = -1 - a + a * h * (3 - e)
    elif theta == -1:
        tap1 = 0
        tap2 = a * h * (2 - e)
        intercept = intercept0 + (1 - e) * (2 * a + h) + a * h
    elif theta == 0:
        tap1 = (1 - e) * h * (1 + a)
        tap2 = 0
        intercept = intercept0
    elif theta == 1:
        tap1 = 0
        tap2 = (1 - e) * (1 + a * (1 - h))
        intercept = intercept0 - tap2
    else:
        tap1 = a + (1 - e) * (1 - a) * (1 - h)
        tap2 = 0
        decrement = (
            2 * (1 - e) * (1 + a * (1 - h))
            + 3 * a * h + a * e * (1 - h)
        )
        intercept = intercept0 - decrement
    base = slope * payload + tap1 * b1 + tap2 * b2
    return (e, a, h), theta, base, intercept, slope, tap1, tap2


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("thresholds", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    rows = []
    with args.thresholds.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            low_value, high_value = int(row["F_low"]), int(row["F_high"])
            row["low"] = -INF if low_value <= -999 else low_value
            row["high"] = INF if high_value >= 999 else high_value
            rows.append(row)

    violations = []
    exact = Counter()
    for row in rows:
        key, theta, base, intercept, slope, tap1, tap2 = components(row)
        low, high = int(row["low"]), int(row["high"])
        value = base + intercept
        if low <= value <= high:
            exact[(theta, "inside")] += 1
        else:
            exact[(theta, "outside")] += 1
            violations.append((
                min(abs(value - low), abs(value - high)), key, theta,
                int(row["low3"]), int(row["b1"]), int(row["b2"]),
                value, low, high, slope, tap1, tap2, intercept,
            ))

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("w") as target:
        target.write(f"cells\t{len(rows)}\n")
        target.write(f"violations\t{len(violations)}\n")
        for key in sorted(exact):
            target.write(f"theta={key[0]} {key[1]}\t{exact[key]}\n")
        target.write("\n[violations]\n")
        target.write("distance\te\ta\th\ttheta\tlow3\tb1\tb2\tvalue\t"
                     "low\thigh\tslope\ttap1\ttap2\tintercept\n")
        for item in sorted(violations, reverse=True):
            distance, key, theta, low3, b1, b2, value, low, high, slope, tap1, tap2, intercept = item
            target.write(
                f"{distance}\t{key[0]}\t{key[1]}\t{key[2]}\t{theta}\t"
                f"{low3}\t{b1}\t{b2}\t{value}\t{low}\t{high}\t"
                f"{slope}\t{tap1}\t{tap2}\t{intercept}\n"
            )
    print(f"cells={len(rows)} violations={len(violations)} report={args.report}")


if __name__ == "__main__":
    main()
