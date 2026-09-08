#!/usr/bin/env python3
"""Build a source-defined adversarial bank for the current R1263 equality gate.

The upstream product window is chosen without labels.  Both current-source
forced b1 endpoints must differ architecturally, the actual comparator must
be exactly equal, and an independent P5 tree replay must reproduce the
incumbent carry/kill decision.  This emits software evidence only.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
from collections import Counter
from pathlib import Path

from h1400_causal_stage_localization import digest, run
from h1210_stagea_residual_reframe import parse_dump, run as dump_run
from h1400_p5_representation_audit import tree_variants
from h1479_r1475_topology_isomorphism import trace_tree


MODES = ("rn", "rd", "ru")
SEED = "0x1576a4093822299f"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--scanner", required=True, type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--max-externals", type=int, default=50000)
    parser.add_argument("--seed", default=SEED)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise SystemExit(f"refusing to overwrite {args.output_dir}")
    source = args.root / "src/fsincos_skylake.c"
    prior_path = args.root / "tmp/ledger33/current/h1575_current_rule_ablation.json"
    prior = json.loads(prior_path.read_text())
    assert digest(source) == prior["sha256"]["source"]
    assert digest(args.baseline) == prior["sha256"]["models"]["baseline"]
    test = subprocess.run([str(args.scanner.resolve()), "--selftest"], capture_output=True, text=True, check=True)
    assert test.stdout == "SELFTEST: ok\n" and not test.stderr
    args.output_dir.mkdir(parents=True)
    command = [str(args.scanner.resolve()), "1000000", args.seed, str(args.max_externals)]
    scan = subprocess.run(command, capture_output=True, text=True, check=True)
    with (args.output_dir / "raw_proxy_preimages.tsv").open("x") as target:
        target.write(scan.stdout)
    with (args.output_dir / "scanner_summary.txt").open("x") as target:
        target.write(scan.stderr)
    raw = list(csv.DictReader(io.StringIO(scan.stdout), delimiter="\t"))
    unique = {}
    for row in raw:
        sig = int(row["operand"].split()[1], 16)
        square = sig*sig >> 61
        s4 = int(row["s4"])
        fourth = int(row["fourth"], 16)
        positive = int(row["positive_proxy"], 16)
        shift = int(row["rsh"])
        product = fourth*positive
        assert square*square >> s4 == fourth
        assert (square*square).bit_length()-67 == s4
        assert product.bit_length()-67 == shift
        residue = product % (1<<shift)
        assert residue == int(row["rdisc_proxy"], 16)
        block = 1 << (shift-16)
        assert 3*residue-(2*residue % block)-(residue % block) == 1<<shift
        assert 3*residue-(3*residue % block) == 1<<shift
        unique.setdefault(row["operand"], row)
    operands = list(unique)
    print(f"scanner raw={len(raw)} unique={len(operands)}", flush=True)
    models = {"baseline": args.baseline.resolve()}
    for name, taps in (("strict", 1), ("inclusive", 2)):
        path = (args.output_dir / name).resolve()
        subprocess.run(["cc", "-O2", "-std=c11", "-DG_ROUND84=0", f"-DG_R99TAPS={taps}",
                        str(source.resolve()), "-lm", "-o", str(path)], capture_output=True, text=True, check=True)
        models[name] = path
    outputs = {name: {} for name in models}
    for name, model in models.items():
        for mode in MODES:
            outputs[name].update(run(model, mode, operands))
        print(f"model {name} complete", flush=True)
    visible = {op for op in operands if any(outputs["strict"][mode,op] != outputs["inclusive"][mode,op]
                                             for mode in MODES)}
    _, stderr = dump_run(models["baseline"], "rn", sorted(visible), dump=True)
    traces = {r["op"]: r for r in parse_dump(stderr, sorted(visible))}
    config = next(c for n, _, c in tree_variants() if n == "patent")
    candidates = []
    rejects = Counter()
    for operand in sorted(visible):
        row = traces[operand]
        if "rd3" not in row or int(row["rd3"],16) != 1<<int(row["rsh"]):
            rejects["not_actual_b1_equality"] += 1
            continue
        if int(row["b2"]) != 0 or int(row["side"]) != 1:
            rejects["wrong_actual_side_or_b2"] += 1
            continue
        if int(row["tc_rf_sig"],16) != int(unique[operand]["positive_proxy"],16):
            rejects["current_positive_differs_from_proxy"] += 1
            continue
        nodes, _, final = trace_tree(row, config)
        shift = int(row["rsh"])
        held = (nodes["l2_2"][1] >> (shift+4)) & 1
        kill = 1 ^ (((final[0] | final[1]) >> (shift+15)) & 1)
        gate = held & kill
        assert int(row["b1"]) == 1-gate
        selected = "strict" if gate else "inclusive"
        mode_rows = []
        for mode in MODES:
            key = mode,operand
            assert outputs["baseline"][key] == outputs[selected][key]
            if outputs["strict"][key] != outputs["inclusive"][key]:
                mode_rows.append({"mode": mode, "baseline": outputs["baseline"][key],
                                  "strict": outputs["strict"][key], "inclusive": outputs["inclusive"][key]})
        assert mode_rows
        candidates.append({"operand": operand, "s4": int(row["s4"]), "rsh": shift,
                           "theta": int(row["theta"]), "low3": int(row["low3"]), "branch": row["branch"],
                           "held_carry": held, "final_kill": kill, "r1263_gate": gate,
                           "prediction": selected, "modes": mode_rows,
                           "scanner_row": unique[operand],
                           "trace": {k: row[k] for k in ("rd3", "tc_f4_sig", "tc_rf_sig", "b1", "b2")}})
    counts = {"raw_preimages": len(raw), "unique_preimages": len(operands),
              "tap_endpoint_visible_operands": len(visible), "actual_equality_candidates": len(candidates),
              "rejected": dict(rejects),
              "gate_counts": dict(Counter(str(c["r1263_gate"]) for c in candidates)),
              "s4_gate_counts": dict(Counter(f"{c['s4']}/{c['r1263_gate']}" for c in candidates))}
    report = {"experiment": "h1577_equality_adversarial_bank", "capture_state": "SOFTWARE_ONLY_NOT_FROZEN",
              "hardware_execution": "none", "new_hardware_labels": "none", "selector_claim": "none",
              "generator_arguments": command[1:], "counts": counts, "candidates": candidates,
              "claim_boundary": "sampled_proxy_plateaus_with_exact_current_source_endpoint_replay_not_domain_exhaustion",
              "sha256": {"source": digest(source), "script": digest(Path(__file__)), "scanner": digest(args.scanner),
                         "scanner_source": digest(args.root / "experiments/h1576_equality_plateau_lattice.c"),
                         "raw": digest(args.output_dir / "raw_proxy_preimages.tsv"),
                         "summary": digest(args.output_dir / "scanner_summary.txt"),
                         "models": {n: digest(p) for n,p in models.items()}, "ablation": digest(prior_path)}}
    with (args.output_dir / "bank.json").open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps(counts, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
