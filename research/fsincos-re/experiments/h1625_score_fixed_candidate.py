#!/usr/bin/env python3
"""Score immutable H1624 predictions/actual C1, preserving all raw SW bits.

This script is frozen before capture. It never runs x87 and refuses to
overwrite scores or the OPENED_ONCE sidecar. Shared-output agreement rows
are distinguished from the three actual candidate/incumbent discriminators.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--mark-opened", action="store_true")
    args = parser.parse_args()
    kit, output = args.kit.resolve(), args.output_dir.resolve()
    assert not output.exists() and not (args.mark_opened and (kit / "OPENED.json").exists())
    checked = set()
    for line in (kit / "CHECKSUMS.sha256").read_text().splitlines():
        expected, name = line.split(None, 1); path = Path(name.strip())
        assert not path.is_absolute() and ".." not in path.parts and str(path) not in checked
        assert digest(kit / path) == expected
        checked.add(str(path))
    assert checked == {"FREEZE.json", "manifest.tsv", "run_capture.sh", "candidate_signatures.txt",
                       *(f"inputs/fcos_{mode}.txt" for mode in ("rn", "rd", "ru", "rz"))}
    freeze = json.loads((kit / "FREEZE.json").read_text())
    assert freeze["experiment"] == "h1624_fixed_candidate_adversarial" and freeze["capture_state"] == "FROZEN_UNOPENED"
    assert freeze["one_observation_maximum_per_tuple"] and freeze["candidate_changed"] is False
    assert digest(kit / "manifest.tsv") == freeze["sha256"]["manifest"]
    assert digest(kit / "run_capture.sh") == freeze["sha256"]["runner"]
    with (kit / "manifest.tsv").open(newline="") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    assert len(rows) == freeze["unique_capture_tuples"] == 1668
    assert len({r["case_id"] for r in rows}) == len({(r["instruction"], r["precision_control"], r["mode"], r["operand"]) for r in rows}) == len(rows)
    assert len({r["operand"] for r in rows}) == freeze["unique_operands"] == 417
    raw = kit / "hardware-output"
    assert (raw / "binary.sha256").read_text().split()[0] == freeze["hardware_target"]["capture_binary_sha256"]
    cpu = (raw / "cpu-summary.txt").read_text()
    assert re.search(r"vendor_id\s*:\s*GenuineIntel", cpu)
    assert re.search(r"cpu family\s*:\s*6\s*$", cpu, re.M)
    assert re.search(r"^model\s*:\s*85\s*$", cpu, re.M)
    assert (raw / "complete-utc.txt").is_file()
    hashes = {}
    for line in (raw / "outputs.sha256").read_text().splitlines():
        expected, name = line.split(None, 1)
        assert name.strip() == "hardware-output/" + Path(name.strip()).name
        assert Path(name.strip()).name not in hashes
        hashes[Path(name.strip()).name] = expected
    assert set(hashes) == {lane + ".txt" for lane in freeze["lanes"]}
    observed = {}
    for name, lane in freeze["lanes"].items():
        selected = [r for r in rows if r["mode"] == lane["mode"]]
        inputs = kit / "inputs" / (name + ".txt")
        assert inputs.read_text().splitlines() == [r["operand"] for r in selected]
        assert digest(inputs) == lane["sha256"]
        path = raw / (name + ".txt"); lines = path.read_text().splitlines()
        assert len(lines) == len(selected) == lane["rows"] and digest(path) == hashes[path.name]
        for row, line in zip(selected, lines):
            match = re.fullmatch(r"OK ([0-9a-fA-F]{4}) ([0-9a-fA-F]{16}) SW ([0-9a-fA-F]{4})", line)
            assert match, "malformed raw row"
            se, sig, sw = (word.lower() for word in match.groups())
            observed[row["case_id"]] = (se + ":" + sig, sw)
    counts, cells, scored = Counter(), defaultdict(Counter), []
    for row in rows:
        assert row["instruction"] == "fcos" and row["precision_control"] == "pc64" and row["capture_state"] == "FROZEN_UNOPENED"
        assert row["mode"] in ("rn", "rd", "ru", "rz") and row["candidate_C1"] in ("0", "1")
        value, status = observed[row["case_id"]]
        c1 = (int(status, 16) >> 9) & 1
        record = dict(row, hardware=value, hardware_status=status, hardware_C1=str(c1),
                      candidate_output_exact=value == row["candidate"], baseline_output_exact=value == row["baseline"],
                      candidate_C1_exact=str(c1) == row["candidate_C1"], models_disagree=row["candidate"] != row["baseline"])
        metrics = {"observed": True, **{key: record[key] for key in (
            "candidate_output_exact", "baseline_output_exact", "candidate_C1_exact", "models_disagree")}}
        for key, truth in metrics.items():
            counts[key] += int(truth); cells[row["kind"]][key] += int(truth)
        scored.append(record)
    assert counts["models_disagree"] == freeze["model_disagreement_tuples"] == 3
    output.mkdir(parents=True)
    score = output / "score.tsv"
    with score.open("x", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(scored[0]), delimiter="\t")
        writer.writeheader(); writer.writerows(scored)
    report = {"experiment": "h1625_score_fixed_candidate", "capture_state": "OPENED_ONCE",
              "unique_operands": 417, "unique_capture_tuples": 1668, "repeats": 0,
              "counts": dict(counts), "cells": {key: dict(value) for key, value in cells.items()},
              "candidate_output_misses": [r for r in scored if not r["candidate_output_exact"]],
              "candidate_C1_misses": [r for r in scored if not r["candidate_C1_exact"]],
              "baseline_output_misses": [r for r in scored if not r["baseline_output_exact"]],
              "discriminators": [r for r in scored if r["models_disagree"]],
              "verdict": "FIXED_CANDIDATE_SURVIVES_FINITE_FRESH_BANK" if counts["candidate_output_exact"] == counts["candidate_C1_exact"] == 1668 else "FIXED_CANDIDATE_FALSIFIED",
              "claim_boundary": "Positive-direct FCOS binade -3 only; output plus C1, not general correctness, other domains, physical mechanism or full status. No promotion or paper update.",
              "sha256": {"freeze": digest(kit / "FREEZE.json"), "manifest": digest(kit / "manifest.tsv"),
                         "score": digest(score), "scorer": digest(Path(__file__)), "raw_outputs": hashes,
                         "raw_metadata": {p.name: digest(p) for p in raw.iterdir() if p.is_file() and p.name not in hashes}}}
    with (output / "report.json").open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True); target.write("\n")
    if args.mark_opened:
        record = {"experiment": freeze["experiment"], "capture_state": "OPENED_ONCE", "repeats": 0,
                  "unique_capture_tuples": 1668, "candidate_changed": False, "paper_change": "none", "emulator_default_change": "none",
                  "verdict": report["verdict"], "counts": dict(counts), "freshness": freeze["freshness"],
                  "sha256": dict(report["sha256"], report=digest(output / "report.json"))}
        with (kit / "OPENED.json").open("x") as target:
            json.dump(record, target, indent=2, sort_keys=True); target.write("\n")
    print(json.dumps({key: report[key] for key in ("unique_capture_tuples", "counts", "verdict", "discriminators")}, sort_keys=True))


if __name__ == "__main__":
    main()
