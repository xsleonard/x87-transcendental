#!/usr/bin/env python3
"""Audit current promoted rule composition against old controls and new misses.

Fixed single-rule ablations are causal probes, not candidate selectors.  No
hardware is run, and the current emulator source/defaults remain unchanged.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from h1400_causal_stage_localization import run, digest
from h1210_stagea_residual_reframe import parse_dump, run as dump_run
from h1564_shared_tree_automorphism_wall import CASES, cached_h1531_rows


CONFIGS = {
    "baseline": [],
    "no_equality": ["G_R1263EQGATE=0"],
    "no_hard3_merge": ["G_R1270MERGE3X=0"],
    "unconditional_hard3_merge": ["G_R1272MERGEGATE=0"],
    "no_negative_history": ["G_R1378X67Y64=0"],
    "no_positive_history": ["G_R1237CPAFADD=0"],
    "none_of_five": ["G_R1263EQGATE=0", "G_R1270MERGE3X=0", "G_R1272MERGEGATE=0",
                     "G_R1378X67Y64=0", "G_R1237CPAFADD=0"],
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--build-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.build_dir.exists():
        raise SystemExit("refusing an existing build directory or output")
    source = args.root / "src/fsincos_skylake.c"
    frontier_path = args.root / "tmp/ledger33/current/h1568_expanded_causal_frontier.json"
    frontier = json.loads(frontier_path.read_text())
    assert digest(source) == frontier["sha256"]["source"]
    wall_path = args.root / "tmp/ledger33/current/h1531_shared_tree_topology_audit.json"
    wall = cached_h1531_rows(json.loads(wall_path.read_text()))
    rows = [dict(r) for r in frontier["rows"]]
    for case in CASES:
        assert wall[case["mode"], case["operand"]] == case["hardware"]
        rows.append({"source": "h1531_defining_control", "case_id": case["name"],
                     "mode": case["mode"], "operand": case["operand"], "hardware": case["hardware"],
                     "baseline_exact": True, "outputs": {"baseline": case["hardware"]}})
    assert len({(r["mode"], r["operand"]) for r in rows}) == len(rows)
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["mode"]].append(row["operand"])
    args.build_dir.mkdir(parents=True)
    models, summaries = {}, {}
    for name, defines in CONFIGS.items():
        binary = (args.build_dir / name).resolve()
        command = ["cc", "-O2", "-std=c11", "-DG_ROUND84=0", *["-D"+d for d in defines],
                   str(source.resolve()), "-lm", "-o", str(binary)]
        subprocess.run(command, check=True, capture_output=True, text=True)
        outputs = {}
        traces = {}
        for mode, operands in grouped.items():
            outputs.update(run(binary, mode, operands))
            _, stderr = dump_run(binary, mode, operands, dump=True)
            traces.update({(mode, op): t for op, t in zip(operands, parse_dump(stderr, operands))})
        counts = Counter()
        changes = []
        for row in rows:
            key = row["mode"], row["operand"]
            base = row["outputs"]["baseline"]
            value = outputs[key]
            if name == "baseline":
                assert value == base, key
            row.setdefault("ablation_outputs", {})[name] = value
            counts["exact" if value == row["hardware"] else "miss"] += 1
            if value != base:
                kind = "regression" if row["baseline_exact"] else "repair" if value == row["hardware"] else "other_change"
                counts[kind] += 1
                changes.append({"case_id": row["case_id"], "source": row["source"],
                                "mode": row["mode"], "operand": row["operand"], "kind": kind,
                                "baseline": base, "ablation": value, "hardware": row["hardware"],
                                "branch": traces[key].get("branch"),
                                "theta": traces[key].get("theta"), "low3": traces[key].get("low3")})
        summaries[name] = {"defines": ["G_ROUND84=0", *defines], "counts": dict(counts), "changes": changes}
        models[name] = digest(binary)
        print(name, dict(counts), flush=True)
    invariant = [r["case_id"] for r in rows if not r["baseline_exact"]
                 and len(set(r["ablation_outputs"].values())) == 1]
    report = {"experiment": "h1575_current_rule_ablation", "hardware_execution": "none_cached_observations_only",
              "selector_claim": "none", "observed_rows": len(rows),
              "baseline_misses": sum(not r["baseline_exact"] for r in rows),
              "invariant_miss_cases": invariant, "configurations": summaries, "rows": rows,
              "claim_boundary": "seven_fixed_programs_on_56_observed_rows_not_global_falsification_of_each_component",
              "sha256": {"source": digest(source), "frontier": digest(frontier_path),
                         "defining_wall": digest(wall_path), "models": models, "script": digest(Path(__file__))}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")


if __name__ == "__main__":
    main()
