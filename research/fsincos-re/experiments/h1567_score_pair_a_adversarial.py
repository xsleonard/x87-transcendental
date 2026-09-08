#!/usr/bin/env python3
"""Score the frozen H1566 one-shot pair-A adversarial wall."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from h1474_score_r1382_lattice import parse_hardware_line


MODES = ("rn", "rd", "ru")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def classify(rows, observed):
    counts = Counter()
    scored = []
    for row, (value, status) in zip(rows, observed):
        incumbent = row["incumbent"].lower()
        no_merge = row["r1382"].lower()
        endpoint = (
            "incumbent" if value == incumbent
            else "r1382" if value == no_merge
            else "other"
        )
        record = dict(row)
        record.update({
            "hardware": value,
            "hardware_status": status,
            "endpoint": endpoint,
            "pair_a_verdict": "EXACT" if value == row["pair_a"].lower() else "MISS",
            "pair_b_verdict": "EXACT" if value == row["pair_b"].lower() else "MISS",
        })
        scored.append(record)
        counts[f"endpoint.{endpoint}"] += 1
        counts[f"pair_a.{record['pair_a_verdict']}"] += 1
        counts[f"pair_b.{record['pair_b_verdict']}"] += 1
        counts[f"role.{row['role']}.pair_a.{record['pair_a_verdict']}"] += 1
    return scored, counts


def selftest() -> None:
    rows = [
        {"incumbent": "i", "r1382": "n", "pair_a": "i", "pair_b": "n",
         "role": "pair_discriminator"},
        {"incumbent": "i", "r1382": "n", "pair_a": "n", "pair_b": "i",
         "role": "pair_discriminator"},
        {"incumbent": "i", "r1382": "n", "pair_a": "i", "pair_b": "i",
         "role": "unanimous_control"},
        {"incumbent": "i", "r1382": "n", "pair_a": "n", "pair_b": "n",
         "role": "unanimous_control"},
    ]
    _, counts = classify(rows, [("i", "s"), ("n", "s"), ("i", "s"), ("n", "s")])
    if counts["pair_a.EXACT"] != 4 or counts["pair_b.EXACT"] != 2:
        raise RuntimeError("H1567 scorer selftest failed")


def main() -> None:
    selftest()
    parser = argparse.ArgumentParser()
    parser.add_argument("freeze", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("input_directory", type=Path)
    parser.add_argument("capture_directory", type=Path)
    parser.add_argument("output_prefix", type=Path)
    args = parser.parse_args()
    score_path = args.output_prefix.with_name(args.output_prefix.name + "_score.tsv")
    report_path = args.output_prefix.with_name(args.output_prefix.name + "_report.txt")
    for path in (score_path, report_path):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")

    freeze = json.loads(args.freeze.read_text())
    if freeze.get("experiment") != "h1566_freeze_pair_a_adversarial" \
            or freeze.get("capture_state") != "FROZEN_UNOPENED":
        raise RuntimeError("unexpected H1566 freeze")
    if freeze.get("one_observation_maximum_per_tuple") is not True:
        raise RuntimeError("freeze does not enforce one observation maximum")
    with args.manifest.open(newline="") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    if len(rows) != 8 or len(rows) != freeze["unique_capture_tuples"]:
        raise RuntimeError("freeze/manifest row count differs")
    if digest(args.manifest) != freeze["sha256"]["manifest"]:
        raise RuntimeError("manifest hash differs from freeze")

    by_mode = defaultdict(list)
    for row in rows:
        if row["capture_state"] != "FROZEN_UNOPENED" \
                or row["instruction"] != "fcos" \
                or row["precision_control"] != "pc64":
            raise RuntimeError(f"{row['case_id']}: manifest invariant changed")
        by_mode[row["mode"]].append(row)
    ordered_observations = {}
    capture_hashes = {}
    for mode in MODES:
        input_path = args.input_directory / f"fcos_{mode}.txt"
        if digest(input_path) != freeze["sha256"]["mode_inputs"][mode]:
            raise RuntimeError(f"{input_path}: hash differs from freeze")
        actual = [line.strip().lower() for line in input_path.read_text().splitlines()]
        expected = [row["operand"].lower() for row in by_mode[mode]]
        if actual != expected:
            raise RuntimeError(f"{input_path}: positional order changed")
        capture_path = args.capture_directory / f"fcos_{mode}.txt"
        lines = capture_path.read_text().splitlines()
        if len(lines) != len(expected):
            raise RuntimeError(f"{capture_path}: capture row count changed")
        capture_hashes[capture_path.name] = digest(capture_path)
        for number, (row, line) in enumerate(zip(by_mode[mode], lines), 1):
            ordered_observations[row["case_id"]] = parse_hardware_line(
                line, capture_path, number)
    observed = [ordered_observations[row["case_id"]] for row in rows]
    scored, counts = classify(rows, observed)
    if counts["pair_a.EXACT"] == len(rows):
        verdict = "PAIR_A_SURVIVES_EIGHT_ROW_ADVERSARIAL_WALL"
    else:
        verdict = "PAIR_A_FALSIFIED_BY_EIGHT_ROW_ADVERSARIAL_WALL"

    score_path.parent.mkdir(parents=True, exist_ok=True)
    with score_path.open("x", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=tuple(scored[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(scored)
    with report_path.open("x") as target:
        target.write(f"freeze_sha256\t{digest(args.freeze)}\n")
        target.write(f"manifest_sha256\t{digest(args.manifest)}\n")
        target.write(f"score_sha256\t{digest(score_path)}\n")
        target.write("capture_policy\tone_observation_per_frozen_tuple\n")
        target.write(f"rows\t{len(rows)}\n")
        for name, value in sorted(capture_hashes.items()):
            target.write(f"capture_sha256.{name}\t{value}\n")
        target.write(f"challenge_verdict\t{verdict}\n")
        target.write("claim_boundary\tfresh_balanced_finite_wall_not_global_or_topology_proof\n")
        target.write("\n[counts]\n")
        for name, value in sorted(counts.items()):
            target.write(f"{name}\t{value}\n")
    print(
        f"wrote {score_path} and {report_path}: rows={len(rows)} "
        f"pair_a_exact={counts['pair_a.EXACT']} "
        f"pair_b_exact={counts['pair_b.EXACT']} "
        f"incumbent={counts['endpoint.incumbent']} "
        f"r1382={counts['endpoint.r1382']} other={counts['endpoint.other']} "
        f"verdict={verdict}", flush=True)


if __name__ == "__main__":
    main()
