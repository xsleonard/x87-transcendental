#!/usr/bin/env python3
"""Aggregate h1173 fixed-feature counts across archived corpora."""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def read_report(path: Path):
    metadata = {}
    ranking = {}
    section = None
    with path.open() as source:
        for raw in source:
            line = raw.rstrip("\n")
            if line == "[ranking]":
                section = "ranking-header"
                continue
            if line.startswith("["):
                section = None
                continue
            if not line:
                continue
            if section == "ranking-header":
                expected = ("errors\trequired_miss\tforbidden_fire\t"
                            "required_hit\tneutral_fire\timpossible_fire\t"
                            "feature")
                if line != expected:
                    raise RuntimeError(f"unexpected ranking header in {path}")
                section = "ranking"
                continue
            if section == "ranking":
                fields = line.split("\t")
                if len(fields) != 7:
                    raise RuntimeError(f"malformed ranking row in {path}")
                ranking[fields[6]] = tuple(map(int, fields[:6]))
                continue
            if "\t" in line:
                key, value = line.split("\t", 1)
                metadata[key] = value
    return metadata, ranking


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("inputs", nargs="+", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit(f"refusing to overwrite {args.report}")

    aggregate = Counter()
    input_rows = []
    names = None
    total_rows = 0
    for path in args.inputs:
        metadata, ranking = read_report(path)
        if names is None:
            names = set(ranking)
        elif set(ranking) != names:
            raise RuntimeError(f"feature schema mismatch in {path}")
        total_rows += int(metadata["rows"])
        input_rows.append((path, metadata["rows"], digest(path)))
        for name, values in ranking.items():
            for index, value in enumerate(values):
                aggregate[name, index] += value
    if names is None:
        raise SystemExit("no reports")

    scores = []
    for name in names:
        values = tuple(aggregate[name, index] for index in range(6))
        if values[0] != values[1] + values[2]:
            raise AssertionError(f"error decomposition mismatch for {name}")
        scores.append(values + (name,))
    scores.sort(key=lambda row: (row[0], row[1], row[2], -row[3],
                                 row[4], row[5], row[6]))
    zero_collateral = [row for row in scores if row[2] == 0 and row[3] > 0]

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as target:
        target.write(f"corpora\t{len(args.inputs)}\n")
        target.write(f"rows\t{total_rows}\nfeatures\t{len(names)}\n")
        target.write(f"zero_collateral\t{len(zero_collateral)}\n")
        target.write("\n[inputs]\npath\trows\tsha256\n")
        for path, rows, sha256 in input_rows:
            target.write(f"{path}\t{rows}\t{sha256}\n")
        target.write("\n[ranking]\n")
        target.write("errors\trequired_miss\tforbidden_fire\trequired_hit\t"
                     "neutral_fire\timpossible_fire\tfeature\n")
        for score in scores:
            target.write("\t".join(map(str, score)) + "\n")
        target.write("\n[zero-collateral]\n")
        for score in zero_collateral:
            target.write("\t".join(map(str, score)) + "\n")
    print(
        f"wrote {args.report} rows={total_rows} features={len(names)} "
        f"best={scores[0]} zero_collateral={len(zero_collateral)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
