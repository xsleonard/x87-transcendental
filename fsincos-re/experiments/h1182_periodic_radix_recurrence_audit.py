#!/usr/bin/env python3
"""Transfer h1158's radix recurrence to upper binades by phase periodicity.

The h1158 recurrence was recovered on correction exponents -74 and -75 with
the binary phase ``e=-ce-74``.  In the upper R59 population the same physical
relations recur two exponents higher: ``side=1-e`` and the distance equation
remain exact if ``e`` is the correction-exponent phase modulo two.  This
script freezes that parameter-free interpretation and scores it against the
cached h1163 physical carry labels.

No coefficient is fitted here and no hardware instruction is executed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def recurrence(row: dict[str, str]) -> tuple[int, int, tuple[int, int, int]]:
    ce = int(row["ce"])
    a = int(row["s4"]) - 66
    h = int(row["rsh"]) - 63
    e = (-ce - 74) & 1
    if a not in (0, 1) or h not in (0, 1):
        raise ValueError("outside binary phase cube")
    expected_distance = -ce - int(row["s4"]) + 2 + (64 - int(row["rsh"]))
    if int(row["side"]) != 1 - e or int(row["dist"]) != expected_distance:
        raise ValueError("physical phase relation does not hold")

    theta = int(row["theta"])
    payload = int(row["low3"]) + 8 - int(row["dist"])
    b1, b2 = int(row["b1"]), int(row["b2"])
    slope = 2 + 3 * a + h * (1 - a)
    intercept0 = -1 - a - (1 - e) * (h + 2 * a)
    tap1 = 0
    tap2 = 0
    intercept = intercept0
    if theta == -2:
        tap1 = (2 * a * (1 - e * (1 - h))
                + (1 - e) * h * (1 - a))
        intercept = -1 - a + a * h * (3 - e)
    elif theta == -1:
        tap2 = a * h * (2 - e)
        intercept += (1 - e) * (2 * a + h) + a * h
    elif theta == 0:
        tap1 = (1 - e) * h * (1 + a)
    elif theta == 1:
        tap2 = (1 - e) * (1 + a * (1 - h))
        intercept -= tap2
    elif theta == 2:
        tap1 = a + (1 - e) * (1 - a) * (1 - h)
        intercept -= (2 * (1 - e) * (1 + a * (1 - h))
                      + 3 * a * h + a * e * (1 - h))
    else:
        raise ValueError("outside five-state theta band")

    threshold = slope * payload + tap1 * b1 + tap2 * b2 + intercept
    m_value = int(row["Mreg"], 16)
    if m_value >> 127:
        m_value -= 1 << 128
    boundary = threshold << 66
    fire = m_value < boundary if theta >= 0 else m_value >= boundary
    return int(fire), threshold, (e, a, h)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("physical_rows", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    counts = Counter()
    misses = []
    with args.physical_rows.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            if row["physical_status"] != "constraining":
                continue
            counts["rows"] += 1
            target = row["label"] == "POS"
            counts["targets" if target else "controls"] += 1
            try:
                predicted, threshold, phase = recurrence(row)
            except ValueError as error:
                counts["out_of_domain"] += 1
                misses.append((row["op"], "domain", str(error), "", "", ""))
                continue
            truth = int(row["physical_label"])
            counts[f"phase.{phase}"] += 1
            counts[f"truth.{truth}"] += 1
            counts[f"predicted.{predicted}"] += 1
            if predicted != truth:
                counts["misses"] += 1
                counts["target_misses" if target else "control_misses"] += 1
                misses.append((row["op"], "target" if target else "control",
                               str(phase), row["theta"], str(threshold),
                               row["physical_label"]))

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"physical_rows_sha256\t{digest(args.physical_rows)}\n")
        target.write("\n[counts]\n")
        for key, value in sorted(counts.items()):
            target.write(f"{key}\t{value}\n")
        target.write("\n[misses]\n")
        target.write("op\tkind\tphase\ttheta\tthreshold\tphysical_label\n")
        for miss in misses:
            target.write("\t".join(miss) + "\n")

    print(
        f"rows={counts['rows']} misses={counts['misses']} "
        f"target_misses={counts['target_misses']} "
        f"control_misses={counts['control_misses']} "
        f"out_of_domain={counts['out_of_domain']} report={args.report}")


if __name__ == "__main__":
    main()
