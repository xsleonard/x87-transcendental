#!/usr/bin/env python3
"""Freeze H1496's balanced eight-row adversarial wall for pair A.

H1488 selected pair A over pair B on a six-row independent bank.  H1496 was
constructed earlier from a disjoint 30-million-plateau exact lattice search
and contains two rows from each pair-A/pair-B pattern.  This freezer verifies
that software-only source, rejects repository-visible or private-ledger
collisions, and emits an immutable one-shot FCOS/PC64 campaign.  It does not
execute x87 or reveal the private ledger's identity or contents.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path


MODES = ("rn", "rd", "ru")
PATTERNS = ("0000", "0011", "1100", "1111")


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
    parser.add_argument("--surface", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--private-ledger-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise SystemExit(f"refusing to overwrite {args.output_dir}")
    if not args.private_ledger_dir.is_dir():
        raise SystemExit("private ledger directory is unavailable")

    report = json.loads(args.surface.read_text())
    if report.get("experiment") != "h1496_boundary_carry_adversarial_surface" \
            or report.get("status") != "SOFTWARE_ONLY_BALANCED_ADVERSARIAL_SURFACE":
        raise RuntimeError("unexpected H1496 source report")
    source = report["selected"]
    if len(source) != 8:
        raise RuntimeError(f"expected eight H1496 rows, got {len(source)}")
    pattern_counts = Counter(str(row["candidate_pattern"]) for row in source)
    if pattern_counts != Counter({pattern: 2 for pattern in PATTERNS}):
        raise RuntimeError("H1496 pattern balance changed")
    if any(int(row["target_column"]) != 46 for row in source):
        raise RuntimeError("H1496 selected row escaped target column 46")
    signatures = {str(row["sig"]).lower() for row in source}
    if len(signatures) != len(source):
        raise RuntimeError("duplicate H1496 operand")

    repo_hits = collisions(signatures, args.repo_root, {args.surface.resolve()})
    private_hits = collisions(signatures, args.private_ledger_dir, set())
    if repo_hits or private_hits:
        raise RuntimeError(
            f"capture freshness failed: repo={len(repo_hits)} "
            f"private={len(private_hits)}")

    rows = []
    for index, item in enumerate(source, 1):
        mode = str(item["mode"])
        if mode not in MODES:
            raise RuntimeError(f"unexpected capture mode {mode}")
        pattern = str(item["candidate_pattern"])
        pair_a_merge = int(item["pair_a_merge"])
        pair_b_merge = int(item["pair_b_merge"])
        if pattern != f"{pair_a_merge}{pair_a_merge}{pair_b_merge}{pair_b_merge}":
            raise RuntimeError("pair pattern stopped matching exact pair partition")
        incumbent = str(item["incumbent"])
        no_merge = str(item["r1382"])
        if incumbent == no_merge:
            raise RuntimeError("selected row is not endpoint-visible")
        rows.append({
            "case_id": f"Z{index:03d}",
            "capture_state": "FROZEN_UNOPENED",
            "instruction": "fcos",
            "mode": mode,
            "precision_control": "pc64",
            "operand": str(item["operand"]).replace(":", " "),
            "incumbent": incumbent,
            "r1382": no_merge,
            "pair_a": incumbent if pair_a_merge else no_merge,
            "pair_b": incumbent if pair_b_merge else no_merge,
            "pair_a_merge": str(pair_a_merge),
            "pair_b_merge": str(pair_b_merge),
            "candidate_pattern": pattern,
            "role": "pair_discriminator" if pair_a_merge != pair_b_merge
                    else "unanimous_control",
            "target_column": str(item["target_column"]),
            "product_bit": str(item["product_bit"]),
            "pair_a_boundary_carry": str(item["pair_a_boundary_carry"]),
            "source_iteration": str(item["iteration"]),
        })
    if Counter(row["pair_a_merge"] for row in rows) != Counter({"0": 4, "1": 4}):
        raise RuntimeError("pair-A endpoint balance changed")

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
# One observation per frozen H1566 FCOS tuple.  Do not rerun this campaign.
set -eu

if [ "$#" -ne 1 ]; then
    echo "usage: $0 /path/to/x87_capture" >&2
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
    || [ "$(wc -l < inputs/fcos_ru.txt)" -ne 4 ]; then
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
echo "H1566_CAPTURE_COMPLETE tuples=8 repeats=0"
""")

    freeze = {
        "experiment": "h1566_freeze_pair_a_adversarial",
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
        "mode_counts": dict(sorted(Counter(row["mode"] for row in rows).items())),
        "pattern_counts": dict(sorted(Counter(
            row["candidate_pattern"] for row in rows).items())),
        "role_counts": dict(sorted(Counter(row["role"] for row in rows).items())),
        "pair_a_merge_counts": dict(sorted(Counter(
            row["pair_a_merge"] for row in rows).items())),
        "hardware_execution": "none",
        "hardware_labels": "none",
        "paper_change": "none",
        "sha256": {
            "h1496_surface": digest(args.surface),
            "manifest": digest(manifest),
            "mode_inputs": {
                mode: digest(path) for mode, path in mode_inputs.items()},
            "runner": digest(runner),
        },
        "capture_rule": (
            "Open each tuple at most once on the established Skylake oracle; "
            "score pair A on the balanced H1496 wall; do not promote it from "
            "this finite bank or claim a shared-tree topology."
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
        "pattern_counts": freeze["pattern_counts"],
        "role_counts": freeze["role_counts"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
