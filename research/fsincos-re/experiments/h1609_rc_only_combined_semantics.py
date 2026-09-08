#!/usr/bin/env python3
"""Allow arbitrary architectural-RC-only choice of H1608's semantic vector.

Split only actually observed modes. Each mode has its own independent common
six-choice vector across inputs; no inferred mode/status label is supplied.
Rejoining each operand's mode diagrams must recover H1608's complete functions.
This uses H1608's numerical compiler; it is not an independent solver proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path

import h1600_joint_rc_c1_faithful_graph as joint_constraints
import h1608_combined_policy_bypass_solve as combined


fixed, graph, rc = combined.fixed, combined.graph, joint_constraints.rc
N, K = combined.N, combined.K
H1608 = "tmp/ledger33/current/h1608_combined_policy_bypass_solve"
LOCKS = {
    H1608+"/report.json": "842bd5ff9c73c8e8e3dd4dedeb5874df86f01501c8d45d899554e80857cb4ec4",
    "experiments/h1608_combined_policy_bypass_solve.py":
        "498746dcc91a35b326785af800cbc864b4ad5f53e4d801d89f3136c474e829f6",
    "experiments/h1600_joint_rc_c1_faithful_graph.py":
        "6ce8f94f999a66746194ed06d35819df8cbae317d42ca3e116c7f8a770978198",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def only_mode(row: dict, mode: str) -> dict:
    observations = [r for r in row["authenticated_observations"] if r["mode"] == mode]
    assert len(observations) == 1
    statuses = [r for r in row["actual_C1_constraints"] if r["mode"] == mode]
    current = rc.inverse(observations[0]["hardware"], mode)
    refined = current
    for status in statuses:
        assert status["hardware"] == observations[0]["hardware"]
        refined = joint_constraints.refine_c1(refined, status["hardware"], status["c1"])
    assert current.nonempty() and refined.nonempty()
    return {**row, "authenticated_observations": observations, "actual_C1_constraints": statuses,
            "joint_RC_inverse": current.json(), "joint_RC_C1_inverse": refined.json()}


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
    parent = json.loads((root/H1608/"report.json").read_text())
    for relative, expected in parent["sha256"]["evidence"].items():
        assert digest(root/relative) == expected, relative
        assert evidence.get(relative, expected) == expected
        evidence[relative] = expected
    facts = json.loads((root/fixed.REPORT).read_text())
    rows = facts["rows"]
    tests = joint_constraints.selftest()
    output.mkdir(parents=True)
    rng, results = random.Random(0x1609), {}
    for payload in ("omitted", "frozen_numeric"):
        mdd = fixed.MDD(N, K)
        relative = H1608+f"/{payload}_diagram.json"
        expected = parent["results"][payload]["diagram_sha256"]
        assert digest(root/relative) == expected
        evidence[relative] = expected
        saved = json.loads((root/relative).read_text())
        assert saved["variables"] == list(graph.NAMES) and saved["choices"] == list(combined.CHOICES)
        imported = combined.import_nodes(mdd, saved["nodes"])
        by_mode = {mode: {"rows": [], "roots": [], "details": []} for mode in rc.MODES}
        replays = 0
        for index, original in enumerate(rows):
            operand_roots = []
            for observed in original["authenticated_observations"]:
                mode = observed["mode"]
                row = only_mode(original, mode)
                pair, detail = combined.compile_operand(mdd, row, payload)
                operand_roots.append(pair)
                by_mode[mode]["rows"].append(row)
                by_mode[mode]["roots"].append(pair)
                vectors = [tuple(rng.randrange(K) for _ in range(N)) for _ in range(32)]
                vectors.extend(vector for vector in (mdd.witness(pair[0]), mdd.witness(pair[1])) if vector is not None)
                for vector in vectors:
                    direct = combined.forward(row, payload, vector)
                    assert mdd.evaluate(pair[0], vector) == direct["RC_matches"]
                    assert mdd.evaluate(pair[1], vector) == direct["RC_C1_matches"]
                    replays += 1
                detail.update(operand=row["operand"], mode=mode, roots=pair,
                              authenticated_observation=row["authenticated_observations"][0],
                              actual_C1_constraints=row["actual_C1_constraints"],
                              output_inverse=row["joint_RC_inverse"], output_C1_inverse=row["joint_RC_C1_inverse"])
                by_mode[mode]["details"].append(detail)
            # Conjoining actual modes with the SAME vector is precisely
            # the old RC-independent per-operand problem. Equality here is
            # full canonical-function equality, not a counts-only check.
            for kind in (0, 1):
                assert mdd.all_of(pair[kind] for pair in operand_roots) == imported[saved["operand_roots"][index][kind]]
            print(payload, original["operand"], "mode functions rejoin exactly", flush=True)
        mode_results, common_by_mode = {}, {}
        for mode in rc.MODES:
            data = by_mode[mode]
            common = [mdd.all_of(pair[kind] for pair in data["roots"]) for kind in (0, 1)]
            common_by_mode[mode] = common
            counts = [mdd.count(root_id) for root_id in common]
            cores = [combined.core_certificate(mdd, [pair[kind] for pair in data["roots"]],
                     data["rows"], payload, field)
                     for kind, field in enumerate(("RC_matches", "RC_C1_matches"))]
            vector = mdd.witness(common[1])
            witness_replays = None
            if vector is not None:
                witness_replays = {row["operand"]: combined.forward(row, payload, vector) for row in data["rows"]}
                assert all(r["RC_C1_matches"] for r in witness_replays.values())
            mode_results[mode] = {"observed_operands": len(data["rows"]),
                "actual_C1_constraints": sum(len(row["actual_C1_constraints"]) for row in data["rows"]),
                "output_only_common_assignments": counts[0], "output_and_C1_common_assignments": counts[1],
                "output_only_core": cores[0], "output_and_C1_core": cores[1],
                "witness_choices": None if vector is None else [combined.CHOICES[i] for i in vector],
                "witness_replays": witness_replays, "rows": data["details"]}
            print(payload, mode, "shared output / output+C1 counts", *counts, flush=True)
        # Four independently chosen semantic vectors describe an arbitrary
        # RC-only policy map. A single zero mode factor rejects the full map.
        output_maps = math.prod(item["output_only_common_assignments"] for item in mode_results.values())
        joint_maps = math.prod(item["output_and_C1_common_assignments"] for item in mode_results.values())
        diagram_path = output/f"{payload}_diagram.json"
        with diagram_path.open("x") as stream:
            json.dump({"choices": combined.CHOICES, "variables": graph.NAMES, "nodes": mdd.nodes,
                       "mode_operand_roots": {mode: item["roots"] for mode, item in by_mode.items()},
                       "common_roots_by_mode": common_by_mode}, stream, separators=(",", ":"))
            stream.write("\n")
        results[payload] = {"modes": mode_results, "output_only_RC_policy_maps": output_maps,
            "output_and_C1_RC_policy_maps": joint_maps,
            "status": "UNSAT_RC_ONLY_COMBINED_FAMILY" if joint_maps == 0 else "SAT_REQUIRES_CONTROLS",
            "full_H1608_function_rejoins": 2*len(rows), "straight_line_graph_replays": replays,
            "diagram_nodes": len(mdd.nodes), "diagram_sha256": digest(diagram_path),
            "control_wall": "NOT_RUN_NO_RC_ONLY_COMMON_MAP" if joint_maps == 0 else "PENDING_NOT_A_VALIDATED_SOLUTION"}
    report = {"experiment": "h1609_rc_only_combined_semantics", "C_or_hardware_execution": "none",
        "observed_operands": len(rows), "actual_RC_rows": 64, "actual_C1_constraints": 27,
        "named_RC_maps_per_payload": (K**N)**len(rc.MODES), "choices": combined.CHOICES,
        "selftest": tests, "results": results,
        "scope": "one independent common H1608 six-choice vector per architectural RC, actual modes/status only, fixed graph/original widths or exact to all consumers, final RC64, omitted or frozen original numeric payload",
        "independence_boundary": "uses H1608 numerical compiler/MDD and H1600 mode/status inverses; exact function rejoin and direct execution cross-checks, not an independently implemented compiler",
        "claim_boundary": "does not exclude operand-dependent state, other widths/graphs, edge-specific forwarding, altered payload generation, nonstandard internal rules, or a general closed-form solution",
        "sha256": {"script": digest(Path(__file__)), "evidence": evidence}}
    with (output/"report.json").open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")


if __name__ == "__main__":
    main()
