#!/usr/bin/env python3
"""Test shared X67/Y64 multiplier inputs with free output materializations.

The graph, constants and final RC64 are fixed. Each unequal-operand multiply
has an input-independent port orientation; X is CHOP67 and Y has one shared
64-bit conventional policy. All thirteen result policies remain independently
free among five conventional policies and exact. This is a numerical family,
not evidence that historical port diagrams specify every Skylake operation.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import random
from collections import Counter
from fractions import Fraction
from functools import lru_cache
from pathlib import Path

import h1608_combined_policy_bypass_solve as base
import h1613_split_power_forwarding as routing


fixed, graph, spec, V = base.fixed, base.graph, base.spec, base.V
N, K, POLICIES = base.N, base.K, base.CHOICES
ORIENTED = tuple(node[0] for node in graph.NODES if node[1] == "mul" and node[2] != node[3])
Y_POLICIES = fixed.POLICIES
PARENT = "tmp/ledger33/current/h1608_combined_policy_bypass_solve"
LOCKS = {
    PARENT+"/report.json": "842bd5ff9c73c8e8e3dd4dedeb5874df86f01501c8d45d899554e80857cb4ec4",
    "experiments/h1608_combined_policy_bypass_solve.py":
        "498746dcc91a35b326785af800cbc864b4ad5f53e4d801d89f3136c474e829f6",
    "experiments/h1613_split_power_forwarding.py":
        "899e156f802dcfa6eb6a51ede71d2ce1413bbd1ca3159122dec37677860abcaa",
    "experiments/h1357_x67_y64_power_recurrence.py":
        "c25aedd9b24729412e722b2f472a8cae5ac0968d2252fd11a058331df0a84162",
    "tmp/ledger33/current/h1357_x67_y64_power_recurrence.txt":
        "2a34305720bd30c7bcc98853a77168bc821c00ad45c9c53055ce28bace959427",
    "experiments/h1358_score_x67_y64_direct_banks.py":
        "8f1c2c8b0b7709599e0b9912f829fe4871a61b9daf618a7b0f49b64954d434fb",
    "tmp/ledger33/current/h1358_x67_y64_direct_score_pc.txt":
        "92393995dd6b5a42ddb245192ce9fddb3cc70fd37188dc77fa44c3d6ea396c46",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def port_inputs(node: tuple, state: dict, mask: int, y_policy: str, enabled: bool) -> tuple[V, V]:
    left, right = state[node[2]], state[node[3]]
    if node[0] in ORIENTED and mask & (1 << ORIENTED.index(node[0])):
        left, right = right, left
    if enabled:
        left = fixed.rounded(left, 67, "chop")
        right = fixed.rounded(right, 64, y_policy)
    return left, right


def operation(state: dict, node: tuple, payload: V, mask: int, y_policy: str, enabled: bool = True) -> V:
    if node[1] == "mul":
        left, right = port_inputs(node, state, mask, y_policy, enabled)
        return spec.exact_mul(left, right)
    return graph.operation(state, node, payload)


def compile_operand(mdd: fixed.MDD, row: dict, payload_name: str, mask: int,
                    y_policy: str, enabled: bool = True) -> tuple[tuple[int, int], dict]:
    payload = graph.unpack(row["variants"][payload_name]["frozen_payload_signed"])
    bounds = [(Fraction(q["lower"]), Fraction(q["upper"]), q["lower_closed"], q["upper_closed"])
              for q in (row["joint_RC_inverse"], row["joint_RC_C1_inverse"])]

    @lru_cache(None)
    def visit(index: int, values: tuple[tuple[int, int], ...]) -> tuple[int, int, int]:
        state = {name: V(*value) for name, value in zip(base.LIVE[index], values)}
        if index == N:
            z = spec.exact_add(V(1, 0), state["correction"]).fraction()
            assert 0 < z < 1
            accepted = [int((z > lo or z == lo and lc) and (z < hi or z == hi and hc))
                        for lo, hi, lc, hc in bounds]
            assert accepted[1] <= accepted[0]
            return accepted[0], accepted[1], 1
        node = graph.NODES[index]
        exact = operation(state, node, payload, mask, y_policy, enabled)
        choices = [base.numerical_key(base.selected(exact, node[4], policy)) for policy in range(K)]
        branches = {}
        for value in choices:
            if value not in branches:
                state[node[0]] = V(*value)
                next_values = tuple(base.numerical_key(state[name]) for name in base.LIVE[index+1])
                branches[value] = visit(index+1, next_values)
        assert 1 <= len(branches) <= 3
        pair = tuple(mdd.node(index, tuple(branches[value][kind] for value in choices)) for kind in (0, 1))
        return *pair, sum(result[2] for result in branches.values())

    state = graph.initial(row["operand"])
    result = visit(0, tuple(base.numerical_key(state[name]) for name in base.LIVE[0]))
    info = visit.cache_info()
    stats = {"numerical_paths": result[2], "live_states": info.currsize, "suffix_reuses": info.hits}
    visit.cache_clear()
    return result[:2], stats


def forward_values(operand: str, payload: V, vector: tuple[int, ...], mask: int,
                   y_policy: str, enabled: bool = True) -> tuple[V, list]:
    state, stages = graph.initial(operand), []
    for node, policy in zip(graph.NODES, vector):
        exact = operation(state, node, payload, mask, y_policy, enabled)
        stage = {"node": node[0], "policy": POLICIES[policy]}
        if node[1] == "mul":
            left, right = port_inputs(node, state, mask, y_policy, enabled)
            stage["X_input"], stage["Y_input"] = left.record(), right.record()
        state[node[0]] = base.selected(exact, node[4], policy)
        stages.append({**stage, "exact_result": exact.record(), "selected_result": state[node[0]].record()})
    return state["correction"], stages


def forward(row: dict, payload_name: str, vector: tuple[int, ...], mask: int, y_policy: str) -> dict:
    payload = graph.unpack(row["variants"][payload_name]["frozen_payload_signed"])
    correction, stages = forward_values(row["operand"], payload, vector, mask, y_policy)
    return {**base.bypass.constraints(row, correction), "stages": stages}


def rational_forward(operand: str, payload: V, vector: tuple[int, ...], mask: int, y_policy: str) -> dict:
    """Independent explicit dataflow and port arithmetic, without operation()."""
    x = spec.decode_external(operand).fraction()
    c = {i: value.fraction() for i, value in spec.COEFFICIENTS.items()}
    chosen = {}
    def multiply(index, left, right, bit=None):
        if bit is not None and mask & (1 << bit):
            left, right = right, left
        return (base.rational_round(left, 67, "chop") *
                base.rational_round(right, 64, y_policy))
    def keep(index, value):
        selected = base.rational_round(value, graph.NODES[index][4], POLICIES[vector[index]])
        chosen[graph.NAMES[index]] = selected
        return selected
    square = keep(0, multiply(0, x, x))
    fourth = keep(1, multiply(1, square, square))
    n1 = keep(2, multiply(2, fourth, c[5], 0))
    nadd = keep(3, c[3]+n1)
    n2 = keep(4, multiply(4, fourth, nadd, 1))
    negative = keep(5, c[1]+n2)
    p1 = keep(6, multiply(6, fourth, c[6], 2))
    padd = keep(7, c[4]+p1)
    p2 = keep(8, multiply(8, fourth, padd, 3))
    positive = keep(9, c[2]+p2)
    left = keep(10, multiply(10, square, negative, 4))
    right = keep(11, multiply(11, fourth, positive, 5))
    keep(12, left+right+payload.fraction())
    return chosen


def selftest() -> dict:
    tests = base.selftest()
    assert ORIENTED == ("negative_mul1", "negative_mul2", "positive_mul1", "positive_mul2", "left", "right")
    rng = random.Random(0x1614)
    stages_checked = input_checks = boundary_checks = fourth_checks = 0
    for mask in range(64):
        for y_policy in Y_POLICIES:
            operand = f"3ffc {rng.randrange(1 << 63, 1 << 64):016x}"
            payload = V(rng.randrange(-8, 9), -81)
            vector = tuple(rng.randrange(K) for _ in range(N))
            _, stages = forward_values(operand, payload, vector, mask, y_policy)
            rational = rational_forward(operand, payload, vector, mask, y_policy)
            for stage in stages:
                assert graph.unpack(stage["selected_result"]).fraction() == rational[stage["node"]]
                stages_checked += 1
                if "X_input" in stage:
                    assert int(stage["X_input"]["sig_hex"], 16).bit_length() <= 67
                    assert int(stage["Y_input"]["sig_hex"], 16).bit_length() <= 64
                    input_checks += 1
            # Disabling both input cuts restores the original whole graph,
            # regardless of orientation, because multiplication commutes.
            plain, _ = forward_values(operand, payload, vector, mask, y_policy, False)
            state = graph.initial(operand)
            for node, policy in zip(graph.NODES, vector):
                state[node[0]] = base.selected(graph.operation(state, node, payload), node[4], policy)
            assert plain.fraction() == state["correction"].fraction()
            boundary_checks += 1
            # The ordinary fourth operation contains the known numerical
            # X67/Y64 power recurrence; this does not transfer its domain gate.
            x = spec.decode_external(operand)
            square = spec.mul(x, x, 67, "chop")
            actual = base.selected(operation({"square": square}, graph.NODES[1], V(0, 0), mask, "chop"), 67, 0)
            expected = spec.mul(square, spec.quantize(square, 64, "chop"), 67, "chop")
            assert actual.fraction() == expected.fraction()
            fourth_checks += 1
    return {"inherited_tests": tests, "rational_graph_stage_checks": stages_checked,
            "materialized_input_width_checks": input_checks, "disabled_port_graph_checks": boundary_checks,
            "ordinary_X67_Y64_fourth_checks": fourth_checks, "status": "PASS"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    tests = selftest()
    if args.selftest:
        print(json.dumps(tests, sort_keys=True))
        return
    if not args.root or not args.output_dir:
        parser.error("use --selftest or --root/--output-dir")
    root, output = args.root.resolve(), args.output_dir.resolve()
    assert not output.exists(), "refusing existing output directory"
    evidence = dict(LOCKS)
    for relative, expected in evidence.items():
        assert digest(root/relative) == expected, relative
    prior = json.loads((root/PARENT/"report.json").read_text())
    for relative, expected in prior["sha256"]["evidence"].items():
        assert digest(root/relative) == expected, relative
        assert evidence.get(relative, expected) == expected
        evidence[relative] = expected
    facts = json.loads((root/fixed.REPORT).read_text())
    rows = facts["rows"]
    first = ("3ffc e73ffffd2c52df71", "3ffc fcbfffffcee1bd36", "3ffc b0000000044ca2bf",
             "3ffc b72fd2547f8c2fef", "3ffc ba100000056e0a67", "3ffc cdcc0585c940196f")
    ordered = sorted(rows, key=lambda row: (first.index(row["operand"]) if row["operand"] in first else len(first), row["operand"]))
    identity_checks = 0
    for payload in ("omitted", "frozen_numeric"):
        relative = PARENT+f"/{payload}_diagram.json"
        evidence[relative] = prior["results"][payload]["diagram_sha256"]
        assert digest(root/relative) == evidence[relative]
        saved = json.loads((root/relative).read_text())
        mdd = fixed.MDD(N, K)
        mapping = base.import_nodes(mdd, saved["nodes"])
        for index, row in enumerate(rows):
            pair, _ = compile_operand(mdd, row, payload, index % 64, Y_POLICIES[index % 5], False)
            assert list(pair) == [mapping[node] for node in saved["operand_roots"][index]]
            identity_checks += 2
    output.mkdir(parents=True)
    raw_path = output/"port_diagrams.jsonl.gz"
    details, survivors = [], []
    checks = rational_checks = 0
    rng, wall = random.Random(0x161400), None
    with raw_path.open("xb") as raw_file, gzip.GzipFile(fileobj=raw_file, mode="wb", filename="", mtime=0) as raw:
        for y_policy in Y_POLICIES:
            for mask in range(64):
                for payload in ("omitted", "frozen_numeric"):
                    mdd, common, checked, roots = fixed.MDD(N, K), [1, 1], [], []
                    for row in ordered:
                        pair, stats = compile_operand(mdd, row, payload, mask, y_policy)
                        roots.append(pair)
                        common = [mdd.conjunction(common[kind], pair[kind]) for kind in (0, 1)]
                        vectors = [tuple(rng.randrange(K) for _ in range(N)) for _ in range(16)]
                        vectors.extend(vector for vector in (mdd.witness(pair[0]), mdd.witness(pair[1])) if vector is not None)
                        for index, vector in enumerate(vectors):
                            numerical = forward(row, payload, vector, mask, y_policy)
                            assert mdd.evaluate(pair[0], vector) == numerical["RC_matches"]
                            assert mdd.evaluate(pair[1], vector) == numerical["RC_C1_matches"]
                            checks += 1
                            if index == 0:
                                value = graph.unpack(row["variants"][payload]["frozen_payload_signed"])
                                rational = rational_forward(row["operand"], value, vector, mask, y_policy)
                                for stage in numerical["stages"]:
                                    assert graph.unpack(stage["selected_result"]).fraction() == rational[stage["node"]]
                                    rational_checks += 1
                        checked.append({"operand": row["operand"], **stats,
                            "output_prefix_assignments": mdd.count(common[0]), "joint_prefix_assignments": mdd.count(common[1])})
                        if common[1] == 0:
                            break
                    identifier = f"Y{y_policy}:route{mask:02d}:{payload}"
                    detail = {"id": identifier, "routing_mask": mask, "Y_policy": y_policy, "payload": payload,
                        "checked_prefix": checked, "target_joint_assignments": mdd.count(common[1]),
                        "output_only_rejection_proved": common[0] == 0,
                        "rejection_uses_only_RD": common[0] == 0 and all({o["mode"] for o in row["authenticated_observations"]} == {"rd"} for row in ordered[:len(checked)]),
                        "control_status": "NOT_RUN_NO_TARGET_SURVIVOR"}
                    control_checks = []
                    if common[1]:
                        assert len(checked) == len(rows)
                        survivors.append(identifier)
                        vector = mdd.witness(common[1])
                        detail["witness_policies"] = [POLICIES[i] for i in vector]
                        detail["witness_replays"] = {row["operand"]: forward(row, payload, vector, mask, y_policy) for row in rows}
                        assert all(item["RC_C1_matches"] for item in detail["witness_replays"].values())
                        if payload == "frozen_numeric":
                            detail["control_status"] = "NEEDS_AUTHENTICATED_ORIGINAL_PAYLOAD_TRACES"
                        else:
                            if wall is None:
                                import h1603_direct_control_semantics_bank as controls
                                wall = controls.load_controls(root)
                                evidence.update(wall.evidence)
                            for control in wall.controls:
                                row = routing.make_control_row(control)
                                pair, _ = compile_operand(mdd, row, payload, mask, y_policy)
                                common = [mdd.conjunction(common[kind], pair[kind]) for kind in (0, 1)]
                                control_checks.append({"operand": row["operand"], "roots": pair, "joint_assignments": mdd.count(common[1])})
                                if common[1] == 0:
                                    break
                            detail["control_status"] = "PASS_CACHED_BANK_ONLY" if common[1] else "FALSIFIED_BY_CACHED_CONTROLS"
                            detail["control_prefix_operands"] = len(control_checks)
                    details.append(detail)
                    raw.write((json.dumps({"id": identifier, "routing_mask": mask, "Y_policy": y_policy,
                        "payload": payload, "oriented_nodes": ORIENTED, "graph": graph.NODES,
                        "nodes": mdd.nodes, "operand_order": [row["operand"] for row in checked],
                        "operand_roots": roots, "control_checks": control_checks, "final_roots": common}, separators=(",", ":"))+"\n").encode())
                    print(identifier, len(checked), detail["target_joint_assignments"], detail["control_status"], flush=True)
    all_rd = all(row["rejection_uses_only_RD"] for row in details)
    result = {"experiment": "h1614_asymmetric_multiplier_ports", "hardware_execution": "none", "selector_promotion": "none",
        "oriented_nodes": ORIENTED, "X_policy": "chop67", "Y_policies_at_64": Y_POLICIES,
        "output_policies": POLICIES, "routing_programs": 64, "policy_vectors_per_case": K**N,
        "named_programs_per_payload": 5*64*K**N, "payload_treatments": ["omitted", "frozen_numeric"],
        "actual_mode_rows": sum(len(row["authenticated_observations"]) for row in rows),
        "actual_C1_constraints": sum(len(row["actual_C1_constraints"]) for row in rows),
        "selftest": tests, "complete_disabled_port_H1608_function_checks": identity_checks,
        "direct_policy_replays": checks, "additional_rational_stage_checks": rational_checks,
        "target_survivors": survivors, "all_cases_excluded_using_only_RD": all_rd,
        "RC_only_extension": "EXCLUDED_BY_ALL_CASES_RD_CERTIFICATE" if all_rd else "NOT_SETTLED_BY_SAME_MODE_PREFIXES",
        "hypotheses": details, "rejection_prefix_histogram": dict(sorted(Counter(len(row["checked_prefix"]) for row in details if not row["target_joint_assignments"]).items())),
        "scope": "All eight multiply input pairs materialized as X=CHOP67,Y=shared conventional64; six independent fixed orientations; thirteen independently free conventional-or-exact output policies at original widths; original graph/constants/finalRC64 and absent/frozen numeric payload",
        "claim_boundary": "not a decoded physical port contract or transfer of R86/R1378 gating; not per-site/input-dependent Y policies, other X policies, changed result widths, consumer-specific power versions, different graphs/history or regenerated payload",
        "sha256": {"script": digest(Path(__file__)), "evidence": evidence, "port_diagrams": digest(raw_path)}}
    with (output/"report.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"cases": len(details), "survivors": survivors,
        "prefix_histogram": result["rejection_prefix_histogram"], "all_RD": all_rd}, sort_keys=True))


if __name__ == "__main__":
    main()
