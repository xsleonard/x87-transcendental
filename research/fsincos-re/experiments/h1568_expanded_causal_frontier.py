#!/usr/bin/env python3
"""Reconcile the historical R59 frontier with four opened lattice campaigns.

Only actually captured modes supply truth.  The original eleven miss rows
and the four immutable one-shot campaigns are deduplicated by mode/operand;
no unobserved rounding-mode result is inferred.  Replay the current ledger-off
C model, its two forced final-carry endpoints, and R1382's no-merge endpoint.
Numerical stage interventions are localization probes, never selector laws.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from h1400_causal_stage_localization import STAGES, digest, read_misses, run
from h1474_score_r1382_lattice import parse_hardware_line
from h1210_stagea_residual_reframe import parse_dump, run as dump_run


CAMPAIGNS = ("h1472", "h1477", "h1488", "h1566")
MODES = ("rn", "rd", "ru", "rz")


def read_campaign(root: Path, name: str, hashes: dict) -> list[dict]:
    kit = root / "transfer-tests" / name
    freeze = json.loads((kit / "FREEZE.json").read_text())
    opened = json.loads((kit / "OPENED.json").read_text())
    if opened["capture_state"] != "OPENED_ONCE" or opened["repeats"] != 0:
        raise RuntimeError(f"{name}: unverified capture state")
    if digest(kit / "FREEZE.json") != opened["sha256"]["freeze"]:
        raise RuntimeError(f"{name}: changed freeze")
    if digest(kit / "manifest.tsv") != freeze["sha256"]["manifest"]:
        raise RuntimeError(f"{name}: changed manifest")
    rows = list(csv.DictReader((kit / "manifest.tsv").open(), delimiter="\t"))
    if len(rows) != freeze["unique_capture_tuples"]:
        raise RuntimeError(f"{name}: tuple count differs")
    result = []
    for mode in ("rn", "rd", "ru"):
        selected = [row for row in rows if row["mode"] == mode]
        inputs = kit / "inputs" / f"fcos_{mode}.txt"
        raw = kit / "hardware-output" / f"fcos_{mode}.txt"
        if digest(inputs) != freeze["sha256"]["mode_inputs"][mode]:
            raise RuntimeError(f"{name}/{mode}: changed inputs")
        if digest(raw) != opened["sha256"][f"capture_fcos_{mode}"]:
            raise RuntimeError(f"{name}/{mode}: changed raw hardware")
        if inputs.read_text().splitlines() != [row["operand"] for row in selected]:
            raise RuntimeError(f"{name}/{mode}: changed positional inputs")
        lines = raw.read_text().splitlines()
        if len(lines) != len(selected):
            raise RuntimeError(f"{name}/{mode}: changed output count")
        hashes[str(raw.relative_to(root))] = digest(raw)
        for number, (row, line) in enumerate(zip(selected, lines), 1):
            value, status = parse_hardware_line(line, raw, number)
            if row["instruction"] != "fcos" or row["precision_control"] != "pc64":
                raise RuntimeError("campaign is outside the direct FCOS/PC64 scope")
            result.append({
                "source": name, "case_id": row["case_id"], "mode": mode,
                "operand": row["operand"].lower(), "hardware": value,
                "status": status, "frozen_incumbent": row["incumbent"],
                "frozen_nomerge": row.get("r1382", row.get("candidate")),
            })
    for filename in ("FREEZE.json", "OPENED.json", "manifest.tsv"):
        hashes[str((kit / filename).relative_to(root))] = digest(kit / filename)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--models", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    models = {name: (args.models / name).resolve()
              for name in ("baseline", "carry0", "carry1", "nomerge")}
    hashes = {}
    old = args.root / "tmp/ledger33/current/h1378_x67y64_attached_noledger_misses.tsv"
    _, truth, predictions = read_misses(old)
    rows = [{"source": "h1378", "case_id": f"old-{index:02d}",
             "mode": mode, "operand": operand, "hardware": value,
             "status": "", "frozen_incumbent": predictions[mode, operand],
             "frozen_nomerge": None}
            for index, ((mode, operand), value) in enumerate(sorted(truth.items()), 1)]
    hashes[str(old.relative_to(args.root))] = digest(old)
    for name in CAMPAIGNS:
        rows.extend(read_campaign(args.root, name, hashes))
    keys = [(row["mode"], row["operand"]) for row in rows]
    if len(set(keys)) != len(keys):
        raise RuntimeError("overlapping observed identities require explicit reconciliation")
    grouped = {mode: sorted({row["operand"] for row in rows if row["mode"] == mode})
               for mode in MODES}
    values = {}
    for name, model in models.items():
        values[name] = {}
        for mode, operands in grouped.items():
            if operands:
                values[name].update(run(model, mode, operands))
    traces = {}
    for mode, operands in grouped.items():
        if operands:
            _, stderr = dump_run(models["baseline"], mode, operands, dump=True)
            traces.update({(mode, op): row for op, row in
                           zip(operands, parse_dump(stderr, operands))})
    counts = defaultdict(Counter)
    for row in rows:
        key = row["mode"], row["operand"]
        if values["baseline"][key] != row["frozen_incumbent"]:
            raise RuntimeError(f"current baseline differs from frozen incumbent: {key}")
        if row["frozen_nomerge"] is not None \
                and values["nomerge"][key] != row["frozen_nomerge"]:
            raise RuntimeError(f"current no-merge differs from frozen endpoint: {key}")
        row["outputs"] = {name: outputs[key] for name, outputs in values.items()}
        row["baseline_exact"] = row["hardware"] == row["outputs"]["baseline"]
        row["allowed_carries"] = [carry for carry in (0, 1)
                                   if row["hardware"] == row["outputs"][f"carry{carry}"]]
        trace = traces[key]
        row["terminal_state"] = {
            field: trace[field] for field in (
                "branch", "s4", "theta", "low3", "side", "ce", "k",
                "dist", "payload", "rsh", "b1", "b2", "Mreg", "rd3",
                "tc_f4_sig", "tc_rf_sig") if field in trace}
        counts[row["source"]]["observed_rows"] += 1
        counts[row["source"]]["baseline_exact" if row["baseline_exact"] else "baseline_miss"] += 1
        counts[row["source"]]["carry_" + "".join(map(str, row["allowed_carries"]))] += 1

    interventions = []
    for stage in STAGES:
        for delta in (-1, 1):
            output = {}
            for mode, operands in grouped.items():
                if operands:
                    output.update(run(models["baseline"], mode, operands,
                                      f"{stage.argument}:{delta}"))
            repaired = [r["case_id"] for r in rows if not r["baseline_exact"]
                        and output[r["mode"], r["operand"]] == r["hardware"]]
            broken = [r["case_id"] for r in rows if r["baseline_exact"]
                      and output[r["mode"], r["operand"]] != r["hardware"]]
            interventions.append({"stage": stage.name, "delta": delta,
                                  "repaired_count": len(repaired),
                                  "broken_count": len(broken),
                                  "repaired_cases": repaired, "broken_cases": broken})
    misses = [row for row in rows if not row["baseline_exact"]]
    report = {
        "experiment": "h1568_expanded_causal_frontier",
        "hardware_execution": "none_existing_raw_captures_only",
        "scope": "direct_FCOS_PC64_h1378_plus_h1472_h1477_h1488_h1566_observed_modes",
        "claim_boundary": "lower_bound_on_known_global_failures_not_a_full_repository_census",
        "unique_observed_rows": len(rows),
        "unique_observed_operands": len({row["operand"] for row in rows}),
        "baseline_miss_rows": len(misses),
        "baseline_miss_operands": len({row["operand"] for row in misses}),
        "all_observed_rows_have_exact_forced_carry": all(row["allowed_carries"] for row in rows),
        "counts_by_source": {name: dict(sorted(count.items())) for name, count in counts.items()},
        "stage_interventions": interventions,
        "rows": rows,
        "sha256": {"evidence": hashes,
                   "models": {name: digest(path) for name, path in models.items()},
                   "source": digest(args.root / "src/fsincos_skylake.c")},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps({key: report[key] for key in (
        "unique_observed_rows", "unique_observed_operands", "baseline_miss_rows",
        "baseline_miss_operands", "all_observed_rows_have_exact_forced_carry",
        "counts_by_source")}, sort_keys=True))


if __name__ == "__main__":
    main()
