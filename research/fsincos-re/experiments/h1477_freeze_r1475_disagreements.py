#!/usr/bin/env python3
"""Freeze the disjoint H1476 challenge for the H1475 wire hypothesis.

The H1476 rows were selected without hardware labels to distinguish the
leading right-product XOR from every other H1475 logical hypothesis class.
This freezer checks repository-visible and caller-supplied private evidence,
then emits one immutable FCOS tuple per selected operand.  It does not execute
x87 and never records the private ledger's identity or contents.
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
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
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
    parser.add_argument("--bank", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--private-ledger-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise SystemExit(f"refusing to overwrite {args.output_dir}")
    if not args.private_ledger_dir.is_dir():
        raise SystemExit("private ledger directory is unavailable")

    report = json.loads(args.bank.read_text())
    source = report["selected"]
    if len(source) != 10:
        raise RuntimeError(f"expected 10 selected disagreements, got {len(source)}")
    if report["hypothesis_equivalence_classes_after_selection"] != 66:
        raise RuntimeError("H1476 hypothesis partition changed")
    operands = {str(row["operand"]).lower() for row in source}
    if len(operands) != len(source):
        raise RuntimeError("duplicate H1476 operand")

    excluded = {args.bank.resolve()}
    repo_hits = collisions(operands, args.repo_root, excluded)
    private_hits = collisions(operands, args.private_ledger_dir, set())
    if repo_hits or private_hits:
        raise RuntimeError(
            f"capture freshness failed: repo={len(repo_hits)} "
            f"private={len(private_hits)}"
        )

    rows = []
    for index, item in enumerate(source, 1):
        mode = str(item["mode"])
        if mode not in MODES:
            raise RuntimeError(f"unexpected capture mode {mode}")
        if item["incumbent"] == item["r1382"]:
            raise RuntimeError("selected row is not endpoint-visible")
        expected = item["incumbent"] if item["leading_merge"] else item["r1382"]
        if item["leading_candidate"] != expected:
            raise RuntimeError("H1475 endpoint no longer follows its wire")
        rows.append({
            "case_id": f"X{index:03d}",
            "capture_state": "FROZEN_UNOPENED",
            "instruction": "fcos",
            "mode": mode,
            "precision_control": "pc64",
            "operand": str(item["operand"]).replace(":", " "),
            "incumbent": item["incumbent"],
            "r1382": item["r1382"],
            "r1475": item["leading_candidate"],
            "r1475_merge": str(item["leading_merge"]),
            "iteration": str(item["iteration"]),
            "selection": "h1476_greedy_hypothesis_partition",
        })

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
# One observation per frozen H1477 FCOS tuple.  Do not rerun this campaign.
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
if [ "$(wc -l < inputs/fcos_rn.txt)" -ne 4 ] \\
    || [ "$(wc -l < inputs/fcos_rd.txt)" -ne 3 ] \\
    || [ "$(wc -l < inputs/fcos_ru.txt)" -ne 3 ]; then
    echo "frozen input count mismatch" >&2
    exit 2
fi

mkdir "$OUT"
uname -a > "$OUT/uname.txt"
grep -m1 -E 'vendor_id|model name|cpu family|model[[:space:]]|stepping|microcode' \\
    /proc/cpuinfo > "$OUT/cpu-summary.txt" || true
sha256sum "$BIN" inputs/fcos_*.txt > "$OUT/inputs.sha256"

"$BIN" rn pc64 cos --status < inputs/fcos_rn.txt > "$OUT/fcos_rn.txt"
"$BIN" rd pc64 cos --status < inputs/fcos_rd.txt > "$OUT/fcos_rd.txt"
"$BIN" ru pc64 cos --status < inputs/fcos_ru.txt > "$OUT/fcos_ru.txt"

sha256sum "$OUT"/fcos_*.txt > "$OUT/outputs.sha256"
echo "H1477_CAPTURE_COMPLETE tuples=10 repeats=0"
""")

    freeze = {
        "experiment": "h1477_freeze_r1475_disagreements",
        "capture_state": "FROZEN_UNOPENED",
        "unique_capture_tuples": len(rows),
        "instruction": "fcos",
        "precision_control": "pc64",
        "one_observation_maximum_per_tuple": True,
        "repository_collision_count": 0,
        "private_ledger_collision_count": 0,
        "private_ledger_files_examined": sum(
            path.is_file() for path in args.private_ledger_dir.rglob("*")
        ),
        "private_ledger_identity_published": False,
        "mode_counts": {
            mode: sum(row["mode"] == mode for row in rows) for mode in MODES
        },
        "r1475_merge_counts": {
            value: sum(row["r1475_merge"] == value for row in rows)
            for value in ("0", "1")
        },
        "h1475_logical_class_size": 2,
        "h1475_logical_class_note": (
            "the second syntax is XOR of both complemented inputs and is "
            "the same Boolean function"
        ),
        "hardware_execution": "none",
        "hardware_labels": "none",
        "paper_change": "none",
        "sha256": {
            "source_bank": digest(args.bank),
            "manifest": digest(manifest),
            "mode_inputs": {
                mode: digest(path) for mode, path in mode_inputs.items()
            },
            "runner": digest(runner),
        },
        "capture_rule": (
            "Open each tuple at most once on the established Skylake oracle; "
            "score against the frozen incumbent/R1382/R1475 endpoints; do "
            "not promote R1475 without exact survival and wider controls."
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
        "r1475_merge_counts": freeze["r1475_merge_counts"],
        "repository_collision_count": 0,
        "private_ledger_collision_count": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
