#!/usr/bin/env python3
"""Score the frozen H1477 one-shot right-product-wire challenge.

The scorer validates the freeze hashes and positional input order, classifies
each hardware value as incumbent, R1382, or other, and evaluates every H1475
hypothesis against the resulting merge/no-merge vector.  It is read-only with
respect to capture evidence and refuses to overwrite prior output.
"""

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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("freeze", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("input_directory", type=Path)
    parser.add_argument("capture_directory", type=Path)
    parser.add_argument("h1476_bank", type=Path)
    parser.add_argument("output_prefix", type=Path)
    args = parser.parse_args()
    score_path = args.output_prefix.with_name(args.output_prefix.name + "_score.tsv")
    report_path = args.output_prefix.with_name(args.output_prefix.name + "_report.txt")
    for path in (score_path, report_path):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")

    freeze = json.loads(args.freeze.read_text())
    if freeze.get("experiment") != "h1477_freeze_r1475_disagreements" \
            or freeze.get("capture_state") != "FROZEN_UNOPENED":
        raise RuntimeError("unexpected H1477 freeze")
    if freeze.get("one_observation_maximum_per_tuple") is not True:
        raise RuntimeError("freeze does not enforce one observation maximum")
    with args.manifest.open(newline="") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    if len(rows) != freeze["unique_capture_tuples"]:
        raise RuntimeError("freeze/manifest row count differs")
    if digest(args.manifest) != freeze["sha256"]["manifest"]:
        raise RuntimeError("manifest hash differs from freeze")

    bank = json.loads(args.h1476_bank.read_text())
    if digest(args.h1476_bank) != freeze["sha256"]["source_bank"]:
        raise RuntimeError("H1476 bank hash differs from freeze")
    selected_by_operand = {
        row["operand"].replace(":", " "): row for row in bank["selected"]
    }
    if len(selected_by_operand) != len(rows):
        raise RuntimeError("H1476 selected set differs from H1477")

    by_mode: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row["capture_state"] != "FROZEN_UNOPENED" \
                or row["instruction"] != "fcos" \
                or row["precision_control"] != "pc64":
            raise RuntimeError(f"{row['case_id']}: manifest invariant changed")
        by_mode[row["mode"]].append(row)
    for mode in MODES:
        input_path = args.input_directory / f"fcos_{mode}.txt"
        if digest(input_path) != freeze["sha256"]["mode_inputs"][mode]:
            raise RuntimeError(f"{input_path}: hash differs from freeze")
        actual = [line.strip().lower() for line in input_path.read_text().splitlines()]
        expected = [row["operand"].lower() for row in by_mode[mode]]
        if actual != expected:
            raise RuntimeError(f"{input_path}: positional order changed")

    capture_hashes = {}
    counts = Counter()
    hardware_merge_by_operand = {}
    for mode in MODES:
        path = args.capture_directory / f"fcos_{mode}.txt"
        if not path.is_file():
            raise RuntimeError(f"missing capture {path}")
        lines = path.read_text().splitlines()
        expected = by_mode[mode]
        if len(lines) != len(expected):
            raise RuntimeError(f"{path}: {len(lines)} rows != {len(expected)}")
        capture_hashes[path.name] = digest(path)
        for number, (row, line) in enumerate(zip(expected, lines), 1):
            observed, status = parse_hardware_line(line, path, number)
            incumbent = row["incumbent"].lower()
            r1382 = row["r1382"].lower()
            if incumbent == r1382:
                raise RuntimeError(f"{row['case_id']}: endpoints collapsed")
            if observed == incumbent:
                endpoint = "incumbent"
                merge = 1
            elif observed == r1382:
                endpoint = "r1382"
                merge = 0
            else:
                endpoint = "other"
                merge = None
            operand = row["operand"].lower()
            source = selected_by_operand[operand]
            if int(row["r1475_merge"]) != source["leading_merge"]:
                raise RuntimeError(f"{row['case_id']}: R1475 prediction changed")
            row["hardware"] = observed
            row["hardware_status"] = status
            row["endpoint"] = endpoint
            row["hardware_merge"] = "" if merge is None else str(merge)
            row["r1475_verdict"] = (
                "EXACT" if observed == row["r1475"].lower() else "MISS"
            )
            hardware_merge_by_operand[operand] = merge
            counts[f"endpoint.{endpoint}"] += 1
            counts[f"r1475.{row['r1475_verdict']}"] += 1
            counts[f"mode.{mode}.endpoint.{endpoint}"] += 1

    hypotheses = bank["selected"][0]["hypothesis_merge"]
    survivor_indexes = []
    if all(value is not None for value in hardware_merge_by_operand.values()):
        for hypothesis in range(len(hypotheses)):
            if all(
                source["hypothesis_merge"][hypothesis]
                == hardware_merge_by_operand[source["operand"].replace(":", " ")]
                for source in bank["selected"]
            ):
                survivor_indexes.append(hypothesis)

    score_path.parent.mkdir(parents=True, exist_ok=True)
    with score_path.open("x", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=tuple(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    if counts["r1475.EXACT"] == len(rows):
        verdict = "R1475_SURVIVES_FROZEN_DISAGREEMENT_BANK"
    else:
        verdict = "R1475_FALSIFIED_BY_FROZEN_DISAGREEMENT_BANK"
    with report_path.open("x") as target:
        target.write(f"freeze_sha256\t{digest(args.freeze)}\n")
        target.write(f"manifest_sha256\t{digest(args.manifest)}\n")
        target.write(f"h1476_bank_sha256\t{digest(args.h1476_bank)}\n")
        target.write(f"score_sha256\t{digest(score_path)}\n")
        target.write("capture_policy\tone_observation_per_frozen_tuple\n")
        target.write(f"rows\t{len(rows)}\n")
        for name, value in sorted(capture_hashes.items()):
            target.write(f"capture_sha256.{name}\t{value}\n")
        target.write(f"challenge_verdict\t{verdict}\n")
        target.write(f"surviving_h1475_syntaxes\t{len(survivor_indexes)}\n")
        target.write(
            "claim_boundary\tfresh_disagreement_bank_not_global_selector_proof\n"
        )
        target.write("\n[counts]\n")
        for name, value in sorted(counts.items()):
            target.write(f"{name}\t{value}\n")
        target.write("\n[surviving hypothesis indexes]\n")
        for index in survivor_indexes:
            target.write(f"{index}\n")
    print(
        f"wrote {score_path} and {report_path}: rows={len(rows)} "
        f"r1475_exact={counts['r1475.EXACT']} "
        f"incumbent={counts['endpoint.incumbent']} "
        f"r1382={counts['endpoint.r1382']} other={counts['endpoint.other']} "
        f"surviving_syntaxes={len(survivor_indexes)} verdict={verdict}",
        flush=True,
    )


if __name__ == "__main__":
    main()
