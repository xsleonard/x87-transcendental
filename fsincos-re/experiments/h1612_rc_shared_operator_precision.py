#!/usr/bin/env python3
"""RC-only conventional policies with a shared finite width vector.

H1610's same-RD prefixes already reject 17,546 cases even with RC-only policy
selection. This tests all actual modes for the remaining 276 cases. Widths
do not vary with RC or operand. No hardware or unobserved status is used.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
import math
import random
from pathlib import Path

import h1609_rc_only_combined_semantics as split
import h1610_shared_operator_precision as sweep


fixed, graph, spec, V = sweep.fixed, sweep.graph, sweep.spec, sweep.V
N, K, MODES = sweep.N, sweep.K, split.rc.MODES
PARENT = "tmp/ledger33/current/h1610_shared_operator_precision"
LOCKS = {
    PARENT+"/report.json": "5b19899c92d5ba3b471ccfeea98eb4d8388ebeb266ccd0bdca449371cfdc5013",
    PARENT+"/precision_diagrams.jsonl.gz": "f24d0779926ece6896d2776f7cf5b6c88a8d6b7cadc423f7cfc37940ec34a0d2",
    "experiments/h1610_shared_operator_precision.py":
        "a9a3dbe97512db6e49d664ef089d1d00edf33fa57056faf0f55af6373a30bd7d",
    "experiments/h1609_rc_only_combined_semantics.py":
        "0669847f4a7616ccba8217d4317607d3fb45b8e9614920b6d1fc2bf9893d30df",
    "experiments/h1600_joint_rc_c1_faithful_graph.py":
        "6ce8f94f999a66746194ed06d35819df8cbae317d42ca3e116c7f8a770978198",
    "experiments/h1603_direct_control_semantics_bank.py":
        "87283b4b84b921314ce892507d156b563e5354009f13f58145720aadd53fc5d0",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def output_ok(row: dict, replay: dict) -> bool:
    return all(replay["outputs"][item["mode"]] == item["hardware"] for item in row["authenticated_observations"])


def core(mdd: fixed.MDD, roots: list[int], rows: list[dict], payload: str, widths: tuple, joint: bool) -> dict:
    if mdd.all_of(roots):
        return {"exists": False}
    singles = [i for i, value in enumerate(roots) if value == 0]
    pair = next(((i, j) for i, j in itertools.combinations(range(len(roots)), 2)
                 if mdd.conjunction(roots[i], roots[j]) == 0), None) if not singles else None
    if singles:
        selected = [singles[0]]
    elif pair is not None:
        selected = list(pair)
    else:
        selected = list(range(len(roots)))
        for i in tuple(selected):
            trial = [j for j in selected if j != i]
            if mdd.all_of(roots[j] for j in trial) == 0:
                selected = trial
    witnesses = []
    for removed in selected:
        remaining = [i for i in selected if i != removed]
        vector = mdd.witness(mdd.all_of(roots[i] for i in remaining))
        assert vector is not None
        replays = {}
        for i in selected:
            replay = sweep.forward(rows[i], payload, widths, vector)
            accepted = replay["accepted"] if joint else output_ok(rows[i], replay)
            assert accepted == (i in remaining)
            replays[rows[i]["operand"]] = replay
        witnesses.append({"removed_operand": rows[removed]["operand"],
                          "policies": [fixed.POLICIES[i] for i in vector], "replays": replays})
    return {"exists": True, "operands": [rows[i]["operand"] for i in selected],
            "cardinality_minimum_proved": bool(singles) or pair is not None, "deletion_minimal": True,
            "deletion_witnesses": witnesses}


def load_parent(root: Path, parent: dict, facts: dict) -> tuple[list, list]:
    by_id = {row["id"]: row for row in parent["hypotheses"]}
    by_operand = {row["operand"]: row for row in facts["rows"]}
    inherited, remaining, seen = [], [], set()
    with gzip.open(root/PARENT/"precision_diagrams.jsonl.gz", "rt") as stream:
        for line in stream:
            raw = json.loads(line)
            identifier = raw["id"]
            assert identifier not in seen
            seen.add(identifier)
            record = by_id[identifier]
            assert raw["operand_order"] == [row["operand"] for row in record["checked_prefix"]]
            assert raw["policies"] == list(fixed.POLICIES)
            assert raw["widths"] == list(sweep.operator_widths(record["multiply_precision"], record["horner_add_precision"], record["correction_precision"]))
            mdd = fixed.MDD(N, K)
            mapping = sweep.combined.import_nodes(mdd, raw["nodes"])
            common = [mdd.all_of(mapping[pair[kind]] for pair in raw["target_roots"]) for kind in (0, 1)]
            assert common == [mapping[r] for r in raw["final_roots"]] == [0, 0]
            if len(raw["operand_order"]) <= 2:
                # A policy chosen by architectural RC must be identical on
                # this entire already-rejected prefix: every tuple is RD.
                assert all({item["mode"] for item in by_operand[op]["authenticated_observations"]} == {"rd"}
                           for op in raw["operand_order"])
                inherited.append({"id": identifier, "widths": raw["widths"], "payload": record["payload"],
                                  "mode": "rd", "output_only_core_prefix": raw["operand_order"],
                                  "certificate": PARENT+"/precision_diagrams.jsonl.gz"})
            else:
                remaining.append((record, raw))
    assert seen == set(by_id)
    assert len(inherited) == 17546 and len(remaining) == 276
    return inherited, remaining


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output_dir.resolve()
    assert not output.exists(), "refusing existing output directory"
    evidence = dict(LOCKS)
    for relative, expected in LOCKS.items():
        assert digest(root/relative) == expected, relative
    parent = json.loads((root/PARENT/"report.json").read_text())
    for relative, expected in parent["sha256"]["evidence"].items():
        assert digest(root/relative) == expected, relative
        assert evidence.get(relative, expected) == expected
        evidence[relative] = expected
    facts = json.loads((root/fixed.REPORT).read_text())
    rows = facts["rows"]
    inherited, remaining = load_parent(root, parent, facts)
    tests = {"inverse_and_C1": split.joint_constraints.selftest(), "diagram": fixed.selftest()}
    print("validated inherited same-RD exclusions", len(inherited), "remaining", len(remaining), flush=True)
    output.mkdir(parents=True)
    raw_path = output/"rc_precision_diagrams.jsonl.gz"
    rng, results, target_survivors, control_survivors = random.Random(0x1612), [], [], []
    total_replays = 0
    wall = None
    with raw_path.open("xb") as raw_file, gzip.GzipFile(fileobj=raw_file, mode="wb", filename="", mtime=0) as raw_out:
        for case_index, (old_record, saved) in enumerate(remaining):
            identifier, payload, widths = old_record["id"], old_record["payload"], tuple(saved["widths"])
            mdd = fixed.MDD(N, K)
            imported = sweep.combined.import_nodes(mdd, saved["nodes"])
            old_roots = {op: [imported[r] for r in pair] for op, pair in zip(saved["operand_order"], saved["target_roots"])}
            mode_data = {mode: {"rows": [], "roots": []} for mode in MODES}
            compiled, rejoins, old_rejoins = [], 0, 0
            for original in rows:
                pairs = []
                for observation in original["authenticated_observations"]:
                    mode = observation["mode"]
                    row = split.only_mode(original, mode)
                    pair, stats = sweep.compile_operand(mdd, row, payload, widths)
                    mode_data[mode]["rows"].append(row)
                    mode_data[mode]["roots"].append(pair)
                    pairs.append(pair)
                    compiled.append({"operand": row["operand"], "mode": mode, "roots": pair, **stats})
                    vectors = [tuple(rng.randrange(K) for _ in range(N)) for _ in range(8)]
                    vectors.extend(vector for vector in (mdd.witness(pair[0]), mdd.witness(pair[1])) if vector is not None)
                    for vector in vectors:
                        direct = sweep.forward(row, payload, widths, vector)
                        assert mdd.evaluate(pair[0], vector) == output_ok(row, direct)
                        assert mdd.evaluate(pair[1], vector) == direct["accepted"]
                        total_replays += 1
                rejoined = [mdd.all_of(pair[kind] for pair in pairs) for kind in (0, 1)]
                # Verify full canonical functions against both a full-bank
                # joint compilation and the pinned H1610 prefix where saved.
                joint_pair, _ = sweep.compile_operand(mdd, original, payload, widths)
                assert rejoined == list(joint_pair)
                rejoins += 2
                if original["operand"] in old_roots:
                    assert rejoined == old_roots[original["operand"]]
                    old_rejoins += 2
            modes, mode_common = {}, {}
            for mode, data in mode_data.items():
                common = [mdd.all_of(pair[kind] for pair in data["roots"]) for kind in (0, 1)]
                mode_common[mode] = common
                certificates = [core(mdd, [pair[kind] for pair in data["roots"]], data["rows"], payload, widths, bool(kind))
                                for kind in (0, 1)]
                vector = mdd.witness(common[1])
                witness = None
                if vector is not None:
                    replays = {row["operand"]: sweep.forward(row, payload, widths, vector) for row in data["rows"]}
                    assert all(replay["accepted"] for replay in replays.values())
                    witness = {"policies": [fixed.POLICIES[i] for i in vector], "replays": replays}
                modes[mode] = {"actual_rows": len(data["rows"]),
                    "actual_C1_constraints": sum(len(row["actual_C1_constraints"]) for row in data["rows"]),
                    "output_only_assignments": mdd.count(common[0]), "joint_assignments": mdd.count(common[1]),
                    "output_only_core": certificates[0], "joint_core": certificates[1], "witness": witness}
            output_maps = math.prod(item["output_only_assignments"] for item in modes.values())
            joint_maps = math.prod(item["joint_assignments"] for item in modes.values())
            record = {"id": identifier, "multiply_precision": old_record["multiply_precision"],
                "horner_add_precision": old_record["horner_add_precision"], "correction_precision": old_record["correction_precision"],
                "payload": payload, "modes": modes, "output_only_RC_maps": output_maps, "joint_RC_maps": joint_maps,
                "full_joint_function_rejoins": rejoins, "pinned_H1610_function_rejoins": old_rejoins,
                "status": "UNSAT_RC_ONLY_POLICIES" if joint_maps == 0 else "SAT_TARGETS_REQUIRES_CONTROLS"}
            control_checks = []
            if joint_maps:
                target_survivors.append(identifier)
                if payload == "frozen_numeric":
                    record["control_status"] = "NEEDS_AUTHENTICATED_ORIGINAL_NUMERIC_PAYLOAD_TRACES_NO_FABRICATION"
                else:
                    if wall is None:
                        import h1603_direct_control_semantics_bank as controls
                        wall = controls.load_controls(root)
                        evidence.update(wall.evidence)
                    for control in wall.controls:
                        original = sweep.control_row(control)
                        checked_modes = {}
                        for mode in MODES:
                            row = split.only_mode(original, mode)
                            pair, _ = sweep.compile_operand(mdd, row, payload, widths)
                            mode_common[mode] = [mdd.conjunction(mode_common[mode][kind], pair[kind]) for kind in (0, 1)]
                            checked_modes[mode] = pair
                        control_checks.append({"operand": control.operand, "roots": checked_modes,
                            "joint_assignments_by_mode": {mode: mdd.count(pair[1]) for mode, pair in mode_common.items()}})
                        if any(pair[1] == 0 for pair in mode_common.values()):
                            break
                    survived = all(pair[1] != 0 for pair in mode_common.values())
                    record["control_status"] = "PASS_CACHED_BANK_ONLY" if survived else "FALSIFIED_BY_CACHED_CONTROLS"
                    record["control_prefix_operands"] = len(control_checks)
                    if survived:
                        control_survivors.append(identifier)
                        record["control_surviving_map"] = {mode: [fixed.POLICIES[i] for i in mdd.witness(pair[1])]
                                                           for mode, pair in mode_common.items()}
            else:
                record["control_status"] = "NOT_RUN_NO_COMPLETE_TARGET_MAP"
            results.append(record)
            raw_out.write((json.dumps({"id": identifier, "widths": widths, "policies": fixed.POLICIES,
                "nodes": mdd.nodes, "mode_order": MODES, "compiled_observations": compiled,
                "control_checks": control_checks, "final_roots_by_mode": mode_common}, separators=(",", ":"))+"\n").encode())
            if (case_index+1) % 8 == 0 or joint_maps:
                print(case_index+1, "of", len(remaining), identifier, record["status"],
                      {mode: item["joint_assignments"] for mode, item in modes.items()}, flush=True)
    # If a single mode rejects every possible width vector, giving each RC
    # its own width vector cannot help: that mode has no available choice.
    # This consequence uses the inherited per-case RD certificates as well
    # as the newly compiled cases, rather than extrapolating other modes.
    impossible_for_every_width = [mode for mode in MODES
        if all(item["mode"] == mode for item in inherited)
        and all(item["modes"][mode]["output_only_assignments"] == 0 for item in results)]
    report = {"experiment": "h1612_rc_shared_operator_precision", "hardware_or_C_execution": "none",
        "selector_promotion": "none", "widths_fixed_across_RC_and_inputs": True,
        "inherited_same_RD_exclusions": inherited, "newly_tested_precision_payload_cases": len(results),
        "full_width_payload_cases_covered": len(inherited)+len(results), "observed_operands": len(rows),
        "actual_mode_rows": 64, "actual_C1_constraints": 27, "named_policy_RC_maps_per_width_case": (K**N)**len(MODES),
        "selftest": tests, "direct_policy_replays": total_replays, "results": results,
        "target_survivors": target_survivors, "cached_control_survivors": control_survivors,
        "modes_impossible_for_every_width_on_outputs_alone": impossible_for_every_width,
        "derived_RC_dependent_width_exclusion": {
            "proved": bool(impossible_for_every_width),
            "reason": "each listed mode has zero common policies for every allowed width vector; no RC-to-width choice can serve that mode",
            "scope": "widths may depend on RC but still use exactly H1610's shared M/A/correction class structure and bounded precision set"},
        "scope": "H1610 M/A/correction width vector fixed across modes and operands; every operation policy independently chosen by architectural RC only; original graph/constants, final RC64, absent/frozen original numeric payload",
        "claim_boundary": "no operand-dependent width/policy selection, arbitrary per-cut precisions, bypass/changed-width combinations, new graph/routing/nonstandard history or regenerated payload; RC-dependent width exclusion only when the explicitly derived all-width impossible-mode certificate holds; not global closed-form impossibility",
        "sha256": {"script": digest(Path(__file__)), "evidence": evidence, "rc_precision_diagrams": digest(raw_path)}}
    with (output/"report.json").open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"tested": len(results), "inherited": len(inherited),
                      "target_survivors": target_survivors, "control_survivors": control_survivors}, sort_keys=True))


if __name__ == "__main__":
    main()
