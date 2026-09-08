#!/usr/bin/env python3
"""Counterexample-guided exact regression gate for H1614's first target fit.

Searches only a shared thirteen-policy vector at fixed X67/Y64-CHOP ports,
orientation zero and absent payload. Old high-q captures precede the cached
H1603 wall. A rejected witness adds the complete observed-row constraint;
no input predicate or new hardware label is invented. A surviving witness
is only cached-bank feasibility, never a silicon solution or fresh validation.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

import h1614_asymmetric_multiplier_ports as model
import h1603_direct_control_semantics_bank as controls


fixed, graph, spec, V = model.fixed, model.graph, model.spec, model.V
LOCKS = {
    "experiments/h1614_asymmetric_multiplier_ports.py":
        "fa8bd43d0d6f5b0a4a7c6cb71f70ad6b99672c99f67b3ed88a9dbef994e5f52a",
    "experiments/h1603_direct_control_semantics_bank.py":
        "87283b4b84b921314ce892507d156b563e5354009f13f58145720aadd53fc5d0",
    fixed.REPORT: fixed.REPORT_SHA,
}
OLD_LABELS = (
    ("h1315_tail_stratified_blind_report_labels.tsv", "7a862e2d407122b9adbc83e636c1ae730009663e30b43239699913cb7f04140b"),
    ("h1326_complete_highq_separator_blind_report_labels.tsv", "92259f7187bc56ff037e93ec7cd98a4f95e1596dea42d9bab2aee071494cdf1a"),
    ("h1352_power_mux_adversarial_score_labels.tsv", "a5a1576d3aaf40ab6e7f5c658d29152e17ef9dbdd4db140eb1d331ee36a0dcc4"),
)
NATURAL = tuple(model.POLICIES.index(node[5]) for node in graph.NODES)


def observed_row(operand: str, observations: list[dict]) -> dict:
    interval = fixed.rc.inverse(observations[0]["hardware"], observations[0]["mode"])
    for row in observations[1:]:
        interval = interval.intersect(fixed.rc.inverse(row["hardware"], row["mode"]))
    assert interval.nonempty()
    return {"operand": operand, "authenticated_observations": observations, "actual_C1_constraints": [],
            "joint_RC_inverse": interval.json(), "joint_RC_C1_inverse": interval.json(),
            "variants": {"omitted": {"frozen_payload_signed": V(0, 0).record()}}}


def load_old(root: Path, evidence: dict) -> list[dict]:
    grouped, tuples = defaultdict(list), set()
    score_path = "tmp/ledger33/current/h1358_x67_y64_direct_score_pc.txt"
    evidence[score_path] = model.LOCKS[score_path]
    assert model.digest(root/score_path) == evidence[score_path]
    pins = dict(line.split("\t", 1) for line in (root/score_path).read_text().splitlines() if "\t" in line)
    for index, (name, expected) in enumerate(OLD_LABELS):
        relative = "tmp/ledger33/current/"+name
        assert pins[f"direct_labels_sha256.{index}"] == expected
        assert model.digest(root/relative) == expected
        evidence[relative] = expected
        with (root/relative).open() as source:
            for line, row in enumerate(csv.DictReader(source, delimiter="\t"), 2):
                operand, mode, hardware = row["op"].lower(), row["mode"].lower(), row["hardware"].lower()
                assert controls.direct_positive(operand) and mode in ("rn", "rd", "ru")
                assert (operand, mode) not in tuples
                tuples.add((operand, mode))
                grouped[operand].append({"instruction": "fcos", "mode": mode, "hardware": hardware,
                                         "source": relative, "source_line_one_based": line})
    assert len(tuples) == 370 and len(grouped) == 261
    return [observed_row(operand, sorted(rows, key=lambda row: spec.MODES.index(row["mode"])))
            for operand, rows in sorted(grouped.items())]


def fast_score(row: dict, vector: tuple[int, ...]) -> dict:
    state = graph.initial(row["operand"])
    for node, choice in zip(graph.NODES, vector):
        state[node[0]] = model.base.selected(model.operation(state, node, V(0, 0), 0, "chop"), node[4], choice)
    correction = state["correction"]
    outputs = {obs["mode"]: spec.encode_external(spec.add(V(1, 0), correction, 64, obs["mode"]))
               for obs in row["authenticated_observations"]}
    misses = [obs["mode"] for obs in row["authenticated_observations"] if outputs[obs["mode"]] != obs["hardware"]]
    return {"outputs": outputs, "mismatched_modes": misses, "prevalue": str(spec.exact_add(V(1, 0), correction).fraction())}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output_dir.resolve()
    assert not output.exists(), "refusing existing output directory"
    evidence = {**model.LOCKS, **LOCKS}
    for relative, expected in evidence.items():
        assert model.digest(root/relative) == expected, relative
    target_report = json.loads((root/fixed.REPORT).read_text())
    targets = target_report["rows"]
    # Authenticate the inherited numerical/evidence chain without executing
    # the long H1614 all-orientation experiment again.
    prior = json.loads((root/model.PARENT/"report.json").read_text())
    for relative, expected in prior["sha256"]["evidence"].items():
        assert model.digest(root/relative) == expected, relative
        assert evidence.get(relative, expected) == expected
        evidence[relative] = expected
    tests = model.selftest()
    mdd, common, target_roots = fixed.MDD(model.N, model.K), 1, []
    for row in targets:
        pair, _ = model.compile_operand(mdd, row, "omitted", 0, "chop")
        common = mdd.conjunction(common, pair[1])
        target_roots.append(pair)
    initial_root, initial_count = common, mdd.count(common)
    assert initial_count > 0
    initial_witness = mdd.witness(common)
    target_vectors = {"natural_original_output_policies": NATURAL, "first_lexicographic_target_witness": initial_witness}
    target_replays = {}
    for name, vector in target_vectors.items():
        replays = {row["operand"]: model.forward(row, "omitted", vector, 0, "chop") for row in targets}
        assert mdd.evaluate(common, vector) == all(record["RC_C1_matches"] for record in replays.values())
        target_replays[name] = {"policies": [model.POLICIES[i] for i in vector], "replays": replays,
                                "target_joint_matches": sum(record["RC_C1_matches"] for record in replays.values())}
    old = load_old(root, evidence)
    bank = controls.load_controls(root)
    evidence.update(bank.evidence)
    wall = [model.routing.make_control_row(control) for control in bank.controls]
    # Preserve distinct source rows, but verify repeated actual tuples agree.
    seen = {}
    for row in [*targets, *old, *wall]:
        for observed in row["authenticated_observations"]:
            key = row["operand"], observed["mode"]
            assert seen.setdefault(key, observed["hardware"]) == observed["hardware"]
    output.mkdir(parents=True)
    raw_path = output/"witness_regression_replays.jsonl.gz"
    rounds, counterexample_roots, checked = [], [], Counter()
    outcome, final_witness = "UNSAT_CACHED_REGRESSION_BANK", None
    with raw_path.open("xb") as raw_file, gzip.GzipFile(fileobj=raw_file, mode="wb", filename="", mtime=0) as raw:
        while common:
            vector = NATURAL if not rounds and mdd.evaluate(common, NATURAL) else mdd.witness(common)
            before_count = mdd.count(common)
            failed, per_round = None, Counter()
            for origin, rows in (("old_highq", old), ("H1603_controls", wall)):
                for row in rows:
                    numerical = fast_score(row, vector)
                    per_round[origin+".operands"] += 1
                    per_round[origin+".mode_rows"] += len(row["authenticated_observations"])
                    checked[origin+".operands"] += 1
                    checked[origin+".mode_rows"] += len(row["authenticated_observations"])
                    raw.write((json.dumps({"round": len(rounds), "origin": origin, "operand": row["operand"],
                        "hardware": {obs["mode"]: obs["hardware"] for obs in row["authenticated_observations"]},
                        **numerical}, separators=(",", ":"))+"\n").encode())
                    if numerical["mismatched_modes"]:
                        pair, _ = model.compile_operand(mdd, row, "omitted", 0, "chop")
                        assert not mdd.evaluate(pair[0], vector)
                        counterexample_roots.append(pair)
                        common = mdd.conjunction(common, pair[0])
                        assert mdd.count(common) < before_count
                        failed = {"origin": origin, "row": row, "replay": numerical, "roots": pair}
                        break
                if failed:
                    break
            rounds.append({"policies": [model.POLICIES[i] for i in vector], "assignments_before": before_count,
                           "assignments_after": mdd.count(common), "checks": dict(per_round), "counterexample": failed})
            print("round", len(rounds), before_count, mdd.count(common), "PASS" if failed is None else failed["origin"]+":"+failed["row"]["operand"], flush=True)
            if failed is None:
                outcome, final_witness = "SAT_CACHED_BANK_ONLY_REQUIRES_WIDER_VALIDATION", vector
                break
    diagrams = {"nodes": mdd.nodes, "target_order": [row["operand"] for row in targets],
                "target_roots": target_roots, "initial_joint_root": initial_root,
                "counterexample_roots": counterexample_roots, "final_root": common}
    with (output/"policy_certificate.json").open("x") as stream:
        json.dump(diagrams, stream, separators=(",", ":"))
        stream.write("\n")
    report = {"experiment": "h1615_asymmetric_port_regression_gate", "status": outcome,
        "hypothesis": "orientation0_Xchop67_Ychop64_all_multipliers_original_widths_common_sixchoice_outputs_absent_payload",
        "target_operands": len(targets), "actual_target_modes": sum(len(row["authenticated_observations"]) for row in targets),
        "actual_target_C1": sum(len(row["actual_C1_constraints"]) for row in targets),
        "initial_target_assignments": initial_count, "target_vector_checks": target_replays,
        "old_highq_operands": len(old), "old_highq_mode_rows": 370,
        "H1603_control_operands": len(wall), "H1603_control_mode_rows": len(wall)*4,
        "unique_target_and_regression_tuples": len(seen), "rounds": rounds, "performed_replay_counts": dict(checked),
        "remaining_unrefuted_assignments_not_all_certified": mdd.count(common),
        "final_cached_bank_witness": None if final_witness is None else [model.POLICIES[i] for i in final_witness],
        "selftest": tests, "hardware_execution": "none", "selector_promotion": "none",
        "claim_boundary": "finite cached constraints only; historical model-selected H1603 wall and previously opened high-q banks are not fresh blind validation; no other port orientations or Y policies excluded; C1 unknown outside actual targets",
        "sha256": {"script": model.digest(Path(__file__)), "evidence": evidence,
                   "witness_replays": model.digest(raw_path), "policy_certificate": model.digest(output/"policy_certificate.json")}}
    with (output/"report.json").open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": outcome, "rounds": len(rounds), "initial_target_assignments": initial_count,
                      "remaining": mdd.count(common)}, sort_keys=True))


if __name__ == "__main__":
    main()
