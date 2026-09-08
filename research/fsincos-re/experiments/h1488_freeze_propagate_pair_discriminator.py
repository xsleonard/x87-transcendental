#!/usr/bin/env python3
"""Freeze a one-shot discriminator for H1487's two surviving functions.

The six operands come from H1485's pre-existing, hardware-unopened software
bank.  Two make the formally distinct layout pairs predict opposite endpoints;
four are balanced unanimous controls.  This freezer audits repository-visible
and caller-supplied private evidence, but does not execute x87 or reveal the
private ledger's identity or contents.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path


MODES = ("rn", "rd", "ru")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def collisions(operands: set[str], root: Path, excluded: set[Path]) -> set[str]:
    command = ["rg", "-l", "-i", "--fixed-strings"]
    for operand in sorted(operands):
        command.extend(("-e", operand))
    command.append(str(root))
    completed = subprocess.run(
        command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False)
    if completed.returncode not in (0, 1):
        raise RuntimeError(f"evidence search failed: {completed.stderr}")
    found = set()
    for name in completed.stdout.splitlines():
        path = Path(name)
        if path.resolve() in excluded:
            continue
        text = path.read_text(errors="ignore").lower()
        found.update(operand for operand in operands if operand in text)
    return found


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--h1485-bank", required=True, type=Path)
    parser.add_argument("--h1485-score", required=True, type=Path)
    parser.add_argument("--h1486", required=True, type=Path)
    parser.add_argument("--h1487", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--private-ledger-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise SystemExit(f"refusing to overwrite {args.output_dir}")
    if not args.private_ledger_dir.is_dir():
        raise SystemExit("private ledger directory is unavailable")

    bank = json.loads(args.h1485_bank.read_text())
    audit = json.loads(args.h1486.read_text())
    proof = json.loads(args.h1487.read_text())
    source = bank["all_endpoint_visible"]
    if len(source) != 6:
        raise RuntimeError(f"expected six H1485 rows, got {len(source)}")
    if proof["status"] != "TWO_FORMALLY_DISTINCT_SURVIVING_FUNCTIONS":
        raise RuntimeError("H1487 did not prove the two-function partition")
    predicted = {
        row["operand"].replace(":", " "): row
        for row in audit["unopened_predictions"]["h1485_rows"]
    }

    operands = {str(row["sig"]).lower() for row in source}
    if len(operands) != len(source) or set(predicted) != {
            str(row["operand"]).lower().replace(":", " ") for row in source}:
        raise RuntimeError("H1485/H1486 operand set changed")
    excluded = {
        args.h1485_bank.resolve(), args.h1485_score.resolve(),
        args.h1486.resolve(),
    }
    repo_hits = collisions(operands, args.repo_root, excluded)
    private_hits = collisions(operands, args.private_ledger_dir, set())
    if repo_hits or private_hits:
        raise RuntimeError(
            f"capture freshness failed: repo={len(repo_hits)} "
            f"private={len(private_hits)}")

    rows = []
    for index, item in enumerate(source, 1):
        operand = str(item["operand"]).lower().replace(":", " ")
        prediction = predicted[operand]
        pattern = prediction["candidate_pattern"]
        if pattern not in ("0000", "0011", "1100", "1111"):
            raise RuntimeError(f"unexpected two-function pattern {pattern}")
        pair_a = int(pattern[0])
        pair_b = int(pattern[2])
        if pattern[0] != pattern[1] or pattern[2] != pattern[3]:
            raise RuntimeError("H1487 within-pair equivalence did not replay")
        incumbent = str(item["incumbent"])
        no_merge = str(item["r1382"])
        rows.append({
            "case_id": f"Y{index:03d}",
            "capture_state": "FROZEN_UNOPENED",
            "instruction": "fcos",
            "mode": str(item["mode"]),
            "precision_control": "pc64",
            "operand": operand,
            "incumbent": incumbent,
            "r1382": no_merge,
            "pair_a": incumbent if pair_a else no_merge,
            "pair_b": incumbent if pair_b else no_merge,
            "pair_a_merge": str(pair_a),
            "pair_b_merge": str(pair_b),
            "role": "pair_discriminator" if pair_a != pair_b
                    else "unanimous_control",
            "source_iteration": str(item["iteration"]),
        })
    if sum(row["role"] == "pair_discriminator" for row in rows) != 2:
        raise RuntimeError("expected two H1487 pair discriminators")
    if sum(row["role"] == "unanimous_control" for row in rows) != 4:
        raise RuntimeError("expected four unanimous controls")
    for field in ("pair_a_merge", "pair_b_merge"):
        if sorted(row[field] for row in rows) != ["0", "0", "0", "1", "1", "1"]:
            raise RuntimeError(f"{field} is not balanced")

    args.output_dir.mkdir(parents=True)
    manifest = args.output_dir / "manifest.tsv"
    with manifest.open("x", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    input_dir = args.output_dir / "inputs"
    input_dir.mkdir()
    mode_inputs = {}
    for mode in MODES:
        path = input_dir / f"fcos_{mode}.txt"
        with path.open("x") as target:
            for row in rows:
                if row["mode"] == mode:
                    target.write(row["operand"] + "\n")
        mode_inputs[mode] = path

    runner = args.output_dir / "run_capture.sh"
    with runner.open("x") as target:
        target.write("""#!/bin/sh
