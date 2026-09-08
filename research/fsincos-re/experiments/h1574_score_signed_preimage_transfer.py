#!/usr/bin/env python3
"""Score H1573 in both architectural and sign-normalized anchor coordinates."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from h1474_score_r1382_lattice import parse_hardware_line
from h1570_freeze_exact_preimage_transfer import digest
from h1571_score_exact_preimage_transfer import classify
from h1572_signed_preimage_projection import project_mode, project_value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kit", required=True, type=Path)
    parser.add_argument("--output-prefix", required=True, type=Path)
    parser.add_argument("--mark-opened", action="store_true")
    args = parser.parse_args()
    score_path = args.output_prefix.with_name(args.output_prefix.name + "_score.tsv")
    report_path = args.output_prefix.with_name(args.output_prefix.name + "_report.json")
    for path in (score_path, report_path):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")
    opened_path = args.kit / "OPENED.json"
    if args.mark_opened and opened_path.exists():
        raise SystemExit("opened sidecar exists; replay without --mark-opened")
    for negative in (False, True):
        for mode in ("rn", "rd", "ru", "rz"):
            assert project_mode(project_mode(mode, negative), negative) == mode
        assert project_value(project_value("3ffe:123456789abcdef0", negative), negative) == "3ffe:123456789abcdef0"
    freeze_path = args.kit / "FREEZE.json"
    freeze = json.loads(freeze_path.read_text())
    assert freeze["experiment"] == "h1573_signed_preimage_transfer"
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
    assert len(rows) == freeze["unique_capture_tuples"] == 28
    assert len({(r["instruction"], r["mode"], r["operand"]) for r in rows}) == len(rows)
    raw_dir = args.kit / "hardware-output"
    remote_hashes = {Path(name.strip()).name: checksum for checksum, name in
                     (line.split(None, 1) for line in (raw_dir / "outputs.sha256").read_text().splitlines())}
    observed, raw_hashes = {}, {}
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
        raw_hashes[raw.name] = digest(raw)
        assert raw_hashes[raw.name] == remote_hashes[raw.name]
        for number, (row, line) in enumerate(zip(selected, lines), 1):
            observed[row["case_id"]] = parse_hardware_line(line, raw, number)
    assert set(raw_hashes) == set(remote_hashes)
    scored, groups, counts = [], defaultdict(list), Counter()
    for row in rows:
        assert row["capture_state"] == "FROZEN_UNOPENED" and row["precision_control"] == "pc64"
        negative = bool(int(row["output_negative"]))
        assert row["mode"] == project_mode(row["anchor_mode"], negative)
        assert row["transfer_prediction"] == project_value(row["anchor_hardware"], negative)
        value, status = observed[row["case_id"]]
        verdict = classify(row, value)
        projected = project_value(value, negative)
        assert verdict["transfer_exact"] == (projected == row["anchor_hardware"])
        item = dict(row, hardware=value, hardware_status=status, projected_hardware=projected,
                    transfer_verdict="EXACT" if verdict["transfer_exact"] else "MISS",
                    baseline_verdict="EXACT" if verdict["baseline_exact"] else "MISS",
                    allowed_carries="".join(map(str, verdict["allowed_carries"])))
        scored.append(item)
        groups[row["family_id"]].append(item)
        counts[f"transfer.{item['transfer_verdict']}"] += 1
        counts[f"baseline.{item['baseline_verdict']}"] += 1
        counts[f"{row['instruction']}.baseline.{item['baseline_verdict']}"] += 1
        counts[f"carry.{item['allowed_carries'] or 'other'}"] += 1
    families = []
    for name, members in groups.items():
        assert len(members) == 2 and {m["residual_side"] for m in members} == {"-1", "1"}
        assert len({(m["anchor"], m["anchor_mode"]) for m in members}) == 1
        families.append({"family_id": name, "anchor": members[0]["anchor"],
                         "projected_side_pair_agrees": len({m["projected_hardware"] for m in members}) == 1,
                         "both_transfer_exact": all(m["transfer_verdict"] == "EXACT" for m in members)})
    score_path.parent.mkdir(parents=True, exist_ok=True)
    with score_path.open("x", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(scored[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(scored)
    report = {"experiment": "h1574_score_signed_preimage_transfer", "observed_rows": len(scored),
              "repeats": 0, "counts": dict(sorted(counts.items())), "families": families,
              "residual_side_pair_splits": sum(not f["projected_side_pair_agrees"] for f in families),
              "hypothesis_verdict": "SURVIVES_FINITE_BANK" if counts["transfer.EXACT"] == len(rows)
                                    else "SIGNED_TRANSFER_FALSIFIED",
              "claim_boundary": "finite_exact_sign_quadrant_transfer_not_global_selector_proof",
              "sha256": {"freeze": digest(freeze_path), "manifest": digest(manifest),
                         "score": digest(score_path), "scorer": digest(Path(__file__)), "raw_captures": raw_hashes}}
    with report_path.open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")
    if args.mark_opened:
        opened = {"experiment": freeze["experiment"], "capture_state": "OPENED_ONCE",
                  "hardware": "skylake_xeon_vm_oracle", "unique_capture_tuples": len(rows), "repeats": 0,
                  "paper_change": "none", "emulator_change": "none", "freshness": freeze["freshness"],
                  "counts": report["counts"], "hypothesis_verdict": report["hypothesis_verdict"],
                  "sha256": dict(report["sha256"], report=digest(report_path),
                                 capture_metadata={p.name: digest(p) for p in sorted(raw_dir.iterdir())
                                                   if p.name not in raw_hashes})}
        with opened_path.open("x") as target:
            json.dump(opened, target, indent=2, sort_keys=True)
            target.write("\n")
    print(json.dumps({k: report[k] for k in ("observed_rows", "counts", "residual_side_pair_splits",
                                            "hypothesis_verdict")}, sort_keys=True))


if __name__ == "__main__":
    main()
