#!/usr/bin/env python3
"""Require one H1595 graph path/prevalue to satisfy all actual RC/C1 labels.

This is a finite, per-operand existential audit, not a selector. No C or
hardware execution, inferred RC lane, regenerated payload, or fitted predicate.
H1596's authenticated direct observations supply final-round inverses; H1599
supplies only status bits actually recorded for the same external tuples.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from fractions import Fraction as F
from pathlib import Path

import h1595_coupled_faithful_reachability as graph
import h1596_rounding_mode_feasibility as rc


spec, Value = graph.spec, graph.Value
LOCKS = {
    "tmp/ledger33/current/h1595_coupled_faithful_reachability_v2/report.json": "d1c4a18f462a24b2282a2e15eb6e0ac374e34f124b0bf3cd0a24663d98669f2f",
    "tmp/ledger33/current/h1596_rounding_mode_feasibility.json": "8b87f3d340e0257d2ea7591ad5a02d87d9d1883f571644ddcb339209f4af64fa",
    "tmp/ledger33/current/h1599_c1_arithmetic_constraints/report.json": "94f627f006c4ace3486899bb7ac6487d01eaf90f1428567ffb712b0f8422f4af",
}
STAGES = ("sparse_RC", "sparse_RC_and_C1", "joint_RC", "joint_RC_and_C1")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def interval(record: dict) -> rc.Interval:
    return rc.Interval(F(record["lower"]), F(record["upper"]), record["lower_closed"], record["upper_closed"])


def refine_c1(current: rc.Interval, observed: str, c1: int) -> rc.Interval:
    y = spec.decode_external(observed).fraction()
    assert y > 0 and c1 in (0, 1)
    # Under the conditional ordinary positive final-add contract, C1=1 iff
    # the stored result is numerically above the common final prevalue.
    return current.intersect(rc.Interval(current.lo, y, current.lc, False)) if c1 else current.intersect(rc.Interval(y, current.hi, True, current.hc))


def correction_for_mask(operand: str, payload: Value, mask: int) -> Value:
    state = graph.initial(operand)
    for index, node in enumerate(graph.NODES):
        exact = graph.operation(state, node, payload)
        ordinary = spec.quantize(exact, node[4], node[5])
        if mask & (1 << index):
            alternative = [v for v in graph.neighbors(exact, node[4]) if graph.key(v) != graph.key(ordinary)]
            assert len(alternative) == 1
            state[node[0]] = alternative[0]
        else:
            state[node[0]] = ordinary
    return state["correction"]


def selftest() -> dict:
    tests = rc.selftest()
    checks = 0
    for n in (-(1 << 67)+11, -(1 << 66)-15, -(1 << 66)+19):
        for displacement in range(-8, 9):
            correction = Value(n+displacement, -72)
            prevalue = spec.exact_add(Value(1, 0), correction).fraction()
            for mode in spec.MODES:
                endpoint = spec.encode_external(spec.add(Value(1, 0), correction, 64, mode))
                y = spec.decode_external(endpoint).fraction()
                c1 = int(y > prevalue)
                unconstrained = rc.inverse(endpoint, mode)
                assert unconstrained.contains(prevalue)
                assert refine_c1(unconstrained, endpoint, c1).contains(prevalue)
                assert not refine_c1(unconstrained, endpoint, c1 ^ 1).contains(prevalue)
                checks += 1
    return {**tests, "joint_positive_forward_inverse_C1_cases": checks, "status": "PASS"}


def load(root: Path) -> tuple[dict, dict, dict, dict, dict]:
    reports, evidence = {}, {}
    for relative, expected in LOCKS.items():
        path = root/relative
        assert digest(path) == expected, relative
        reports[relative] = json.loads(path.read_text())
        evidence[relative] = expected
    gp, rp, cp = (reports[name] for name in LOCKS)
    for relative, expected in (("experiments/h1595_coupled_faithful_reachability.py", gp["sha256"]["script"]),
                               ("experiments/h1596_rounding_mode_feasibility.py", rp["sha256"]["script"]),
                               ("experiments/h1599_c1_arithmetic_constraints.py", cp["sha256"]["script"]),
                               ("experiments/h1592_independent_integer_spec.py", gp["sha256"]["evidence"]["experiments/h1592_independent_integer_spec.py"]),
                               ("tmp/ledger33/current/h1598_source_before.c", gp["sha256"]["source"])):
        assert digest(root/relative) == expected
        evidence[relative] = expected
    for parent in (gp, rp, cp):
        for relative, expected in parent["sha256"]["evidence"].items():
            assert digest(root/relative) == expected, relative
            if relative in evidence:
                assert evidence[relative] == expected
            evidence[relative] = expected
    # Replay the authenticated importer, not its model columns or inferred
    # lanes. Search the entire H1596 direct/external union for our operands,
    # rather than assuming the named enriched subset exhausts their records.
    banks, imported_evidence = rc.load(root)
    assert all(evidence.get(name, expected) == expected for name, expected in imported_evidence.items())
    evidence.update(imported_evidence)
    union = rc.dedup(banks["named"]+banks["history"]+banks["controls"]+banks["aliases"])
    canonical = json.dumps(union, sort_keys=True, separators=(",", ":")).encode()
    assert len(union) == rp["banks"]["union_named_historical_controls_external"]["unique_observed_rows"] == 150005
    assert hashlib.sha256(canonical).hexdigest() == rp["banks"]["union_named_historical_controls_external"]["canonical_observed_rows_sha256"]
    grouped = defaultdict(list)
    for row in gp["rows"]:
        grouped[row["operand"]].append(row)
    assert len(grouped) == 36 and sum(map(len, grouped.values())) == 37
    observations = defaultdict(list)
    for row in union:
        if row["instruction"] == "fcos" and row["operand"] in grouped:
            observations[row["operand"]].append(row)
    assert len(observations) == 36 and sum(map(len, observations.values())) == 64
    assert Counter(len(group) for group in observations.values()) == {4: 9, 2: 1, 1: 26}
    for op, group in grouped.items():
        current = {r["mode"]: r["hardware"] for r in observations[op]}
        assert all(current[r["mode"]] == r["hardware"] for r in group)
    statuses = defaultdict(list)
    for row in cp["rows"]:
        assert row["operand"] in grouped
        assert row["hardware"] == next(r["hardware"] for r in observations[row["operand"]] if r["mode"] == row["mode"])
        statuses[row["operand"]].append(row)
    assert sum(map(len, statuses.values())) == 27
    return grouped, observations, statuses, reports, evidence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    checks = selftest()
    if args.selftest:
        print(json.dumps(checks, sort_keys=True))
        return
    if not args.root or not args.output_dir:
        parser.error("use --selftest or --root/--output-dir")
    root, output = args.root.resolve(), args.output_dir.resolve()
    if output.exists():
        raise SystemExit(f"refusing existing output directory: {output}")
    grouped, observations, statuses, previous, evidence = load(root)
    h1596 = previous["tmp/ledger33/current/h1596_rounding_mode_feasibility.json"]
    enriched = {r["operand"]: r for r in h1596["banks"]["named_direct_enriched_with_authenticated_historical_modes"]["groups"]}
    output.mkdir(parents=True)
    details, transitions = [], []
    counts = Counter()
    raw_path = output/"joint_rc_c1_paths.tsv.gz"
    with raw_path.open("xb") as raw_file, gzip.GzipFile(fileobj=raw_file, mode="wb", filename="", mtime=0) as raw:
        raw.write(b"operand\tpayload\tmask\tcorrection_n_hex\tcorrection_e2\tjoint_RC_matches\tC1_matches\n")
        for operand in sorted(grouped):
            sparse = grouped[operand]
            observed = observations[operand]
            status = statuses.get(operand, [])
            original = sparse[0]
            current = rc.inverse(observed[0]["hardware"], observed[0]["mode"])
            for row in observed[1:]:
                current = current.intersect(rc.inverse(row["hardware"], row["mode"]))
            assert current.json() == enriched[operand]["intersection"]
            current_c1 = current
            for row in status:
                ordinary = rc.inverse(row["hardware"], row["mode"])
                refined = refine_c1(ordinary, row["hardware"], row["c1"])
                # H1599 stores a magnitude-correction inverse. Reflect about
                # one to compare the exact prevalue interval independently.
                old = interval(row["correction_inverse_with_C1"])
                reflected = rc.Interval(1-old.hi, 1-old.lo, old.hc, old.lc)
                assert refined == reflected
                current_c1 = refine_c1(current_c1, row["hardware"], row["c1"])
            variants = {}
            for payload_name in ("omitted", "frozen_numeric"):
                variant = original["variants"][payload_name]
                payload = graph.unpack(variant["payload_signed_dyadic"])
                assert all(graph.key(graph.unpack(r["variants"][payload_name]["payload_signed_dyadic"])) == graph.key(payload) for r in sparse)
                # Intersect the original observed modes before replaying any
                # correction. Added constraints can only remove those paths.
                masks = set(variant["families"]["all_graph"]["successful_masks"])
                for row in sparse[1:]:
                    masks &= set(row["variants"][payload_name]["families"]["all_graph"]["successful_masks"])
                kept = {name: [] for name in STAGES}
                prevalues = {}
                cached = {}
                for mask in sorted(masks):
                    correction = correction_for_mask(operand, payload, mask)
                    k = graph.key(correction)
                    if k not in cached:
                        z = spec.exact_add(Value(1, 0), correction).fraction()
                        assert z > 0
                        endpoints = {row["mode"]: spec.encode_external(spec.add(Value(1, 0), correction, 64, row["mode"])) for row in observed}
                        assert all(endpoints[row["mode"]] == row["hardware"] for row in sparse)
                        rc_match = all(endpoints[row["mode"]] == row["hardware"] for row in observed)
                        c1_match = all(int(spec.decode_external(row["hardware"]).fraction() > z) == row["c1"] for row in status)
                        assert current.contains(z) == rc_match
                        assert current_c1.contains(z) == (rc_match and c1_match)
                        cached[k] = rc_match, c1_match, z, endpoints
                    rc_match, c1_match, z, endpoints = cached[k]
                    for stage, accepted in (("sparse_RC", True), ("sparse_RC_and_C1", c1_match),
                                             ("joint_RC", rc_match), ("joint_RC_and_C1", rc_match and c1_match)):
                        if accepted:
                            kept[stage].append(mask)
                    raw.write((f"{operand}\t{payload_name}\t{mask}\t{correction.n:x}\t{correction.e}\t{int(rc_match)}\t{int(c1_match)}\n").encode())
                    if k not in prevalues:
                        prevalues[k] = {"signed_correction": correction.record(), "common_prevalue": str(z),
                            "predicted_outputs": endpoints, "matches_all_RC": rc_match, "matches_C1": c1_match,
                            "graph_masks": []}
                    prevalues[k]["graph_masks"].append(mask)
                for row in status:
                    old = set(row["variants"][payload_name]["families_after_C1"]["all_graph"]["successful_masks"])
                    # All observed C1 entries correspond to an original sparse
                    # mode. No status lane has been fabricated by the join.
                    assert set(kept["sparse_RC_and_C1"]) == masks & old
                stages = {stage: {family: graph.summarize_masks(accepted, allowed) for family, allowed in graph.FAMILIES.items()}
                          for stage, accepted in kept.items()}
                witness_masks = sorted({m for family in stages["joint_RC_and_C1"].values() for m in family["minimum_masks"]})
                witnesses = {str(mask): graph.replay_mask(operand, observed[0]["mode"], payload, mask) for mask in witness_masks}
                for mask, witness in witnesses.items():
                    correction = graph.unpack(witness["steps"][-1]["chosen_output"])
                    assert graph.key(correction) in cached and cached[graph.key(correction)][:2] == (True, True)
                    witness["all_observed_predicted_outputs"] = cached[graph.key(correction)][3]
                    witness["common_prevalue"] = str(cached[graph.key(correction)][2])
                for stage in STAGES:
                    counts[payload_name+"."+stage+".paths"] += len(kept[stage])
                    for family, summary in stages[stage].items():
                        counts[payload_name+"."+stage+"."+family+(".reachable" if summary["reachable"] else ".unreachable")] += 1
                for family in graph.FAMILIES:
                    before = stages["sparse_RC_and_C1"][family]
                    after = stages["joint_RC_and_C1"][family]
                    if (before["reachable"], before["minimum_departures"], before["must_depart_nodes"], before["inclusion_minimal_masks"]) != (after["reachable"], after["minimum_departures"], after["must_depart_nodes"], after["inclusion_minimal_masks"]):
                        transitions.append({"operand": operand, "payload": payload_name, "family": family,
                            "new_family_exclusion": before["reachable"] and not after["reachable"],
                            "before_minimum": before["minimum_departures"], "after_minimum": after["minimum_departures"],
                            "before_must_depart": before["must_depart_nodes"], "after_must_depart": after["must_depart_nodes"],
                            "before_minimal_supports": before.get("inclusion_minimal_supports", []),
                            "after_minimal_supports": after.get("inclusion_minimal_supports", [])})
                variants[payload_name] = {"frozen_payload_signed": payload.record(), "stages": stages,
                    "added_RC_modes_remove_no_path_after_actual_C1": kept["sparse_RC_and_C1"] == kept["joint_RC_and_C1"],
                    "added_RC_modes_rejected_paths_without_C1": len(kept["sparse_RC"])-len(kept["joint_RC"]),
                    "added_RC_modes_rejected_paths_after_C1": len(kept["sparse_RC_and_C1"])-len(kept["joint_RC_and_C1"]),
                    "distinct_sparse_prevalues": len(prevalues),
                    "distinct_joint_RC_prevalues": sum(r["matches_all_RC"] for r in prevalues.values()),
                    "distinct_joint_RC_C1_prevalues": sum(r["matches_all_RC"] and r["matches_C1"] for r in prevalues.values()),
                    "prevalues": list(prevalues.values()), "joint_minimum_witnesses": witnesses}
            details.append({"operand": operand, "sparse_observed_modes": [r["mode"] for r in sparse],
                "authenticated_observations": observed,
                "actual_C1_constraints": [{k: r[k] for k in ("source", "mode", "hardware", "hardware_status", "c1")} for r in status],
                "joint_RC_inverse": current.json(), "joint_RC_C1_inverse": current_c1.json(), "variants": variants})
            print(operand, len(observed), {p: v["stages"]["joint_RC_and_C1"]["all_graph"]["minimum_departures"] for p, v in variants.items()}, flush=True)
    report = {"experiment": "h1600_joint_rc_c1_faithful_graph", "status": "JOINT_EXISTENTIAL_FEASIBILITY_NOT_SELECTOR",
        "hardware_execution": "none", "C_execution": "none", "unobserved_modes_or_status_inferred": False,
        "operands": 36, "sparse_observed_RC_rows": 37, "authenticated_joint_RC_rows": 64,
        "actual_C1_rows": 27, "mode_coverage": {"four_modes": 9, "RD_RZ_only": 1, "single_mode": 26},
        "selftest": checks, "summary": dict(counts), "transitions_beyond_sparse_RC_plus_actual_C1": transitions,
        "added_RC_modes_remove_no_path_after_actual_C1": all(v["added_RC_modes_remove_no_path_after_actual_C1"] for r in details for v in r["variants"].values()),
        "new_family_exclusions": [t for t in transitions if t["new_family_exclusion"]], "rows": details,
        "claim_boundary": "one common RC-independent faithful-graph path and prevalue per operand must satisfy all its actual RC/C1 constraints; no common cross-input policy, silicon-equivalence or general-selector claim",
        "graph_assumptions": "H1595 fixed67 products/square/fourth/correction and64 Horner adds; shared dependencies; omitted or original numeric payload frozen; ordinary final RC and conditional C1 round-up interpretation",
        "scope_exclusion": "no alias-to-residual transfer assumptions, no inferred hardware lanes, no status beyond authenticated C1 used",
        "sha256": {"script": digest(Path(__file__)), "evidence": evidence, "raw_paths": digest(raw_path)}}
    with (output/"report.json").open("x") as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps({"summary": dict(counts), "new_family_exclusions": report["new_family_exclusions"], "transitions": transitions}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
