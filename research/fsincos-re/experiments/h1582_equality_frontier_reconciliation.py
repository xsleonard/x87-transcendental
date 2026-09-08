#!/usr/bin/env python3
"""Localize H1580 and count distinct residual failures separately from aliases.

Only opened, hash-checked observations supply labels. Software interventions
are causal probes, not candidate selectors or proof of a physical circuit.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from h1400_causal_stage_localization import STAGES, digest, run
from h1474_score_r1382_lattice import parse_hardware_line
from h1575_current_rule_ablation import CONFIGS
from h1569_algebraic_preimage_families import replay


def checked_score(root: Path, campaign: str, stem: str, evidence: dict) -> list[dict]:
    kit = root / "transfer-tests" / campaign
    prefix = root / "tmp/ledger33/current" / stem
    report_path = prefix.with_name(prefix.name + "_report.json")
    score_path = prefix.with_name(prefix.name + "_score.tsv")
    opened = json.loads((kit / "OPENED.json").read_text())
    report = json.loads(report_path.read_text())
    freeze = json.loads((kit / "FREEZE.json").read_text())
    assert opened["capture_state"] == "OPENED_ONCE" and opened["repeats"] == 0
    assert digest(report_path) == opened["sha256"]["report"]
    assert digest(score_path) == opened["sha256"]["score"] == report["sha256"]["score"]
    assert digest(kit / "FREEZE.json") == opened["sha256"]["freeze"]
    for line in (kit / "CHECKSUMS.sha256").read_text().splitlines():
        checksum, name = line.split(None, 1)
        rel = Path(name.strip())
        assert not rel.is_absolute() and ".." not in rel.parts
        assert digest(kit / rel) == checksum
    rows = list(csv.DictReader(score_path.open(), delimiter="\t"))
    assert len(rows) == report["observed_rows"] == freeze["unique_capture_tuples"]
    for name, lane in freeze["lanes"].items():
        selected = [r for r in rows if (r["instruction"], r["mode"])
                    == (lane["instruction"], lane["mode"])]
        inputs = kit / "inputs" / (name + ".txt")
        raw = kit / "hardware-output" / (name + ".txt")
        assert digest(inputs) == lane["sha256"]
        assert inputs.read_text().splitlines() == [r["operand"] for r in selected]
        assert digest(raw) == report["sha256"]["raw_captures"][raw.name]
        lines = raw.read_text().splitlines()
        assert len(lines) == len(selected) == lane["rows"]
        for number, (row, line) in enumerate(zip(selected, lines), 1):
            assert parse_hardware_line(line, raw, number) == (row["hardware"], row["hardware_status"])
        evidence[str(raw.relative_to(root))] = digest(raw)
    for path in (report_path, score_path, kit / "OPENED.json", kit / "FREEZE.json"):
        evidence[str(path.relative_to(root))] = digest(path)
    return rows


def census(rows: list[dict]) -> dict:
    keys = {(r["instruction"], r["mode"], r["operand"]) for r in rows}
    assert len(keys) == len(rows), "overlap needs explicit reconciliation"
    misses = [r for r in rows if not r["baseline_exact"]]
    return {"observed_rows": len(rows), "external_operands": len({r["operand"] for r in rows}),
            "baseline_miss_rows": len(misses), "baseline_miss_operands": len({r["operand"] for r in misses}),
            "misses_by_instruction": dict(Counter(r["instruction"] for r in misses)),
            "all_rows_have_one_exact_forced_carry": all(len(r["allowed_carries"]) == 1 for r in rows)}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--root", required=True, type=Path)
    p.add_argument("--carry-models", required=True, type=Path)
    p.add_argument("--ablation-models", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    if a.output.exists():
        raise SystemExit("refusing to overwrite evidence")
    current = a.root / "tmp/ledger33/current"
    frontier_path = current / "h1568_expanded_causal_frontier.json"
    ablation_path = current / "h1575_current_rule_ablation.json"
    frontier = json.loads(frontier_path.read_text())
    ablation = json.loads(ablation_path.read_text())
    source_hash = digest(a.root / "src/fsincos_skylake.c")
    assert source_hash == frontier["sha256"]["source"] == ablation["sha256"]["source"]
    evidence = dict(frontier["sha256"]["evidence"])
    for path, checksum in evidence.items():
        assert digest(a.root / path) == checksum
    for path in (frontier_path, ablation_path):
        evidence[str(path.relative_to(a.root))] = digest(path)
    models = {n: (a.carry_models / n).resolve() for n in ("baseline", "carry0", "carry1", "nomerge")}
    for n, path in models.items():
        assert digest(path) == frontier["sha256"]["models"][n]
    ablation_models = {n: (a.ablation_models / n).resolve() for n in CONFIGS}
    assert {n: digest(path) for n, path in ablation_models.items()} == ablation["sha256"]["models"]
    fresh = checked_score(a.root, "h1580", "h1581_equality_off_branch", evidence)
    grouped = {mode: [r["operand"] for r in fresh if r["mode"] == mode] for mode in ("rn", "rd", "ru")}
    outputs, ablated = {}, {}
    for n, model in models.items():
        outputs[n] = {key: value for mode, ops in grouped.items() for key, value in run(model, mode, ops).items()}
    for n, model in ablation_models.items():
        ablated[n] = {key: value for mode, ops in grouped.items() for key, value in run(model, mode, ops).items()}
    new_rows = []
    for row in fresh:
        key = row["mode"], row["operand"]
        assert row["baseline"] == outputs["baseline"][key]
        new_rows.append(dict(row, source="h1580", baseline_exact=row["baseline"] == row["hardware"],
                             allowed_carries=[c for c in (0, 1) if outputs[f"carry{c}"][key] == row["hardware"]],
                             outputs={n: v[key] for n, v in outputs.items()},
                             ablation_outputs={n: v[key] for n, v in ablated.items()}))
    interventions = []
    for stage in STAGES:
        for delta in (-1, 1):
            values = {key: value for mode, ops in grouped.items()
                      for key, value in run(models["baseline"], mode, ops, f"{stage.argument}:{delta}").items()}
            interventions.append({"stage": stage.name, "delta": delta,
                                  "repairs": [r["case_id"] for r in new_rows if not r["baseline_exact"]
                                              and values[r["mode"], r["operand"]] == r["hardware"]],
                                  "regressions": [r["case_id"] for r in new_rows if r["baseline_exact"]
                                                  and values[r["mode"], r["operand"]] != r["hardware"]]})
    direct = [dict(r, instruction="fcos") for r in frontier["rows"]] + new_rows
    union = list(direct)
    anchor_keys = {(r["mode"], r["operand"]): r for r in direct}
    for campaign, stem in (("h1570", "h1571_exact_preimage_transfer"), ("h1573", "h1574_signed_preimage_transfer")):
        for r in checked_score(a.root, campaign, stem, evidence):
            anchor = anchor_keys[r.get("anchor_mode", r["mode"]), r["anchor"]]
            assert r.get("anchor_hardware", r["transfer_prediction"]) == anchor["hardware"]
            assert r["transfer_verdict"] == "EXACT"
            for name in ("baseline", "carry0", "carry1"):
                assert replay(models[name], r["operand"], r["instruction"], r["mode"])[0] == r[name]
            allowed = [c for c in (0, 1) if r[f"carry{c}"] == r["hardware"]]
            assert "".join(map(str, allowed)) == r["allowed_carries"]
            union.append(dict(r, source=campaign, baseline_exact=r["baseline"] == r["hardware"], allowed_carries=allowed))
    fixed_rows = ablation["rows"] + new_rows
    fixed_counts = {name: dict(Counter("exact" if r["ablation_outputs"][name] == r["hardware"] else "miss"
                                      for r in fixed_rows)) for name in CONFIGS}
    report = {"experiment": "h1582_equality_frontier_reconciliation", "hardware_execution": "none_cached_only",
              "selector_claim": "none", "new_direct_observations": census(new_rows),
              "distinct_direct_residual_bank": census(direct), "external_union_including_aliases": census(union),
              "fixed_ablation_bank_rows": len(fixed_rows), "fixed_ablation_counts": fixed_counts,
              "new_misses_invariant_under_seven_ablations": [r["case_id"] for r in new_rows
                  if not r["baseline_exact"] and len(set(r["ablation_outputs"].values())) == 1],
              "new_rows": new_rows, "new_row_stage_interventions": interventions,
              "claim_boundary": "named_observed_bank_lower_bound_not_global_census_or_selector_proof",
              "sha256": {"script": digest(Path(__file__)), "source": source_hash, "evidence": evidence,
                         "carry_models": {n: digest(path) for n, path in models.items()},
                         "ablation_models": ablation["sha256"]["models"]}}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open("x") as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({k: report[k] for k in ("new_direct_observations", "distinct_direct_residual_bank",
                                             "external_union_including_aliases", "fixed_ablation_counts")}, sort_keys=True))


if __name__ == "__main__":
    main()
