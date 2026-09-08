#!/usr/bin/env python3
"""Describe natural-width operation boundaries for the eight R1186 misses.

This is a diagnostic over the cached h1176 feature rows.  It reconstructs the
fixed six-term cosine schedule and prints exact integer distances from every
native FMUL/FADD rounding boundary.  No hardware is executed and target
membership is used only to select rows for the report, never to define a
candidate predicate.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path

from h1184_upstream_halfway_audit import STAGES, schedule


ADD_STAGES = {
    "negative.add1", "negative.add2", "positive.add1", "positive.add2",
}
MISSES = {
    "3ffc ba100000056e0a67",
    "3ffc cca0000009242f0c",
    "3ffc d920000000749eaa",
    "3ffc f4100000059862dd",
    "3ffc fa50000007503a2f",
    "3ffc ffffc00024077827",
    "3ffc ffffc0006e4548d9",
    "3ffc fffff00047c167a3",
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def geometry(stage: str, operation: object) -> tuple[object, ...]:
    bits = 64 if stage in ADD_STAGES else 67
    magnitude = operation.magnitude
    shift = max(0, magnitude.bit_length() - bits)
    denominator = 1 << shift if shift else 1
    remainder = magnitude & (denominator - 1) if shift else 0
    retained = magnitude >> shift
    if stage in ADD_STAGES:
        delta = remainder - (denominator >> 1)
        nearest = "half"
    elif remainder <= denominator - remainder:
        delta = remainder
        nearest = "floor"
    else:
        delta = remainder - denominator
        nearest = "ceiling"
    return (
        stage, bits, shift, retained & 1, nearest, delta,
        f"{remainder:x}", f"{denominator:x}",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("features", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    rows = {}
    with args.features.open(newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            if row["op"] in MISSES:
                rows.setdefault(row["op"], row)
    missing = sorted(MISSES - set(rows))
    if missing:
        raise RuntimeError(f"missing feature rows: {missing}")

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"features_sha256\t{digest(args.features)}\n")
        target.write(f"operands\t{len(rows)}\n")
        target.write(
            "op\tstage\tbits\tshift\tretained_lsb\tnearest_boundary\t"
            "signed_distance\tremainder\tdenominator\n"
        )
        for operand in sorted(rows):
            operations = schedule(rows[operand])
            for stage in STAGES:
                target.write("\t".join(map(
                    str, (operand, *geometry(stage, operations[stage]))
                )) + "\n")

    print(f"wrote {args.report} operands={len(rows)}")


if __name__ == "__main__":
    main()
