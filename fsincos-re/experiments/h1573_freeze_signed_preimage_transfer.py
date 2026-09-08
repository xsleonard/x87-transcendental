#!/usr/bin/env python3
"""Freeze both exact residual sides for H1570's omitted parity classes.

The minimum fresh quotient on each side is selected independently of its
hardware output.  The input sign stays positive; quadrant projection may
negate the cosine output and correspondingly swap the capture rounding mode.
This is a one-shot transfer challenge, not a new model selector.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from h1570_freeze_exact_preimage_transfer import collision_signatures, digest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--private-ledger-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise SystemExit(f"refusing to overwrite {args.output_dir}")
    assert args.private_ledger_dir.is_dir()
    source_path = args.root / "tmp/ledger33/current/h1572_signed_preimage_projection.json"
    enumeration = args.root / "tmp/ledger33/current/h1569_algebraic_preimage_families.json"
    source = json.loads(source_path.read_text())
    assert source["experiment"] == "h1572_signed_preimage_projection"
    assert source["capture_state"] == "SOFTWARE_ONLY_NOT_FROZEN"
    assert source["counts"]["trace_mismatches"] == source["counts"]["forced_endpoint_mismatches"] == 0
    assert digest(enumeration) == source["sha256"]["source_report"]
    candidates = [c for f in source["families"] for c in f["candidates"]]
    signatures = {c["operand"].split()[1] for c in candidates}
    excluded = {source_path.resolve(), enumeration.resolve()}
    rejected = (collision_signatures(signatures, args.root, excluded)
                | collision_signatures(signatures, args.private_ledger_dir, set()))
    rows = []
    for index, family in enumerate(source["families"], 1):
        for side in (-1, 1):
            fresh = [c for c in family["candidates"] if c["residual_side"] == side
                     and c["operand"].split()[1] not in rejected]
            if not fresh:
                raise RuntimeError("one residual side lacks a fresh exact preimage; freeze aborted")
            c = min(fresh, key=lambda c: c["quotient"])
            assert c["trace_and_endpoint_equal_all_modes"] and c["forced_endpoints_equal"]
            assert c["outputs"]["carry0"] != c["outputs"]["carry1"]
            rows.append({"case_id": f"V{len(rows)+1:03d}", "family_id": f"S{index:02d}",
                         "capture_state": "FROZEN_UNOPENED", "instruction": c["instruction"],
                         "mode": c["mode"], "precision_control": "pc64", "operand": c["operand"],
                         "quotient": c["quotient"], "residual_side": side,
                         "output_negative": int(c["output_negative"]),
                         "anchor": family["anchor"], "anchor_mode": family["anchor_mode"],
                         "anchor_source": family["source"], "anchor_case_id": family["case_id"],
                         "anchor_hardware": family["anchor_hardware"],
                         "anchor_baseline_exact": int(family["anchor_baseline_exact"]),
                         "transfer_prediction": c["transfer_prediction"], **c["outputs"],
                         "canonical_trace_equal_all_modes": 1,
                         "direct_trace_sha256": family["direct_trace_sha256"]})
    assert len(rows) == 28 and len({r["operand"].split()[1] for r in rows}) == len(rows)
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
        group = [r for r in rows if (r["instruction"], r["mode"]) == (instruction, mode)]
        path = inputs / f"{name}.txt"
        with path.open("x") as target:
            target.write("".join(r["operand"] + "\n" for r in group))
        lanes[name] = {"instruction": instruction, "mode": mode, "rows": len(group), "sha256": digest(path)}
    # Reuse the already-reviewed H1570 one-shot guard and metadata prelude.
    # The immutable source runner hash is checked before deriving this kit.
    prior = args.root / "transfer-tests/h1570"
    previous_freeze = json.loads((prior / "FREEZE.json").read_text())
    assert digest(prior / "run_capture.sh") == previous_freeze["sha256"]["runner"]
    prelude = (prior / "run_capture.sh").read_text().split('"$BIN" rd pc64 cos --status')[0]
    assert prelude.endswith('sha256sum "$BIN" > hardware-output/binary.sha256\n')
    lines = [prelude.replace("H1570", "H1573").rstrip()]
    for name, lane in lanes.items():
        lines.append(f'"$BIN" {lane["mode"]} pc64 {lane["instruction"][1:]} --status < inputs/{name}.txt > hardware-output/{name}.txt')
    lines.extend(["sha256sum hardware-output/f*.txt > hardware-output/outputs.sha256",
                  'echo "H1573_CAPTURE_COMPLETE tuples=28 repeats=0"'])
    runner = args.output_dir / "run_capture.sh"
    with runner.open("x") as target:
        target.write("\n".join(lines) + "\n")
    freeze = {"experiment": "h1573_signed_preimage_transfer", "capture_state": "FROZEN_UNOPENED",
              "unique_capture_tuples": len(rows), "anchor_families": len(rows)//2,
              "one_observation_maximum_per_tuple": True, "hardware_execution": "none", "new_hardware_labels": "none",
              "selection_rule": "minimum_fresh_quotient_per_residual_sign_for_each_previously_omitted_anchor",
              "hypothesis": "direct_anchor_hardware_endpoint_transfers_under_exact_residual_and_output_sign_projection",
              "claim_boundary": "finite_sign_quadrant_transfer_not_a_general_selector", "lanes": lanes,
              "instruction_counts": dict(Counter(r["instruction"] for r in rows)),
              "negative_output_rows": sum(r["output_negative"] for r in rows),
              "mode_swapped_rows": sum(r["mode"] != r["anchor_mode"] for r in rows),
              "anchor_baseline_exact_counts": dict(Counter(str(r["anchor_baseline_exact"]) for r in rows)),
              "freshness": {"selected_repository_collision_count": 0, "selected_private_collision_count": 0,
                            "rejected_candidate_significands": len(rejected),
                            "private_files_examined": sum(p.is_file() for p in args.private_ledger_dir.rglob("*")),
                            "private_identity_published": False},
              "sha256": {"source_report": digest(source_path), "enumeration": digest(enumeration),
                         "manifest": digest(manifest), "runner": digest(runner), "freezer": digest(Path(__file__)),
                         "runner_template": digest(prior / "run_capture.sh")}}
    freeze_path = args.output_dir / "FREEZE.json"
    with freeze_path.open("x") as target:
        json.dump(freeze, target, indent=2, sort_keys=True)
        target.write("\n")
    with (args.output_dir / "CHECKSUMS.sha256").open("x") as target:
        for path in [freeze_path, manifest, runner, *sorted(inputs.iterdir())]:
            target.write(f"{digest(path)}  {path.relative_to(args.output_dir)}\n")
    print(json.dumps({k: freeze[k] for k in ("unique_capture_tuples", "anchor_families", "freshness",
                                            "instruction_counts", "negative_output_rows", "mode_swapped_rows")}, sort_keys=True))


if __name__ == "__main__":
    main()
