#!/usr/bin/env python3
"""Score the H1570 frozen residual-state transfer prediction, without a rerun."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from h1474_score_r1382_lattice import parse_hardware_line
from h1566_freeze_pair_a_adversarial import digest


def classify(row: dict, hardware: str) -> dict:
    return {"transfer_exact": hardware == row["transfer_prediction"],
            "baseline_exact": hardware == row["baseline"],
            "allowed_carries": [c for c in (0, 1) if hardware == row[f"carry{c}"]]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kit", required=True, type=Path)
    parser.add_argument("--output-prefix", required=True, type=Path)
    parser.add_argument("--mark-opened", action="store_true")
    args = parser.parse_args()
    toy = {"transfer_prediction": "a", "baseline": "b", "carry0": "b", "carry1": "a"}
    assert classify(toy, "a") == {"transfer_exact": True, "baseline_exact": False, "allowed_carries": [1]}
    assert classify(toy, "b") == {"transfer_exact": False, "baseline_exact": True, "allowed_carries": [0]}
    assert classify(toy, "c") == {"transfer_exact": False, "baseline_exact": False, "allowed_carries": []}
    report_path = args.output_prefix.with_name(args.output_prefix.name + "_report.json")
    score_path = args.output_prefix.with_name(args.output_prefix.name + "_score.tsv")
    for path in (report_path, score_path):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")
    opened_path = args.kit / "OPENED.json"
    if args.mark_opened and opened_path.exists():
        raise SystemExit("opened sidecar already exists; replay without --mark-opened")
    freeze_path = args.kit / "FREEZE.json"
    freeze = json.loads(freeze_path.read_text())
    assert freeze["experiment"] == "h1570_exact_preimage_transfer"
    assert freeze["capture_state"] == "FROZEN_UNOPENED"
    assert freeze["one_observation_maximum_per_tuple"] is True
    for line in (args.kit / "CHECKSUMS.sha256").read_text().splitlines():
        checksum, name = line.split(None, 1)
        relative = Path(name.strip())
        assert not relative.is_absolute() and ".." not in relative.parts
        assert digest(args.kit / relative) == checksum
    manifest = args.kit / "manifest.tsv"
    assert digest(manifest) == freeze["sha256"]["manifest"]
    rows = list(csv.DictReader(manifest.open(), delimiter="\t"))
    assert len(rows) == freeze["unique_capture_tuples"]
    assert len({(r["instruction"], r["mode"], r["operand"]) for r in rows}) == len(rows)
    raw_dir = args.kit / "hardware-output"
    remote_hashes = {}
    for line in (raw_dir / "outputs.sha256").read_text().splitlines():
        checksum, name = line.split(None, 1)
        remote_hashes[Path(name.strip()).name] = checksum
    hashes = {}
    observed = {}
    for name, lane in freeze["lanes"].items():
        selected = [r for r in rows if (r["instruction"], r["mode"])
                    == (lane["instruction"], lane["mode"])]
        inputs = args.kit / "inputs" / f"{name}.txt"
        assert digest(inputs) == lane["sha256"]
        assert inputs.read_text().splitlines() == [r["operand"] for r in selected]
        assert len(selected) == lane["rows"]
        raw = raw_dir / f"{name}.txt"
        lines = raw.read_text().splitlines()
        assert len(lines) == len(selected)
        hashes[raw.name] = digest(raw)
        assert hashes[raw.name] == remote_hashes[raw.name]
        for number, (row, line) in enumerate(zip(selected, lines), 1):
            observed[row["case_id"]] = parse_hardware_line(line, raw, number)
    assert set(remote_hashes) == set(hashes)
    scored = []
    families = defaultdict(list)
    counts = Counter()
    for row in rows:
        assert row["capture_state"] == "FROZEN_UNOPENED"
        assert row["precision_control"] == "pc64"
        hardware, status = observed[row["case_id"]]
        verdict = classify(row, hardware)
        record = dict(row, hardware=hardware, hardware_status=status,
                      transfer_verdict="EXACT" if verdict["transfer_exact"] else "MISS",
                      baseline_verdict="EXACT" if verdict["baseline_exact"] else "MISS",
                      allowed_carries="".join(map(str, verdict["allowed_carries"])))
        counts[f"transfer.{record['transfer_verdict']}"] += 1
        counts[f"baseline.{record['baseline_verdict']}"] += 1
        counts[f"{row['instruction']}.transfer.{record['transfer_verdict']}"] += 1
        counts[f"carry.{record['allowed_carries'] or 'other'}"] += 1
        families[row["family_id"]].append(record)
        scored.append(record)
    family_summary = []
    for family_id, members in families.items():
        assert len(members) == 2 and {m["role"] for m in members} == {"low_q", "high_q"}
        assert len({(m["anchor"], m["instruction"], m["mode"]) for m in members}) == 1
        family_summary.append({"family_id": family_id, "anchor": members[0]["anchor"],
                               "quotient_pair_agrees": len({m["hardware"] for m in members}) == 1,
                               "both_transfer_exact": all(m["transfer_verdict"] == "EXACT" for m in members),
                               "carry64_separated": len({m["carry64"] for m in members}) == 2})
    score_path.parent.mkdir(parents=True, exist_ok=True)
    with score_path.open("x", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(scored[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(scored)
    report = {"experiment": "h1571_score_exact_preimage_transfer", "observed_rows": len(scored),
              "repeats": 0, "counts": dict(sorted(counts.items())), "families": family_summary,
              "quotient_pair_splits": sum(not f["quotient_pair_agrees"] for f in family_summary),
              "hypothesis_verdict": "SURVIVES_FINITE_BANK" if counts["transfer.EXACT"] == len(rows)
                                    else "DIRECT_ANCHOR_TRANSFER_FALSIFIED",
              "claim_boundary": "same_exposed_model_state_test_not_proof_of_hidden_silicon_state_or_selector",
              "sha256": {"freeze": digest(freeze_path), "manifest": digest(manifest),
                         "score": digest(score_path), "scorer": digest(Path(__file__)),
                         "raw_captures": hashes}}
    with report_path.open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")
    if args.mark_opened:
        opened = {"experiment": freeze["experiment"], "capture_state": "OPENED_ONCE",
                  "hardware": "skylake_xeon_vm_oracle", "unique_capture_tuples": len(rows),
                  "repeats": 0, "paper_change": "none", "emulator_change": "none",
                  "hypothesis_verdict": report["hypothesis_verdict"],
                  "freshness": freeze["freshness"], "counts": report["counts"],
                  "sha256": dict(report["sha256"], report=digest(report_path),
                                 capture_metadata={p.name: digest(p) for p in sorted(raw_dir.iterdir())
                                                   if p.name not in hashes})}
        with opened_path.open("x") as target:
            json.dump(opened, target, indent=2, sort_keys=True)
            target.write("\n")
    print(json.dumps({k: report[k] for k in ("observed_rows", "counts", "quotient_pair_splits",
                                            "hypothesis_verdict")}, sort_keys=True))


if __name__ == "__main__":
    main()
