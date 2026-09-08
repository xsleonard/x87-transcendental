#!/usr/bin/env python3
"""Freeze one nonredundant hardware tuple per H1471 endpoint separator.

The H1471 report contains software-model disagreements only.  This freezer
checks that every selected operand is absent from repository-visible evidence
outside H1471 and from a caller-supplied private ledger directory.  Private
paths and contents are never written to the output.  It emits an immutable
FROZEN_UNOPENED manifest and performs no x87 execution.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def collisions(
    operands: set[str], root: Path, excluded: set[Path]
) -> set[str]:
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
    found: set[str] = set()
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
    candidates = [
        row for row in report["pre_candidate_bank"]["candidate_rows"]
        if row["endpoint_visible"]
    ]
    if len(candidates) != 16:
        raise RuntimeError(f"expected 16 endpoint separators, got {len(candidates)}")
    operand_sigs = {str(row["sig"]).lower() for row in candidates}
    if len(operand_sigs) != len(candidates):
        raise RuntimeError("duplicate endpoint-separator operand")

    repo_excluded = {args.bank.resolve()}
    repo_hits = collisions(operand_sigs, args.repo_root, repo_excluded)
    private_hits = collisions(operand_sigs, args.private_ledger_dir, set())
    if repo_hits or private_hits:
        raise RuntimeError(
            f"capture freshness failed: repo={len(repo_hits)} "
            f"private={len(private_hits)}"
        )

    rows = []
    for index, source in enumerate(candidates, 1):
        changed = list(source["changed_modes"])
        if changed == ["rd", "rz"]:
            mode = "rd"
            omitted = "rz=same_positive_result_as_rd"
        elif len(changed) == 1 and changed[0] in ("rn", "ru"):
            mode = changed[0]
            omitted = "none"
        else:
            raise RuntimeError(
                f"unexpected changed-mode set for {source['operand']}: {changed}"
            )
        rows.append({
            "case_id": f"L{index:03d}",
            "capture_state": "FROZEN_UNOPENED",
            "instruction": "fcos",
            "mode": mode,
            "precision_control": "pc64",
            "operand": str(source["operand"]).replace(":", " "),
            "incumbent": source["outputs"][mode]["incumbent"],
            "candidate": source["outputs"][mode]["candidate"],
            "other_changed_modes": ",".join(changed),
            "omitted_redundant_mode": omitted,
            "square_sig": source["square_sig"],
            "fourth_sig": source["fourth_sig"],
            "right_low72": source["right_low72"],
            "actual_merge_gate": source["actual_merge_gate"],
            "selection": "h1471_exact_lattice_then_current_source_replay",
        })

    args.output_dir.mkdir(parents=True)
    manifest = args.output_dir / "manifest.tsv"
    with manifest.open("x", newline="") as target:
        writer = csv.DictWriter(
            target, fieldnames=list(rows[0]), delimiter="\t"
        )
        writer.writeheader()
        writer.writerows(rows)
    inputs = args.output_dir / "fcos-inputs.tsv"
    with inputs.open("x") as target:
        for row in rows:
            target.write(f"{row['mode']}\t{row['operand']}\n")
    mode_input_dir = args.output_dir / "inputs"
    mode_input_dir.mkdir()
    mode_inputs = {}
    for mode in ("rn", "rd", "ru"):
        path = mode_input_dir / f"fcos_{mode}.txt"
        with path.open("x") as target:
            for row in rows:
                if row["mode"] == mode:
                    target.write(f"{row['operand']}\n")
        mode_inputs[mode] = path

    freeze = {
        "experiment": "h1472_freeze_r1382_lattice",
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
            mode: sum(row["mode"] == mode for row in rows)
            for mode in ("rn", "rd", "ru")
        },
        "hardware_execution": "none",
        "hardware_labels": "none",
        "paper_change": "none",
        "sha256": {
            "source_bank": digest(args.bank),
            "manifest": digest(manifest),
            "inputs": digest(inputs),
            "mode_inputs": {
                mode: digest(path) for mode, path in mode_inputs.items()
            },
        },
        "capture_rule": (
            "Open each listed tuple at most once on the established Skylake "
            "oracle; score against the frozen incumbent/candidate values; "
            "do not add results to the academic paper unless they establish "
            "a validated closed mechanism."
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
    }, sort_keys=True))


if __name__ == "__main__":
    main()
