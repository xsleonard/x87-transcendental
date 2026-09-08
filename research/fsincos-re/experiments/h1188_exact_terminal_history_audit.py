#!/usr/bin/env python3
"""Test literal full-product history at the terminal cosine subtraction.

The materialized terminal subtracts two independently chopped 67-bit
products.  This audit instead keeps both exact product tails through their
sum, adds the low-three-bit payload at its fixed alignment, and performs one
67-bit chop.  That is a closed arithmetic representation, not a learned
selector.  It is scored against the immutable physical endpoint labels.
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


def full_terminal_delta(row: dict[str, str]) -> tuple[int, int, int, int]:
    left_base = int(row["tc_mul_exp"]) + int(row["tc_lf_exp"])
    right_base = int(row["tc_f4_exp"]) + int(row["tc_rf_exp"])
    payload_base = int(row["tc_left_exp"]) - 8
    payload = int(row["payload"])
    fine = min(left_base, right_base,
               payload_base if payload else left_base)

    left = (int(row["tc_mul_sig"], 16) * int(row["tc_lf_sig"], 16)
            << (left_base - fine))
    right = (int(row["tc_f4_sig"], 16) * int(row["tc_rf_sig"], 16)
             << (right_base - fine))
    total = -left + right
    if payload:
        payload_value = -payload if int(row["tc_left_sign"]) else payload
        total += payload_value << (payload_base - fine)
    sign = total < 0
    magnitude = abs(total)
    shift = max(0, magnitude.bit_length() - 67)
    significand = magnitude >> shift
    exponent = fine + shift

    retained_exponent = int(row["rscale"]) + int(row["k"])
    base_significand = int(row["umag"], 16) >> int(row["k"])
    common = min(exponent, retained_exponent)
    predicted = significand << (exponent - common)
    baseline = base_significand << (retained_exponent - common)
    unit = 1 << (retained_exponent - common)
    if sign != 1 or (predicted - baseline) % unit:
        return 99, exponent, significand, sign
    return ((predicted - baseline) // unit, exponent, significand, sign)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("physical_rows", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    rows = []
    with args.physical_rows.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            if row["physical_status"] == "constraining":
                rows.append(row)

    counts = Counter()
    target_diagnostics = []
    for row in rows:
        delta, exponent, significand, sign = full_terminal_delta(row)
        target = row["label"] == "POS"
        theta = int(row["theta"])
        predicted_label = int(delta != 0)
        expected_delta = (-int(row["physical_label"])
                          if theta >= 0 else int(row["physical_label"]))
        match = delta == expected_delta
        counts["rows"] += 1
        counts[f"target.{int(target)}"] += 1
        counts[f"match.{int(match)}"] += 1
        counts[f"target.{int(target)}.match.{int(match)}"] += 1
        counts[f"delta.{delta}"] += 1
        if target:
            target_diagnostics.append((
                row["op"], theta, int(row["physical_label"]),
                expected_delta, delta, predicted_label, int(match), sign,
                exponent, f"{significand:x}", row["branch"],
            ))

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"physical_rows_sha256\t{digest(args.physical_rows)}\n")
        target.write("\n[counts]\n")
        for name, value in sorted(counts.items()):
            target.write(f"{name}\t{value}\n")
        target.write("\n[target diagnostics]\n")
        target.write(
            "op\ttheta\tphysical_label\texpected_delta\tfull_delta\t"
            "predicted_label\tmatch\tsign\texponent\tsignificand\tbranch\n"
        )
        for entry in sorted(target_diagnostics):
            target.write("\t".join(map(str, entry)) + "\n")

    print(
        f"wrote {args.report} rows={counts['rows']} "
        f"target_miss={counts['target.1.match.0']} "
        f"control_miss={counts['target.0.match.0']}"
    )


if __name__ == "__main__":
    main()
