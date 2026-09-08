#!/usr/bin/env python3
"""Shared multiplier/add widths with independently free common policies.

Unlike a one-cut perturbation, a width change reaches every operation in its
class. Widths are numerical hypotheses, not recovered micro-op contracts.
Only already authenticated observations are constraints; no hardware runs.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
import random
from collections import Counter
from fractions import Fraction
from functools import lru_cache
from pathlib import Path

import h1606_single_width_policy_solve as one_width
import h1608_combined_policy_bypass_solve as combined


fixed, graph, spec, V = combined.fixed, combined.graph, combined.spec, combined.V
N, K = len(graph.NODES), len(fixed.POLICIES)
PRECISIONS = (24, 53, *range(64, 129))
LOCKS = {
    "experiments/h1606_single_width_policy_solve.py":
        "487b2a2ed81bdf540ffaa90ab6edff59c01a26bb8ee8b4f1f2735e0ec46993ef",
    "experiments/h1608_combined_policy_bypass_solve.py":
        "498746dcc91a35b326785af800cbc864b4ad5f53e4d801d89f3136c474e829f6",
    "tmp/ledger33/current/h1608_combined_policy_bypass_solve/report.json":
        "842bd5ff9c73c8e8e3dd4dedeb5874df86f01501c8d45d899554e80857cb4ec4",
    "tmp/ledger33/current/h1594_internal_operation_provenance.json":
        "dbf427723d53a4ecee0e2374acecbac07892b1708e78d160b5c9123c625382b6",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def operator_widths(multiply: int, horner_add: int, correction: int) -> tuple[int, ...]:
    return tuple(multiply if node[1] == "mul" else correction if node[1] == "add_payload" else horner_add
                 for node in graph.NODES)


def compile_operand(mdd: fixed.MDD, row: dict, payload_name: str, widths: tuple[int, ...]) -> tuple[tuple[int, int], dict]:
    assert len(widths) == N and all(width >= 2 for width in widths)
    payload = graph.unpack(row["variants"][payload_name]["frozen_payload_signed"])
    bounds = [(Fraction(q["lower"]), Fraction(q["upper"]), q["lower_closed"], q["upper_closed"])
              for q in (row["joint_RC_inverse"], row["joint_RC_C1_inverse"])]

    @lru_cache(None)
    def visit(level: int, values: tuple[tuple[int, int], ...]) -> tuple[int, int, int]:
        state = {name: V(*value) for name, value in zip(combined.LIVE[level], values)}
        if level == N:
            z = spec.exact_add(V(1, 0), state["correction"]).fraction()
            assert 0 < z < 1
            accepts = [int((z > lo or z == lo and lc) and (z < hi or z == hi and hc))
                       for lo, hi, lc, hc in bounds]
            assert accepts[1] <= accepts[0]
            return accepts[0], accepts[1], 1
        node = graph.NODES[level]
        exact = graph.operation(state, node, payload)
        keys = [combined.numerical_key(fixed.rounded(exact, widths[level], policy)) for policy in fixed.POLICIES]
        branches = {}
        for key in keys:
            if key not in branches:
                state[node[0]] = V(*key)
                values_next = tuple(combined.numerical_key(state[name]) for name in combined.LIVE[level+1])
                branches[key] = visit(level+1, values_next)
        assert 1 <= len(branches) <= 2
        roots = [mdd.node(level, tuple(branches[key][kind] for key in keys)) for kind in (0, 1)]
        return roots[0], roots[1], sum(result[2] for result in branches.values())

    initial = graph.initial(row["operand"])
    result = visit(0, tuple(combined.numerical_key(initial[name]) for name in combined.LIVE[0]))
    info = visit.cache_info()
    stats = {"numerical_paths": result[2], "live_states": info.currsize, "suffix_reuses": info.hits}
    visit.cache_clear()
    return (result[0], result[1]), stats


def forward(row: dict, payload: str, widths: tuple[int, ...], vector: tuple[int, ...]) -> dict:
    # H1606's straight-line non-memoized traversal provides a separate
    # execution path and checks observed modes and C1 against the inverse.
    return one_width.forward(row, payload, widths, vector)


def selftest(rows: list[dict], root: Path) -> dict:
    tests = fixed.selftest()
    rng = random.Random(0x1610)
    grid_checks = 0
    for width in PRECISIONS:
        for n in (0, 1, (1 << width)-1, 1 << width, (1 << width)+1,
                  (1 << (width+3))+3, (1 << (width+3))+4, (1 << (width+3))+5):
            for sign in (-1, 1):
                value = V(sign*n, -width-3)
                for policy in fixed.POLICIES:
                    expected = combined.rational_round(value.fraction(), width, policy)
                    assert fixed.rounded(value, width, policy).fraction() == expected
                    grid_checks += 1
    stage_checks = 0
    for _ in range(128):
        row = rng.choice(rows)
        payload_name = rng.choice(("omitted", "frozen_numeric"))
        payload = graph.unpack(row["variants"][payload_name]["frozen_payload_signed"])
        widths = tuple(rng.choice(PRECISIONS) for _ in range(N))
        vector = tuple(rng.randrange(K) for _ in range(N))
        state = graph.initial(row["operand"])
        rational = {name: value.fraction() for name, value in state.items()}
        for node, width, choice in zip(graph.NODES, widths, vector):
            name, kind, left, right, _, _ = node
            exact = graph.operation(state, node, payload)
            state[name] = fixed.rounded(exact, width, fixed.POLICIES[choice])
            raw = rational[left]*rational[right] if kind == "mul" else rational[left]+rational[right]
            if kind == "add_payload":
                raw += payload.fraction()
            rational[name] = combined.rational_round(raw, width, fixed.POLICIES[choice])
            assert rational[name] == state[name].fraction()
            stage_checks += 1
    baseline_checks = 0
    for payload in ("omitted", "frozen_numeric"):
        mdd = fixed.MDD(N, K)
        saved = json.loads((root/combined.H1602/f"{payload}_diagram.json").read_text())
        mapping = combined.import_nodes(mdd, saved["nodes"])
        for i, row in enumerate(rows):
            pair, _ = compile_operand(mdd, row, payload, tuple(node[4] for node in graph.NODES))
            assert pair[1] == mapping[saved["operand_roots"][i]]
            baseline_checks += 1
    traversal_checks = 0
    for _ in range(32):
        row = rng.choice(rows)
        payload = rng.choice(("omitted", "frozen_numeric"))
        # Include independently varied widths, a superset of this campaign's
        # class-shared shapes, to test the parameterized compiler itself.
        widths = tuple(rng.choice(PRECISIONS) for _ in range(N))
        mdd = fixed.MDD(N, K)
        pair, stats = compile_operand(mdd, row, payload, widths)
        reference, leaves = one_width.compile_operand(mdd, row, payload, widths)
        assert pair[1] == reference
        assert stats["numerical_paths"] == leaves
        traversal_checks += 1
    return {"inherited_tests": tests, "all_precision_rational_rounding_checks": grid_checks,
            "random_width_rational_graph_stage_checks": stage_checks, "full_H1602_function_checks": baseline_checks,
            "full_nonmemoized_random_width_function_checks": traversal_checks, "status": "PASS"}


def control_row(control) -> dict:
    observations = [{"mode": mode, "hardware": control.hardware(mode)} for mode in fixed.rc.MODES]
    inverse = fixed.rc.inverse(observations[0]["hardware"], observations[0]["mode"])
    for item in observations[1:]:
        inverse = inverse.intersect(fixed.rc.inverse(item["hardware"], item["mode"]))
    return {"operand": control.operand, "authenticated_observations": observations, "actual_C1_constraints": [],
            "joint_RC_inverse": inverse.json(), "joint_RC_C1_inverse": inverse.json(),
            "variants": {"omitted": {"frozen_payload_signed": V(0, 0).record()}}}


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
    old = json.loads((root/"tmp/ledger33/current/h1608_combined_policy_bypass_solve/report.json").read_text())
    for relative, expected in old["sha256"]["evidence"].items():
        assert digest(root/relative) == expected, relative
        assert evidence.get(relative, expected) == expected
        evidence[relative] = expected
    facts = json.loads((root/fixed.REPORT).read_text())
    rows = facts["rows"]
    tests = selftest(rows, root)
    first = ("3ffc e73ffffd2c52df71", "3ffc fcbfffffcee1bd36", "3ffc b0000000044ca2bf",
             "3ffc b72fd2547f8c2fef", "3ffc ba100000056e0a67", "3ffc cdcc0585c940196f")
    ordered = sorted(rows, key=lambda row: (first.index(row["operand"]) if row["operand"] in first else len(first), row["operand"]))
    shapes = [(m, a, c) for m, a in itertools.product(PRECISIONS, repeat=2) for c in sorted({67, a})]
    assert len(shapes) == 2*len(PRECISIONS)**2-len(PRECISIONS)
    output.mkdir(parents=True)
    raw_path = output/"precision_diagrams.jsonl.gz"
    rng, details, target_survivors, control_survivors = random.Random(0x161000), [], [], []
    replay_count = 0
    wall = None
    with raw_path.open("xb") as raw_file, gzip.GzipFile(fileobj=raw_file, mode="wb", filename="", mtime=0) as raw:
        for multiply, add, correction in shapes:
            widths = operator_widths(multiply, add, correction)
            for payload in ("omitted", "frozen_numeric"):
                mdd = fixed.MDD(N, K)
                common = [1, 1]
                checked, roots = [], []
                for row in ordered:
                    pair, stats = compile_operand(mdd, row, payload, widths)
                    roots.append(pair)
                    common = [mdd.conjunction(common[kind], pair[kind]) for kind in (0, 1)]
                    checked.append({"operand": row["operand"], **stats,
                                    "output_only_prefix_assignments": mdd.count(common[0]),
                                    "joint_prefix_assignments": mdd.count(common[1])})
                    vectors = [tuple(rng.randrange(K) for _ in range(N)) for _ in range(4)]
                    witness = mdd.witness(pair[1])
                    if witness is not None:
                        vectors.append(witness)
                    for vector in vectors:
                        direct = forward(row, payload, widths, vector)
                        assert mdd.evaluate(pair[1], vector) == direct["accepted"]
                        output_ok = all(direct["outputs"][o["mode"]] == o["hardware"] for o in row["authenticated_observations"])
                        assert mdd.evaluate(pair[0], vector) == output_ok
                        replay_count += 1
                    if common[1] == 0:
                        break
                identifier = f"mul{multiply}:add{add}:correction{correction}:{payload}"
                control_checks = []
                record = {"id": identifier, "multiply_precision": multiply, "horner_add_precision": add,
                    "correction_precision": correction, "payload": payload, "checked_prefix": checked,
                    "target_joint_assignments": mdd.count(common[1]),
                    "status": "UNSAT_OBSERVED_PREFIX" if common[1] == 0 else "SAT_TARGETS_REQUIRES_CONTROLS",
                    "output_only_rejection_proved": common[0] == 0,
                    "untested_later_operands_not_scored": len(rows)-len(checked)}
                if common[1]:
                    assert len(checked) == len(rows)
                    target_survivors.append(identifier)
                    vector = mdd.witness(common[1])
                    record["target_witness_policies"] = [fixed.POLICIES[p] for p in vector]
                    record["target_witness_replays"] = {row["operand"]: forward(row, payload, widths, vector) for row in rows}
                    assert all(item["accepted"] for item in record["target_witness_replays"].values())
                    if payload == "frozen_numeric":
                        record["control_status"] = "NEEDS_AUTHENTICATED_ORIGINAL_NUMERIC_PAYLOAD_TRACES_NO_FABRICATION"
                    else:
                        if wall is None:
                            import h1603_direct_control_semantics_bank as controls
                            wall = controls.load_controls(root)
                            evidence.update(wall.evidence)
                        for control in wall.controls:
                            row = control_row(control)
                            pair, _ = compile_operand(mdd, row, payload, widths)
                            common = [mdd.conjunction(common[kind], pair[kind]) for kind in (0, 1)]
                            control_checks.append({"operand": row["operand"], "roots": pair,
                                                   "remaining_assignments": mdd.count(common[1])})
                            if common[1] == 0:
                                break
                        record["control_status"] = "FALSIFIED_BY_CACHED_CONTROLS" if common[1] == 0 else "PASS_CACHED_BANK_ONLY_NOT_A_GENERAL_SOLUTION"
                        record["control_prefix_size"] = len(control_checks)
                        if common[1]:
                            control_survivors.append(identifier)
                            record["control_surviving_policies"] = [fixed.POLICIES[p] for p in mdd.witness(common[1])]
                details.append(record)
                raw.write((json.dumps({"id": identifier, "widths": widths, "policies": fixed.POLICIES,
                    "operand_order": [item["operand"] for item in checked], "nodes": mdd.nodes,
                    "target_roots": roots, "control_checks": control_checks, "final_roots": common}, separators=(",", ":"))+"\n").encode())
                if len(details) % 256 == 0 or record["target_joint_assignments"]:
                    print(len(details), "of", 2*len(shapes), identifier, record["status"], flush=True)
    assert len(details) == 2*len(shapes)
    report = {"experiment": "h1610_shared_operator_precision", "hardware_and_C_execution": "none",
        "selector_promotion": "none", "precisions": PRECISIONS, "width_hypotheses_per_payload": len(shapes),
        "precision_payload_cases": len(details), "policy_assignments_per_hypothesis": K**N,
        "node_classes": {"multiply": [node[0] for node in graph.NODES if node[1] == "mul"],
                         "horner_add": [node[0] for node in graph.NODES if node[1] == "add"],
                         "correction": ["correction"]},
        "observed_operands": len(rows), "actual_RC_rows": 64, "actual_C1_rows": 27,
        "selftest": tests, "direct_full_policy_replays": replay_count,
        "target_survivors": target_survivors, "cached_control_survivors": control_survivors,
        "rejection_prefix_histogram": dict(sorted(Counter(len(item["checked_prefix"]) for item in details if not item["target_joint_assignments"]).items())),
        "hypotheses": details,
        "scope": "shared multiplier width M and four-Horner-add width A, correction width A or67; all13 conventional policies independently free but fixed across inputs/RC; original graph/constants, final RC64, absent or frozen original numeric payload",
        "precision_range_rationale": "24/53 are additional coarse finite hypotheses; every integer64..128 spans a bounded wide numerical range; these are significand bits, not storage-format bits or a proven physical limit",
        "claim_boundary": "no arbitrary per-cut widths, exact-bypass combinations, RC/input-dependent widths or policies, new graph/routing/history, nonstandard arithmetic or regenerated payload; untested later rows are not successes; no global closed-form impossibility",
        "sha256": {"script": digest(Path(__file__)), "evidence": evidence, "precision_diagrams": digest(raw_path)}}
    with (output/"report.json").open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"hypotheses": len(details), "target_survivors": target_survivors,
                      "control_survivors": control_survivors, "prefix_histogram": report["rejection_prefix_histogram"]}, sort_keys=True))


if __name__ == "__main__":
    main()
