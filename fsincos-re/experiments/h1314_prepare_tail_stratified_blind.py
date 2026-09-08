#!/usr/bin/env python3
"""Freeze the h1313 tail-stratified FCOS separators before capture."""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from pathlib import Path


CAPTURE_MODES = ("rn", "rd", "ru")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("capture_directory", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    changes_path = args.report.with_name(args.report.stem + "_changes.tsv")
    if args.capture_directory.exists():
        raise SystemExit(
            f"refusing to use existing capture directory "
            f"{args.capture_directory}")
    for output_path in (args.report, changes_path):
        if output_path.exists():
            raise SystemExit(f"refusing to overwrite {output_path}")

    with args.manifest.open(newline="") as source:
        source_rows = list(csv.DictReader(source, delimiter="\t"))
    if not source_rows:
        raise RuntimeError("empty h1313 manifest")

    metadata = (
        "q", "cut", "retained_lsb", "product_bit65", "r1237_fire",
        "word", "remainder", "tail_top4", "tail_top8",
        "tail_leading_zeros",
    )
    changes = []
    counts = Counter()
    for row in source_rows:
        changed_modes = tuple(row["changed_modes"].split(","))
        if not changed_modes or any(mode not in CAPTURE_MODES
                                    for mode in changed_modes):
            raise RuntimeError(
                f"bad changed_modes={row['changed_modes']!r} for {row['op']}")
        for mode in changed_modes:
            predecessor = row[f"{mode}_predecessor"].lower()
            wide = row[f"{mode}_wide"].lower()
            if predecessor == wide:
                raise RuntimeError(
                    f"non-separator listed for {mode}/{row['op']}")
            changes.append({
                "mode": mode,
                "op": row["op"].lower(),
                **{name: row[name] for name in metadata},
                "predecessor": predecessor,
                "wide": wide,
            })
            counts[f"mode.{mode}"] += 1
            counts[f"q.{row['q']}"] += 1
            counts[f"q.{row['q']}.cut.{row['cut']}"] += 1

    expected_operands = {row["op"].lower() for row in source_rows}
    selected_operands = {row["op"] for row in changes}
    if selected_operands != expected_operands:
        raise RuntimeError(
            f"not every h1313 separator is captured: "
            f"{expected_operands - selected_operands}")
    keys = [(row["mode"], row["op"]) for row in changes]
    if len(keys) != len(set(keys)):
        raise RuntimeError("duplicate capture pair")

    args.capture_directory.mkdir(parents=True)
    for mode in CAPTURE_MODES:
        operands = [row["op"] for row in changes if row["mode"] == mode]
        with (args.capture_directory / f"{mode}_inputs.txt").open("x") as target:
            for value in operands:
                target.write(value + "\n")

    columns = tuple(changes[0])
    with changes_path.open("x", newline="") as target:
        writer = csv.DictWriter(target, columns, delimiter="\t")
        writer.writeheader()
        writer.writerows(changes)

    with args.report.open("x") as target:
        target.write(f"manifest_sha256\t{digest(args.manifest)}\n")
        target.write("selection_policy\tone_per_occupied_q_cut_tail_top4_stratum\n")
        target.write("rz_policy\tomitted_positive_result_duplicate_of_rd\n")
        target.write("hardware_execution\tnone\n")
        target.write(f"source_operands\t{len(source_rows)}\n")
        target.write(f"capture_legs\t{len(changes)}\n")
        target.write(f"changes_sha256\t{digest(changes_path)}\n")
        for mode in CAPTURE_MODES:
            input_path = args.capture_directory / f"{mode}_inputs.txt"
            target.write(f"inputs_sha256.{mode}\t{digest(input_path)}\n")
        target.write("\n[counts]\n")
        for name, count in sorted(counts.items()):
            target.write(f"{name}\t{count}\n")

    print(
        f"wrote {args.report}: operands={len(source_rows)} "
        f"capture_legs={len(changes)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