# One observation per frozen H1488 FCOS tuple.  Do not rerun this campaign.
set -eu

if [ "$#" -ne 1 ]; then
    echo "usage: $0 /path/to/x87_capture_x86_64" >&2
    exit 2
fi
BIN=$1
OUT=hardware-output
if [ ! -x "$BIN" ]; then
    echo "capture binary is not executable: $BIN" >&2
    exit 2
fi
if [ -e "$OUT" ]; then
    echo "refusing to reuse existing $OUT" >&2
    exit 2
fi
if [ "$(wc -l < inputs/fcos_rn.txt)" -ne 1 ] \
    || [ "$(wc -l < inputs/fcos_rd.txt)" -ne 3 ] \
    || [ "$(wc -l < inputs/fcos_ru.txt)" -ne 2 ]; then
    echo "frozen input count mismatch" >&2
    exit 2
fi

mkdir "$OUT"
uname -a > "$OUT/uname.txt"
grep -m1 -E 'vendor_id|model name|cpu family|model[[:space:]]|stepping|microcode' \
    /proc/cpuinfo > "$OUT/cpu-summary.txt" || true
sha256sum "$BIN" inputs/fcos_*.txt > "$OUT/inputs.sha256"

"$BIN" rn pc64 cos --status < inputs/fcos_rn.txt > "$OUT/fcos_rn.txt"
"$BIN" rd pc64 cos --status < inputs/fcos_rd.txt > "$OUT/fcos_rd.txt"
"$BIN" ru pc64 cos --status < inputs/fcos_ru.txt > "$OUT/fcos_ru.txt"

sha256sum "$OUT"/fcos_*.txt > "$OUT/outputs.sha256"
echo "H1488_CAPTURE_COMPLETE tuples=6 repeats=0"
""")

    freeze = {
        "experiment": "h1488_freeze_propagate_pair_discriminator",
        "capture_state": "FROZEN_UNOPENED",
        "unique_capture_tuples": len(rows),
        "instruction": "fcos",
        "precision_control": "pc64",
        "one_observation_maximum_per_tuple": True,
        "repository_collision_count": 0,
        "private_ledger_collision_count": 0,
        "private_ledger_files_examined": sum(
            path.is_file() for path in args.private_ledger_dir.rglob("*")),
        "private_ledger_identity_published": False,
        "mode_counts": {
            mode: sum(row["mode"] == mode for row in rows) for mode in MODES},
        "role_counts": {
            role: sum(row["role"] == role for row in rows)
            for role in ("pair_discriminator", "unanimous_control")},
        "pair_merge_counts": {
            pair: {
                value: sum(row[f"{pair}_merge"] == value for row in rows)
                for value in ("0", "1")}
            for pair in ("pair_a", "pair_b")},
        "pair_definitions": {
            "pair_a": proof["candidate_signal_order"][:2],
            "pair_b": proof["candidate_signal_order"][2:],
        },
        "hardware_execution": "none",
        "hardware_labels": "none",
        "paper_change": "none",
        "sha256": {
            "h1485_bank": digest(args.h1485_bank),
            "h1485_score": digest(args.h1485_score),
            "h1486": digest(args.h1486),
            "h1487": digest(args.h1487),
            "manifest": digest(manifest),
            "mode_inputs": {
                mode: digest(path) for mode, path in mode_inputs.items()},
            "runner": digest(runner),
        },
        "capture_rule": (
            "Open each tuple at most once on the established Skylake oracle; "
            "use the two disagreement rows to distinguish the formally "
            "separate propagate functions and all six rows to test survival; "
            "do not promote either function from this bank alone."
        ),
    }
    freeze_path = args.output_dir / "FREEZE.json"
    with freeze_path.open("x") as target:
        json.dump(freeze, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps({
        "output_dir": str(args.output_dir),
        "capture_state": freeze["capture_state"],
        "unique_capture_tuples": len(rows),
        "mode_counts": freeze["mode_counts"],
        "role_counts": freeze["role_counts"],
        "pair_merge_counts": freeze["pair_merge_counts"],
        "repository_collision_count": 0,
        "private_ledger_collision_count": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
