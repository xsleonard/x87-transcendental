#!/usr/bin/env python3
"""Verify saved H1613 route coverage, two-RD cores and singleton witnesses.

This is a certificate audit, not an independent arithmetic-family search.
It adds the explicit implication for arbitrary RC-only route/policy choices.
No capture, input-dependent selector, changed widths or physical wiring claim.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import h1613_split_power_forwarding as solver


PARENT = "tmp/ledger33/current/h1613_split_power_forwarding"
REPORT_SHA = "a36ea9969e0c79bea9a613162b732c0b2913c792e20f24d75b48a098d333b95c"
OPERANDS = ("3ffc e73ffffd2c52df71", "3ffc fcbfffffcee1bd36")
HARDWARE = ("3ffe:f97ff2968a37b8b1", "3ffe:f83dc8dae4171d48")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output_dir.resolve()
    assert not output.exists(), "refusing existing output directory"
    report_path = root/PARENT/"report.json"
    assert solver.digest(report_path) == REPORT_SHA
    report = json.loads(report_path.read_text())
    evidence = {PARENT+"/report.json": REPORT_SHA, **report["sha256"]["evidence"]}
    evidence["experiments/h1613_split_power_forwarding.py"] = report["sha256"]["script"]
    evidence[PARENT+"/routing_diagrams.jsonl.gz"] = report["sha256"]["routing_diagrams"]
    for relative, expected in evidence.items():
        assert solver.digest(root/relative) == expected, relative
    assert report["routes"] == [list(route) for route in solver.ROUTES]
    assert report["routing_programs_per_payload"] == 128
    assert report["policy_vectors_per_routing_program"] == 6**13
    assert report["named_programs_per_payload"] == 128*6**13
    assert report["all_routes_excluded_using_only_RD"] is True
    facts = json.loads((root/solver.fixed.REPORT).read_text())
    rows = {row["operand"]: row for row in facts["rows"]}
    for operand, hardware in zip(OPERANDS, HARDWARE):
        observed = rows[operand]["authenticated_observations"]
        assert len(observed) == 1
        assert observed[0]["mode"] == "rd" and observed[0]["instruction"] == "fcos"
        assert observed[0]["hardware"] == hardware
    expected_ids = {f"route{mask:03d}:{payload}"
                    for mask in range(128) for payload in ("omitted", "frozen_numeric")}
    summaries = {case["id"]: case for case in report["hypotheses"]}
    assert len(summaries) == len(report["hypotheses"]) == 256
    assert set(summaries) == expected_ids
    seen, verified = set(), []
    canonical_conjunction_checks = rational_stage_checks = 0
    with gzip.open(root/PARENT/"routing_diagrams.jsonl.gz", "rt") as stream:
        for line in stream:
            saved = json.loads(line)
            identifier = saved["id"]
            assert identifier in expected_ids and identifier not in seen
            seen.add(identifier)
            summary = summaries[identifier]
            mask, payload = summary["routing_mask"], summary["payload"]
            assert identifier == f"route{mask:03d}:{payload}"
            assert saved["routing_mask"] == mask
            assert saved["routes"] == report["routes"]
            assert saved["policies"] == list(solver.POLICIES)
            assert saved["routed_graph"] == [list(node) for node in solver.routed_nodes(mask)]
            assert saved["operand_order"] == list(OPERANDS)
            assert saved["control_checks"] == []
            assert len(saved["operand_roots"]) == len(summary["checked_prefix"]) == 2
            mdd = solver.fixed.MDD(solver.N, solver.K)
            mapping = solver.base.import_nodes(mdd, saved["nodes"])
            pairs = [[mapping[node] for node in pair] for pair in saved["operand_roots"]]
            common = [1, 1]
            witnesses = []
            for operand, pair, prefix in zip(OPERANDS, pairs, summary["checked_prefix"]):
                assert prefix["operand"] == operand
                common = [mdd.conjunction(common[kind], pair[kind]) for kind in (0, 1)]
                assert mdd.count(common[0]) == prefix["output_only_prefix_assignments"]
                assert mdd.count(common[1]) == prefix["joint_prefix_assignments"]
                canonical_conjunction_checks += 2
                # A complete singleton witness in each family, together with
                # the false two-input root, proves minimum cardinality two.
                vector = mdd.witness(pair[1])
                assert vector is not None and mdd.evaluate(pair[0], vector)
                numerical = solver.forward(rows[operand], payload, vector, mask)
                assert numerical["RC_matches"] and numerical["RC_C1_matches"]
                value = solver.graph.unpack(rows[operand]["variants"][payload]["frozen_payload_signed"])
                rational = solver.rational_forward(operand, value, vector, mask)
                for stage in numerical["stages"]:
                    assert solver.graph.unpack(stage["selected_result"]).fraction() == rational[stage["node"]]
                    rational_stage_checks += 1
                witnesses.append({"operand": operand, "policies": [solver.POLICIES[i] for i in vector],
                                  "numerical_replay": numerical})
            assert common == [0, 0] == [mapping[node] for node in saved["final_roots"]]
            assert summary["output_only_rejection_proved"] and summary["rejection_uses_only_RD"]
            assert summary["target_joint_assignments"] == 0
            assert summary["control_status"] == "NOT_RUN_NO_TARGET_SURVIVOR"
            verified.append({"id": identifier, "output_only_contradiction": True,
                             "minimum_core_cardinality": 2, "singleton_witnesses": witnesses})
    assert seen == expected_ids
    result = {
        "experiment": "h1613_verify_routing_certificate", "status": "PASS",
        "verified_route_payload_cases": len(verified),
        "canonical_prefix_conjunction_checks": canonical_conjunction_checks,
        "direct_singleton_witnesses": 2*len(verified),
        "independent_rational_stage_checks": rational_stage_checks,
        "authenticated_RD_core": [rows[operand]["authenticated_observations"][0] for operand in OPERANDS],
        "RC_only_routing_and_policy_extension": {
            "status": "UNSAT_BY_ALL_ROUTES_RD_CERTIFICATE",
            "proof": "For each payload every routing mask has no shared RD policy vector. A rule selecting routes and policies solely by architectural RC must select one such mask/vector for RD; none satisfies the two recorded RD outputs.",
            "scope": "same original finite widths/graph/constants/finalRC64 and absent/frozen numeric payload; arbitrary RC-only routing AND policy selection; not input-dependent state, changed widths, mixed fourth inputs or other arithmetic graphs"
        },
        "independence_boundary": "Reuses the saved MDD and numerical helpers; no second full-family arithmetic enumeration. Witness stages also use independently spelled rational routing/quantization.",
        "hardware_or_emulator_changes": "none", "cases": verified,
        "sha256": {"script": solver.digest(Path(__file__)), "evidence": evidence}
    }
    output.mkdir(parents=True)
    with (output/"report.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({key: result[key] for key in ("status", "verified_route_payload_cases",
        "canonical_prefix_conjunction_checks", "direct_singleton_witnesses", "independent_rational_stage_checks")}, sort_keys=True))


if __name__ == "__main__":
    main()
