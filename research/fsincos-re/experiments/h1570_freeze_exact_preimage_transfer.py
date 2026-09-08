#!/usr/bin/env python3
"""Freeze fresh algebraic preimages for a residual-state transfer challenge.

This is not a new selector.  The frozen transfer prediction is the already
observed direct anchor's value, not a fitted feature formula.  Select low q
and high q for each eligible anchor, preferring an opposite mathematical
reducer carry64 for the high-q row when available.  Every selection is blind
to its own hardware label and conservatively rejects any previously seen
significand, even if a prior tuple used a different exponent or instruction.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from collections import Counter
from pathlib import Path

from h1566_freeze_pair_a_adversarial import digest


def collision_signatures(signatures: set[str], root: Path, excluded: set[Path]) -> set[str]:
    command = ["rg", "--hidden", "--no-ignore", "-l", "-i", "--fixed-strings",
               "--glob", "!**/.git/**"]
    for sig in sorted(signatures):
        command.extend(("-e", sig))
    command.append(str(root))
    proc = subprocess.run(command, text=True, capture_output=True)
    if proc.returncode not in (0, 1):
        raise RuntimeError("freshness search failed; no campaign frozen")
    hits = set()
    for name in proc.stdout.splitlines():
        path = Path(name)
        if path.resolve() in excluded:
            continue
        content = path.read_text(errors="ignore").lower()
        hits.update(sig for sig in signatures if sig in content)
    return hits


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--private-ledger-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise SystemExit(f"refusing to overwrite {args.output_dir}")
    if not args.private_ledger_dir.is_dir():
        raise RuntimeError("private freshness ledger unavailable")
    source = json.loads(args.source.read_text())
    assert source["experiment"] == "h1569_algebraic_preimage_families"
    assert source["capture_state"] == "SOFTWARE_ONLY_NOT_FROZEN"
    assert source["counts"]["candidate_trace_mismatches"] == 0
    assert source["counts"]["candidate_forced_endpoint_mismatches"] == 0
    candidates = [c for f in source["families"] for c in f["positive_same_residual_cosine_candidates"]]
    signatures = {c["operand"].split()[1] for c in candidates}
    public_hits = collision_signatures(signatures, args.repo_root, {args.source.resolve()})
    private_hits = collision_signatures(signatures, args.private_ledger_dir, set())
    rejected = public_hits | private_hits
    rows = []
    selection = []
    for family in source["families"]:
        choices = [c for c in family["positive_same_residual_cosine_candidates"]
                   if c["operand"].split()[1] not in rejected]
        if len(choices) < 2:
            continue
        choices.sort(key=lambda c: c["quotient"])
        low = choices[0]
        opposite = [c for c in choices[1:] if c["reduction_history"]["carry64"]
                    != low["reduction_history"]["carry64"]]
        high = (opposite or choices[1:])[-1]
        family_id = f"F{len(selection) + 1:02d}"
        selection.append({"family_id": family_id, "available_fresh_choices": len(choices),
                          "carry64_separated": bool(opposite),
                          "anchor": family["anchor"]})
        for role, candidate in (("low_q", low), ("high_q", high)):
            assert all(candidate["trace_and_endpoint_equal"].values())
            assert candidate["forced_endpoints_equal"]
            assert candidate["outputs"]["carry0"] != candidate["outputs"]["carry1"]
            rows.append({"case_id": f"T{len(rows) + 1:03d}", "family_id": family_id,
                         "capture_state": "FROZEN_UNOPENED", "role": role,
                         "instruction": candidate["instruction"], "mode": family["mode"],
                         "precision_control": "pc64", "operand": candidate["operand"],
                         "quotient": candidate["quotient"], "residual_side": 1,
                         "anchor": family["anchor"], "anchor_source": family["source"],
                         "anchor_case_id": family["case_id"],
                         "anchor_baseline_exact": int(family["baseline_anchor_exact"]),
                         "transfer_prediction": family["hardware_anchor"],
                         "baseline": candidate["outputs"]["baseline"],
                         "carry0": candidate["outputs"]["carry0"],
                         "carry1": candidate["outputs"]["carry1"],
                         "borrow_history": candidate["reduction_history"]["borrow_entering_columns_hex"],
                         "carry64": candidate["reduction_history"]["carry64"],
                         "full_trace_equal_all_modes": 1,
                         "direct_trace_sha256": family["direct_trace_sha256"][family["mode"]]})
    if not rows:
        raise RuntimeError("no fresh paired families remain")
    identities = {(r["instruction"], r["mode"], r["operand"]) for r in rows}
    assert len(identities) == len(rows)
    assert len({r["operand"] for r in rows}) == len(rows)
    assert len({r["operand"].split()[1] for r in rows}) == len(rows)
    args.output_dir.mkdir(parents=True)
    manifest = args.output_dir / "manifest.tsv"
    with manifest.open("x", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    inputs = args.output_dir / "inputs"
    inputs.mkdir()
    lanes = {}
    for instruction, mode in sorted({(r["instruction"], r["mode"]) for r in rows}):
        name = f"{instruction}_{mode}"
        selected = [r for r in rows if (r["instruction"], r["mode"]) == (instruction, mode)]
        path = inputs / f"{name}.txt"
        with path.open("x") as target:
            target.write("".join(r["operand"] + "\n" for r in selected))
        lanes[name] = {"instruction": instruction, "mode": mode,
                       "rows": len(selected), "sha256": digest(path)}
    runner = args.output_dir / "run_capture.sh"
    lines = ["#!/bin/sh", "# H1570: one observation per fresh tuple; never rerun, including partial runs.",
             "set -eu", '[ "$#" -eq 1 ] || exit 2', "BIN=$1",
             '[ -x "$BIN" ] || exit 2', '[ ! -e hardware-output ] || exit 2',
             "sha256sum -c CHECKSUMS.sha256",
             '[ "$(sha256sum "$BIN" | cut -d " " -f 1)" = "9eef49556c7da32c270b1f1c29f777bfffbba7eb85a68ddb512e8e7e1a192af1" ] || exit 2',
             "mkdir hardware-output", "uname -a > hardware-output/uname.txt",
             "awk '/vendor_id|model name|cpu family|^model[[:space:]]|stepping|microcode/ {print; n++; if(n==6)exit}' /proc/cpuinfo > hardware-output/cpu-summary.txt",
             'sha256sum "$BIN" > hardware-output/binary.sha256']
    for name, lane in lanes.items():
        lines.append(f'"$BIN" {lane["mode"]} pc64 {lane["instruction"][1:]} --status < inputs/{name}.txt > hardware-output/{name}.txt')
    lines.extend(["sha256sum hardware-output/f*.txt > hardware-output/outputs.sha256",
                  f'echo "H1570_CAPTURE_COMPLETE tuples={len(rows)} repeats=0"'])
    with runner.open("x") as target:
        target.write("\n".join(lines) + "\n")
    freeze = {"experiment": "h1570_exact_preimage_transfer", "capture_state": "FROZEN_UNOPENED",
              "unique_capture_tuples": len(rows), "anchor_families": len(selection),
              "one_observation_maximum_per_tuple": True, "hardware_execution": "none",
              "new_hardware_labels": "none", "paper_change": "none", "emulator_change": "none",
              "hypothesis": "same_exposed_residual_state_preserves_observed_direct_anchor_endpoint",
              "claim_boundary": "finite_transfer_discriminator_not_a_general_selector",
              "selection_rule": "minimum_fresh_q_then_maximum_fresh_q_with_opposite_carry64_if_available",
              "selection": selection, "lanes": lanes,
              "instruction_counts": dict(Counter(r["instruction"] for r in rows)),
              "anchor_baseline_exact_counts": dict(Counter(str(r["anchor_baseline_exact"]) for r in rows)),
              "freshness": {"selected_repository_collision_count": 0, "selected_private_collision_count": 0,
                            "rejected_candidate_significands": len(rejected),
                            "private_files_examined": sum(p.is_file() for p in args.private_ledger_dir.rglob("*")),
                            "private_identity_published": False},
              "sha256": {"source_report": digest(args.source), "manifest": digest(manifest),
                         "runner": digest(runner), "freezer": digest(Path(__file__))}}
    freeze_path = args.output_dir / "FREEZE.json"
    with freeze_path.open("x") as target:
        json.dump(freeze, target, indent=2, sort_keys=True)
        target.write("\n")
    checked = [manifest, runner, freeze_path, *sorted(inputs.iterdir())]
    with (args.output_dir / "CHECKSUMS.sha256").open("x") as target:
        target.write("".join(f"{digest(p)}  {p.relative_to(args.output_dir)}\n" for p in checked))
    print(json.dumps({"unique_capture_tuples": len(rows), "anchor_families": len(selection),
                      "freshness": freeze["freshness"], "instruction_counts": freeze["instruction_counts"],
                      "carry64_separated_families": sum(s["carry64_separated"] for s in selection),
                      "freeze_sha256": digest(freeze_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
