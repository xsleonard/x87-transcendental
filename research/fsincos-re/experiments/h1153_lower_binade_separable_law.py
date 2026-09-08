#!/usr/bin/env python3
"""Test a separable outer-phase plus theta-tap threshold equation."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np


def state(row: dict[str, str]) -> int | None:
    theta = int(row["theta"])
    allowed = {int(value) for value in row["target_allowed"].split(",")}
    physical = allowed & ({-1, 0} if theta >= 0 else {0, 1})
    if len(physical) == 2:
        return None
    if not physical:
        raise RuntimeError(f"no physical endpoint for {row['op']}")
    return int(next(iter(physical)) != 0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--epochs", type=int, default=20000)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    source_rows = []
    with args.features.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            label = state(row)
            if label is not None:
                source_rows.append((row, label))
    outers = sorted({
        (row["ce"], row["s4"], row["side"], row["dist"], row["rsh"])
        for row, _ in source_rows
    })
    thetas = sorted({int(row["theta"]) for row, _ in source_rows})
    outer_id = {value: index for index, value in enumerate(outers)}
    theta_id = {value: index for index, value in enumerate(thetas)}
    width = 2 * len(outers) + 4 * len(thetas)
    constraints = []
    seen = set()
    for row, fire in source_rows:
        outer = (row["ce"], row["s4"], row["side"], row["dist"], row["rsh"])
        theta = int(row["theta"])
        q = int(row["mreg_signed"]) // (1 << 66)
        key = (outer, theta, int(row["payload"]), int(row["b1"]),
               int(row["b2"]), q, fire)
        if key in seen:
            continue
        seen.add(key)
        x = np.zeros(width, dtype=np.float64)
        oi = outer_id[outer]
        ti = theta_id[theta]
        x[oi] = int(row["payload"])
        x[len(outers) + oi] = 1
        base = 2 * len(outers)
        x[base + ti] = 1
        x[base + len(thetas) + ti] = int(row["b1"])
        x[base + 2 * len(thetas) + ti] = int(row["b2"])
        x[base + 3 * len(thetas) + ti] = int(row["payload"]) & 1
        high = fire if theta >= 0 else not fire
        if high:
            constraints.append((x, float(q + 1), key))
        else:
            constraints.append((-x, float(-q), key))

    weights = np.zeros(width, dtype=np.float64)
    for epoch in range(args.epochs):
        violations = 0
        largest = 0.0
        for x, bound, _ in constraints:
            shortfall = bound - float(x @ weights)
            if shortfall > 1e-10:
                weights += (shortfall / float(x @ x)) * x
                violations += 1
                largest = max(largest, shortfall)
        if violations == 0:
            break
    else:
        epoch = args.epochs

    remaining = []
    for x, bound, key in constraints:
        shortfall = bound - float(x @ weights)
        if shortfall > 1e-7:
            remaining.append((shortfall, key))
    remaining.sort(reverse=True)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("w") as target:
        target.write(f"source_rows\t{len(source_rows)}\n")
        target.write(f"constraints\t{len(constraints)}\n")
        target.write(f"epochs\t{epoch + 1}\n")
        target.write(f"remaining\t{len(remaining)}\n")
        target.write("\n[outer]\nouter\tpayload_coefficient\tintercept\n")
        for outer, index in outer_id.items():
            target.write(
                f"{'/'.join(outer)}\t{weights[index]:.12g}\t"
                f"{weights[len(outers) + index]:.12g}\n"
            )
        target.write("\n[theta]\ntheta\tintercept\tb1\tb2\tparity\n")
        base = 2 * len(outers)
        for theta, index in theta_id.items():
            target.write(
                f"{theta}\t{weights[base + index]:.12g}\t"
                f"{weights[base + len(thetas) + index]:.12g}\t"
                f"{weights[base + 2 * len(thetas) + index]:.12g}\t"
                f"{weights[base + 3 * len(thetas) + index]:.12g}\n"
            )
        target.write("\n[remaining]\n")
        for shortfall, key in remaining[:100]:
            target.write(f"{shortfall:.12g}\t{key}\n")
    print(
        f"rows={len(source_rows)} constraints={len(constraints)} "
        f"epochs={epoch + 1} remaining={len(remaining)}"
    )


if __name__ == "__main__":
    main()
