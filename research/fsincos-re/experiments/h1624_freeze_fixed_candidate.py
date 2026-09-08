#!/usr/bin/env python3
"""Freeze every fresh H1623 proposal against the unchanged H1618 graph.

Recheck the public and private history, including compressed public text,
immediately before freeze. Private identities/content/hashes remain local.
The existing numerical candidate is independently evaluated again, and all
four isolated C builds are checked before any hardware observation.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import h1618_isolated_cosine_transfer as candidate
from h1622_fixed_candidate_challenge_bank_v2 import digest
from h1623_fixed_candidate_freshness import BANK, BANK_SHA, SOFTWARE_DIRECTORIES, matches


AUDIT = "tmp/ledger33/current/h1623_fixed_candidate_freshness/report.json"
AUDIT_SHA = "aa0bcd9eb017665859cd401d15115a5dcbf6fe58d4bf1de257cf5478ab9ab46b"
MODELS = "tmp/ledger33/current/h1618_isolated_cosine_transfer"
MODEL_SHA = "b184f29cb7534c6e667f1780b6fdca6a7bb0e52d368e5891700391ff54910112"
CAPTURE_SHA = "9eef49556c7da32c270b1f1c29f777bfffbba7eb85a68ddb512e8e7e1a192af1"


def boundary_edge(row: dict) -> str:
    denominator = 1 << int(row["final_shift"])
    values = (0, 1, denominator // 2 - 1, denominator // 2,
              denominator // 2 + 1, denominator - 1)
    remainder = int(row["final_remainder"])
    return str(values.index(remainder)) if remainder in values else "other"


def write_json(path: Path, value: dict) -> None:
    with path.open("x") as target:
        json.dump(value, target, indent=2, sort_keys=True)
        target.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--private-ledger-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    root, private, output = args.root.resolve(), args.private_ledger_dir.resolve(), args.output_dir.resolve()
    assert private.is_dir() and not output.exists()
    locks = {BANK: BANK_SHA, AUDIT: AUDIT_SHA, MODELS + "/report.json": MODEL_SHA,
             "capture-kit/x87_capture.c": "aededbaea438dbd1526aca4926530b655d6c9a1ad0f0bac82ad58fcbe3d824d1",
             "experiments/h1623_fixed_candidate_freshness.py": "392554c2a402eb8b2411f851b6028326d363f21087b7f3b0d0d4791eceb87656"}
    for name, expected in locks.items():
        assert digest(root / name) == expected, name
    bank, audit, models = (json.loads((root / name).read_text()) for name in (BANK, AUDIT, MODELS + "/report.json"))
    assert audit["state"] == "AUDITED_PROPOSALS_NOT_FROZEN"
    assert bank["capture_state"] == "SOFTWARE_ONLY_NOT_FROZEN" and bank["candidate_changed"] is False
    for name, expected in bank["sha256"]["evidence"].items():
        assert digest(root / name) == expected, name
        locks[name] = expected
    for name, expected in candidate.LOCKS.items():
        assert digest(root / name) == expected, name
        locks[name] = expected
    locks["experiments/h1625_score_fixed_candidate.py"] = digest(root / "experiments/h1625_score_fixed_candidate.py")
    chosen = sorted(audit["eligible"], key=lambda row: row["operand"])
    assert len(chosen) == 417 and Counter(row["kind"] for row in chosen) == {
        "separator": 2, "rounding_boundary_control": 384, "uniform_control": 31}
    events = {row["operand"]: row for row in bank["events"]}
    assert all(events[row["operand"]] == row and row["independently_verified"] for row in chosen)
    operands = [row["operand"] for row in chosen]
    assert len(set(operands)) == len(operands)
    for build in ("baseline_O2", "candidate_O0", "candidate_O2", "candidate_O3", "candidate_ubsan"):
        binary = root / MODELS / build
        assert digest(binary) == models["builds"][build]["binary_sha256"]
        for mode in candidate.spec.MODES:
            values, _, _ = candidate.run_batch(binary, "fcos", mode, operands)
            key = ("baseline_" if build.startswith("baseline") else "candidate_") + mode
            assert values == [row[key] for row in chosen]
    for row in chosen:
        stages = candidate.reference.simplified_graph(row["operand"])
        pre = candidate.spec.exact_add(candidate.V(1, 0), stages["correction"])
        assert pre.fraction() == candidate.V(int(row["pre_significand"], 16), int(row["pre_scale"])).fraction()
        for index, mode in enumerate(candidate.spec.MODES):
            value, c1, _ = candidate.independent_signed_output(stages["correction"], False, mode)
            assert value == row["candidate_" + mode] and str(c1) == row["C1_bits"][index]
    print("All 1668 predictions and C1 checks replayed; beginning final local freshness audit.", flush=True)
    output.mkdir(parents=True)
    patterns = output / "candidate_signatures.txt"
    with patterns.open("x") as target:
        target.write("".join(op.split()[1] + "\n" for op in operands))
    # These directories contain only declared software proposals, not captured
    # labels. The current audit and new kit naturally contain these inputs.
    software = [root / name for name in SOFTWARE_DIRECTORIES]
    software.append((root / AUDIT).parent)
    for directory in software:
        assert not any(p.name in {"OPENED.json", "FREEZE.json", "hardware-output"} for p in directory.rglob("*"))
    excluded = software + [output]
    if private.is_relative_to(root):
        excluded.append(private)
    public_hits = matches(root, patterns, excluded)
    private_hits = matches(private, patterns, [])
    assert not public_hits and not private_hits, "freshness changed; no manifest frozen"
    rows = []
    for index, mode in enumerate(candidate.spec.MODES):
        for row in chosen:
            rows.append({"case_id": f"F{len(rows)+1:04d}", "capture_state": "FROZEN_UNOPENED",
                         "instruction": "fcos", "precision_control": "pc64", "mode": mode,
                         "operand": row["operand"], "kind": row["kind"], "origin": row["origin"],
                         "baseline": row["baseline_" + mode], "candidate": row["candidate_" + mode],
                         "candidate_C1": row["C1_bits"][index], "fourth_cut": row["fourth_cut"],
                         "square_low3": row["square_low3"], "boundary_edge": boundary_edge(row)})
    assert len(rows) == len({(r["instruction"], r["precision_control"], r["mode"], r["operand"]) for r in rows}) == 1668
    manifest = output / "manifest.tsv"
    with manifest.open("x", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader(); writer.writerows(rows)
    inputs = output / "inputs"; inputs.mkdir()
    lanes = {}
    for mode in candidate.spec.MODES:
        path = inputs / ("fcos_" + mode + ".txt")
        with path.open("x") as target:
            target.write("".join(row["operand"] + "\n" for row in rows if row["mode"] == mode))
        lanes["fcos_" + mode] = {"mode": mode, "instruction": "fcos", "rows": 417, "sha256": digest(path)}
    template = root / "experiments/h1624_run_capture.sh"
    runner = output / "run_capture.sh"
    with runner.open("x") as target:
        target.write(template.read_text())
    freshness = {"selected_public_collisions": 0, "selected_private_collisions": 0,
                 "private_files_examined": sum(p.is_file() for p in private.rglob("*")),
                 "private_identity_contents_or_hashes_published": False, "compressed_files_searched": True,
                 "policy": "reject any previously visible input significand, stricter than full tuple",
                 "software_only_public_directory_exceptions": [str(p.relative_to(root)) for p in software]}
    freeze = {"experiment": "h1624_fixed_candidate_adversarial", "capture_state": "FROZEN_UNOPENED",
              "frozen_utc": datetime.now(timezone.utc).isoformat(), "hardware_execution": "none",
              "new_hardware_labels": "none", "candidate_changed": False, "one_observation_maximum_per_tuple": True,
              "hardware_target": {"host": "45.32.204.118", "family": 6, "model": 85,
                                  "capture_binary_sha256": CAPTURE_SHA},
              "unique_operands": 417, "unique_capture_tuples": len(rows), "lanes": lanes,
              "selection_rule": "ALL 417 H1623-eligible operands, sorted, in each of RN/RD/RU/RZ; no further selection",
              "operand_kinds": dict(Counter(r["kind"] for r in chosen)),
              "boundary_cells": len({(r["fourth_cut"], r["square_low3"], boundary_edge(r)) for r in chosen if r["kind"] == "rounding_boundary_control"}),
              "model_disagreement_tuples": sum(r["baseline"] != r["candidate"] for r in rows),
              "independent_output_C1_checks": len(rows), "C_builds_replayed": 5,
              "freshness": freshness,
              "claim_boundary": "Finite direct-positive FCOS residual binade -3 challenge. C1 is predicted, not full SW. No general or physical-mechanism proof, promotion or paper update.",
              "sha256": {"evidence": locks, "manifest": digest(manifest), "runner": digest(runner),
                         "template": digest(template), "freezer": digest(Path(__file__)), "patterns": digest(patterns)}}
    frozen = output / "FREEZE.json"; write_json(frozen, freeze)
    with (output / "CHECKSUMS.sha256").open("x") as target:
        for path in (frozen, manifest, runner, patterns, *sorted(inputs.iterdir())):
            target.write(f"{digest(path)}  {path.relative_to(output)}\n")
    print(json.dumps({key: freeze[key] for key in ("unique_operands", "unique_capture_tuples", "operand_kinds", "boundary_cells", "model_disagreement_tuples", "freshness")}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
