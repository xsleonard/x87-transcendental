#!/usr/bin/env python3
"""Score the immutable H1472 one-shot R1382 lattice challenge.

The capture directory must be the untouched output of
``transfer-tests/h1472/run_capture.sh``.  Hardware rows are positional, so
this scorer first proves that the frozen per-mode input files still encode
the manifest rows in exactly the order in which the capture runner consumes
them.  It then classifies each result as the frozen incumbent endpoint, the
default-off R1382 endpoint, or neither.  It never executes x87 and refuses to
overwrite a prior score.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


MODES = ("rn", "rd", "ru")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_hardware_line(line: str, source: Path, line_number: int) -> tuple[str, str]:
    fields = line.lower().split()
    if len(fields) != 5 or fields[0] != "ok" or fields[3] != "sw":
        raise RuntimeError(
            f"{source}:{line_number}: expected 'OK <se> <sig> SW <status>', "
            f"got {line!r}"
        )
    try:
        se = int(fields[1], 16)
        sig = int(fields[2], 16)
        status = int(fields[4], 16)
    except ValueError as error:
        raise RuntimeError(
            f"{source}:{line_number}: non-hex hardware field"
        ) from error
    if se > 0xFFFF or sig > 0xFFFFFFFFFFFFFFFF or status > 0xFFFF:
        raise RuntimeError(f"{source}:{line_number}: hardware field out of range")
    return f"{se:04x}:{sig:016x}", f"{status:04x}"


def endpoint(observed: str, incumbent: str, candidate: str) -> str:
    incumbent = incumbent.lower()
    candidate = candidate.lower()
    if incumbent == candidate:
        raise RuntimeError("frozen row does not separate incumbent and candidate")
    if observed == incumbent:
        return "incumbent"
    if observed == candidate:
        return "r1382"
    return "other"


def load_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    if not rows:
        raise RuntimeError("empty manifest")
    required = {
        "case_id", "capture_state", "instruction", "mode",
        "precision_control", "operand", "incumbent", "candidate",
        "actual_merge_gate",
    }
    if not required.issubset(rows[0]):
        raise RuntimeError(
            f"manifest missing fields: {sorted(required - set(rows[0]))}"
        )
    keys = []
    for row in rows:
        if row["capture_state"] != "FROZEN_UNOPENED":
            raise RuntimeError(f"{row['case_id']}: unexpected capture state")
        if row["instruction"] != "fcos" or row["precision_control"] != "pc64":
            raise RuntimeError(f"{row['case_id']}: unexpected instruction/precision")
        if row["mode"] not in MODES:
            raise RuntimeError(f"{row['case_id']}: unexpected mode {row['mode']}")
        if row["actual_merge_gate"] != "1":
            raise RuntimeError(f"{row['case_id']}: exact-tree merge gate is not one")
        endpoint("", row["incumbent"], row["candidate"])
        keys.append((row["instruction"], row["mode"], row["operand"]))
    if len(keys) != len(set(keys)):
        raise RuntimeError("manifest contains duplicate capture tuples")
    return rows


def validate_freeze(
    freeze_path: Path, manifest_path: Path, input_dir: Path,
    rows: list[dict[str, str]],
) -> dict[str, object]:
    freeze = json.loads(freeze_path.read_text())
    if freeze.get("experiment") != "h1472_freeze_r1382_lattice":
        raise RuntimeError("unexpected freeze experiment")
    if freeze.get("capture_state") != "FROZEN_UNOPENED":
        raise RuntimeError("freeze was not unopened")
    if freeze.get("one_observation_maximum_per_tuple") is not True:
        raise RuntimeError("freeze does not require one observation per tuple")
    if freeze.get("unique_capture_tuples") != len(rows):
        raise RuntimeError("freeze/manifest tuple-count mismatch")
    expected_manifest = freeze["sha256"]["manifest"]
    if sha256(manifest_path) != expected_manifest:
        raise RuntimeError("manifest hash differs from freeze")

    rows_by_mode: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        rows_by_mode[row["mode"]].append(row)
    for mode in MODES:
        path = input_dir / f"fcos_{mode}.txt"
        expected_hash = freeze["sha256"]["mode_inputs"][mode]
        if sha256(path) != expected_hash:
            raise RuntimeError(f"{path}: hash differs from freeze")
        actual_operands = [
            line.strip().lower() for line in path.read_text().splitlines()
        ]
        expected_operands = [row["operand"].lower() for row in rows_by_mode[mode]]
        if actual_operands != expected_operands:
            raise RuntimeError(f"{path}: operand order differs from manifest")
    return freeze


def main() -> None:
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

    rows = load_manifest(args.manifest)
    freeze = validate_freeze(
        args.freeze, args.manifest, args.input_directory, rows
    )
    rows_by_mode: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        rows_by_mode[row["mode"]].append(row)

    capture_hashes = {}
    counts = Counter()
    for mode in MODES:
        path = args.capture_directory / f"fcos_{mode}.txt"
        if not path.is_file():
            raise RuntimeError(f"missing hardware output {path}")
        lines = path.read_text().splitlines()
        expected = rows_by_mode[mode]
        if len(lines) != len(expected):
            raise RuntimeError(
                f"{path}: {len(lines)} rows, expected exactly {len(expected)}"
            )
        capture_hashes[path.name] = sha256(path)
        for line_number, (row, line) in enumerate(zip(expected, lines), 1):
            observed, status = parse_hardware_line(line, path, line_number)
            verdict = endpoint(observed, row["incumbent"], row["candidate"])
            row["hardware"] = observed
            row["hardware_status"] = status
            row["hardware_pe"] = str(bool(int(status, 16) & 0x0020)).lower()
            row["hardware_c1"] = str(bool(int(status, 16) & 0x0200)).lower()
            row["endpoint"] = verdict
            counts[f"all.endpoint.{verdict}"] += 1
            counts[f"mode.{mode}.endpoint.{verdict}"] += 1

    if counts["all.endpoint.r1382"] == len(rows):
        challenge_verdict = "R1382_SURVIVES_ALL_FROZEN_SEPARATORS"
    else:
        challenge_verdict = "R1382_FALSIFIED_BY_FROZEN_SEPARATOR_BANK"

    score_path.parent.mkdir(parents=True, exist_ok=True)
    with score_path.open("x", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=tuple(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    with report_path.open("x") as target:
        target.write(f"freeze_sha256\t{sha256(args.freeze)}\n")
        target.write(f"manifest_sha256\t{sha256(args.manifest)}\n")
        target.write(f"score_sha256\t{sha256(score_path)}\n")
        target.write("capture_policy\tone_observation_per_frozen_tuple\n")
        target.write(f"frozen_capture_tuples\t{len(rows)}\n")
        target.write(
            f"freeze_private_collision_count\t"
            f"{freeze['private_ledger_collision_count']}\n"
        )
        for name, digest in sorted(capture_hashes.items()):
            target.write(f"capture_sha256.{name}\t{digest}\n")
        target.write(f"challenge_verdict\t{challenge_verdict}\n")
        target.write(
            "claim_boundary\tfrozen_endpoint_separators_only_not_global_"
            "selector_proof\n"
        )
        target.write("\n[counts]\n")
        for name, count in sorted(counts.items()):
            target.write(f"{name}\t{count}\n")

    print(
        f"wrote {score_path} and {report_path}: rows={len(rows)} "
        f"incumbent={counts['all.endpoint.incumbent']} "
        f"r1382={counts['all.endpoint.r1382']} "
        f"other={counts['all.endpoint.other']} "
        f"verdict={challenge_verdict}",
        flush=True,
    )


if __name__ == "__main__":
    main()
