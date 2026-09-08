#!/usr/bin/env python3
"""Score one-shot h1400 core captures without recapturing any operand.

The input directory must contain one output file per frozen input file, named
``<instruction>_<mode>.txt`` and preserving line order.  This program is
read-only with respect to captures: it refuses missing/extra rows and writes a
new score/report pair.  The central transfer verdict compares the selected
standalone cosine projection with the corresponding FSINCOS lane at the exact
same external operand and rounding mode.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def value_from_line(line: str, instruction: str, lane: str) -> str:
    fields = line.split()
    if not fields:
        raise ValueError("empty hardware output")
    if fields[0] == "C2":
        return "C2"
    if fields[0] != "OK":
        raise ValueError(f"bad hardware output: {line!r}")
    if instruction in ("fsin", "fcos"):
        if len(fields) < 3:
            raise ValueError(f"short standalone output: {line!r}")
        return f"{fields[1].lower()}:{fields[2].lower()}"
    if len(fields) < 5:
        raise ValueError(f"short FSINCOS output: {line!r}")
    offset = 1 if lane == "sin" else 3
    return f"{fields[offset].lower()}:{fields[offset + 1].lower()}"


def anchor_value(text: str) -> str:
    if not text:
        return ""
    if ":" in text and " " not in text:
        return text.lower()
    fields = text.split()
    if len(fields) != 3 or fields[0] != "OK":
        raise ValueError(f"bad anchor hardware field: {text!r}")
    return f"{fields[1].lower()}:{fields[2].lower()}"


def point_key(row: dict[str, str]) -> tuple[str, ...]:
    return (
        row["family"],
        row["law"],
        row["transfer_kind"],
        row["mode"],
        row["operand"],
        row["target_lane"],
        row["actual_residual_integer"],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("capture_directory", type=Path)
    parser.add_argument("output_prefix", type=Path)
    args = parser.parse_args()

    score_path = args.output_prefix.with_name(args.output_prefix.name + "_score.tsv")
    report_path = args.output_prefix.with_name(args.output_prefix.name + "_report.txt")
    for path in (score_path, report_path):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")

    with args.manifest.open(newline="") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    keys = [(row["instruction"], row["mode"], row["operand"]) for row in rows]
    if len(keys) != len(set(keys)):
        raise RuntimeError("manifest contains a duplicate capture key")

    capture_hashes = {}
    grouped_indexes: dict[tuple[str, str], list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        grouped_indexes[row["instruction"], row["mode"]].append(index)
    for (instruction, mode), indexes in sorted(grouped_indexes.items()):
        path = args.capture_directory / f"{instruction}_{mode}.txt"
        if not path.is_file():
            raise RuntimeError(f"missing hardware output {path}")
        lines = path.read_text().splitlines()
        if len(lines) != len(indexes):
            raise RuntimeError(
                f"{path}: {len(lines)} rows, expected exactly {len(indexes)}"
            )
        capture_hashes[path.name] = sha256(path)
        for index, line in zip(indexes, lines):
            row = rows[index]
            row["hardware_line"] = line
            row["hardware_target"] = value_from_line(
                line, instruction, row["target_lane"]
            )
            row["incumbent_verdict"] = (
                "EXACT" if row["hardware_target"] == row["model_incumbent"] else "MISS"
            )
            row["ablation_verdict"] = (
                ""
                if not row["model_ablation"]
                else "EXACT"
                if row["hardware_target"] == row["model_ablation"]
                else "MISS"
            )
            expected_anchor = anchor_value(row["anchor_hardware"])
            row["anchor_transfer_verdict"] = (
                ""
                if not expected_anchor
                or row["transfer_kind"] != "exact_internal_residual"
                or row["cosine_projection_sign"] != "1"
                else "EXACT"
                if row["hardware_target"] == expected_anchor
                else "MISS"
            )

    points: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        points[point_key(row)].append(row)
    for key, members in points.items():
        if len(members) != 2 or {row["instruction"] for row in members} == {"fsincos"}:
            raise RuntimeError(f"transfer point does not contain standalone+paired: {key}")
        paired = next(row for row in members if row["instruction"] == "fsincos")
        standalone = next(row for row in members if row["instruction"] != "fsincos")
        verdict = (
            "EXACT"
            if paired["hardware_target"] == standalone["hardware_target"]
            else "DIFF"
        )
        for row in members:
            row["paired_standalone_verdict"] = verdict

    score_path.parent.mkdir(parents=True, exist_ok=True)
    with score_path.open("x", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=tuple(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    counts = Counter()
    point_counts = Counter()
    for row in rows:
        counts[f"family.{row['family']}.incumbent.{row['incumbent_verdict']}"] += 1
        if row["ablation_verdict"]:
            counts[f"family.{row['family']}.ablation.{row['ablation_verdict']}"] += 1
        if row["anchor_transfer_verdict"]:
            counts[
                f"family.{row['family']}.anchor.{row['anchor_transfer_verdict']}"
            ] += 1
    for key, members in points.items():
        verdict = members[0]["paired_standalone_verdict"]
        point_counts[f"family.{key[0]}.paired_vs_standalone.{verdict}"] += 1

    with report_path.open("x") as target:
        target.write(f"manifest_sha256\t{sha256(args.manifest)}\n")
        target.write("capture_policy\tone_observation_per_fresh_tuple\n")
        target.write(f"capture_legs\t{len(rows)}\n")
        target.write(f"transfer_points\t{len(points)}\n")
        for name, digest in sorted(capture_hashes.items()):
            target.write(f"capture_sha256.{name}\t{digest}\n")
        target.write(f"score_sha256\t{sha256(score_path)}\n")
        target.write("\n[counts]\n")
        for name, count in sorted(counts.items()):
            target.write(f"{name}\t{count}\n")
        for name, count in sorted(point_counts.items()):
            target.write(f"{name}\t{count}\n")
    print(f"wrote {score_path} and {report_path}: {len(rows)} one-shot legs")


if __name__ == "__main__":
    main()
