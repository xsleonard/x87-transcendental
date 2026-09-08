#!/usr/bin/env python3
"""Consumer-specific raw/materialized square and fourth-power forwarding.

Seven fixed routing bits split power fan-out; all thirteen operation choices
remain free among five conventional policies or exact forwarding. Routing
and policies are common across inputs and RC. Raw means exact numerical
dyadic, not a claim about a decoded physical bypass bus or its finite width.
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


fixed, graph, spec, V = base.fixed, base.graph, base.spec, base.V
N, K, POLICIES = base.N, base.K, base.CHOICES
ROUTES = (("square", "fourth"), ("square", "left"),
          ("fourth", "negative_mul1"), ("fourth", "negative_mul2"),
          ("fourth", "positive_mul1"), ("fourth", "positive_mul2"), ("fourth", "right"))
PARENT = "tmp/ledger33/current/h1608_combined_policy_bypass_solve"
LOCKS = {
    PARENT+"/report.json": "842bd5ff9c73c8e8e3dd4dedeb5874df86f01501c8d45d899554e80857cb4ec4",
    "experiments/h1608_combined_policy_bypass_solve.py":
        "498746dcc91a35b326785af800cbc864b4ad5f53e4d801d89f3136c474e829f6",
    "experiments/h1603_direct_control_semantics_bank.py":
        "87283b4b84b921314ce892507d156b563e5354009f13f58145720aadd53fc5d0",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def routed_nodes(mask: int) -> tuple:
    assert 0 <= mask < 1 << len(ROUTES)
    nodes = []
    for node in graph.NODES:
        name, kind, left, right, bits, ordinary = node
        for index, (producer, consumer) in enumerate(ROUTES):
            if name == consumer and mask & (1 << index):
                left = producer+"_raw" if left == producer else left
                right = producer+"_raw" if right == producer else right
        # The fourth operation is still a square, not a mixed raw/rounded
        # product: its two uses of square always select the same version.
        if name == "fourth":
            assert left == right
        nodes.append((name, kind, left, right, bits, ordinary))
    return tuple(nodes)


def liveness(nodes: tuple) -> tuple[tuple[str, ...], ...]:
    live = [set() for _ in range(N+1)]
    live[N] = {"correction"}
    for index in reversed(range(N)):
        name, _, left, right, _, _ = nodes[index]
        written = {name, name+"_raw"} if name in ("square", "fourth") else {name}
        live[index] = (live[index+1]-written) | {left, right}
    return tuple(tuple(sorted(names)) for names in live)


def compile_operand(mdd: fixed.MDD, row: dict, payload_name: str, mask: int) -> tuple[tuple[int, int], dict]:
    nodes = routed_nodes(mask)
    live = liveness(nodes)
    payload = graph.unpack(row["variants"][payload_name]["frozen_payload_signed"])
    bounds = [(Fraction(q["lower"]), Fraction(q["upper"]), q["lower_closed"], q["upper_closed"])
              for q in (row["joint_RC_inverse"], row["joint_RC_C1_inverse"])]

    @lru_cache(None)
    def visit(index: int, values: tuple[tuple[int, int], ...]) -> tuple[int, int, int]:
        state = {name: V(*value) for name, value in zip(live[index], values)}
        if index == N:
            z = spec.exact_add(V(1, 0), state["correction"]).fraction()
            assert 0 < z < 1
            accepts = [int((z > lo or z == lo and lc) and (z < hi or z == hi and hc))
                       for lo, hi, lc, hc in bounds]
            assert accepts[1] <= accepts[0]
            return accepts[0], accepts[1], 1
        node = nodes[index]
        exact = graph.operation(state, node, payload)
        if node[0] in ("square", "fourth"):
            state[node[0]+"_raw"] = exact
        choices = [base.numerical_key(base.selected(exact, node[4], policy)) for policy in range(K)]
        branches = {}
        for value in choices:
            if value not in branches:
                state[node[0]] = V(*value)
                next_values = tuple(base.numerical_key(state[name]) for name in live[index+1])
                branches[value] = visit(index+1, next_values)
        assert 1 <= len(branches) <= 3
        roots = [mdd.node(index, tuple(branches[value][kind] for value in choices)) for kind in (0, 1)]
        return roots[0], roots[1], sum(result[2] for result in branches.values())

    state = graph.initial(row["operand"])
    result = visit(0, tuple(base.numerical_key(state[name]) for name in live[0]))
    info = visit.cache_info()
    stats = {"numerical_paths": result[2], "live_states": info.currsize, "suffix_reuses": info.hits}
    visit.cache_clear()
    return (result[0], result[1]), stats


def forward_values(operand: str, payload: V, policies: tuple[int, ...], mask: int) -> tuple[V, list]:
    state, stages = graph.initial(operand), []
    for node, policy in zip(routed_nodes(mask), policies):
        exact = graph.operation(state, node, payload)
        if node[0] in ("square", "fourth"):
            state[node[0]+"_raw"] = exact
        state[node[0]] = base.selected(exact, node[4], policy)
        stages.append({"node": node[0], "input_sources": node[2:4], "policy": POLICIES[policy],
                       "raw_result": exact.record(), "selected_result": state[node[0]].record()})
    return state["correction"], stages


def forward(row: dict, payload_name: str, policies: tuple[int, ...], mask: int) -> dict:
    payload = graph.unpack(row["variants"][payload_name]["frozen_payload_signed"])
    correction, stages = forward_values(row["operand"], payload, policies, mask)
    return {**base.bypass.constraints(row, correction), "stages": stages}


def rational_forward(operand: str, payload: V, policies: tuple[int, ...], mask: int) -> dict:
    """Explicit independent dataflow spelling, not routed_nodes/liveness."""
    x = spec.decode_external(operand).fraction()
    c = {i: value.fraction() for i, value in spec.COEFFICIENTS.items()}
    raw, chosen = {}, {}
    def materialize(index, value):
        name = graph.NAMES[index]
        raw[name] = value
        chosen[name] = base.rational_round(value, graph.NODES[index][4], POLICIES[policies[index]])
        return chosen[name]
    def power(name, bit):
        return raw[name] if mask & (1 << bit) else chosen[name]
    materialize(0, x*x)
    s = power("square", 0)
    materialize(1, s*s)
    materialize(2, power("fourth", 2)*c[5])
    materialize(3, c[3]+chosen["negative_mul1"])
    materialize(4, power("fourth", 3)*chosen["negative_add1"])
    materialize(5, c[1]+chosen["negative_mul2"])
    materialize(6, power("fourth", 4)*c[6])
    materialize(7, c[4]+chosen["positive_mul1"])
    materialize(8, power("fourth", 5)*chosen["positive_add1"])
    materialize(9, c[2]+chosen["positive_mul2"])
    materialize(10, power("square", 1)*chosen["negative_factor"])
    materialize(11, power("fourth", 6)*chosen["positive_factor"])
    materialize(12, chosen["left"]+chosen["right"]+payload.fraction())
    return chosen


def cofactor(mdd: fixed.MDD, root: int, pins: dict[int, int]) -> int:
    @lru_cache(None)
    def visit(node):
        if node < 2:
            return node
        level, children = mdd.nodes[node]
        if level in pins:
            return visit(children[pins[level]])
        return mdd.node(level, tuple(visit(child) for child in children))
    return visit(root)


def selftest() -> dict:
    tests = base.selftest()
    rng = random.Random(0x1613)
    graph_checks = exact_checks = 0
    for mask in range(1 << len(ROUTES)):
        operand = f"3ffc {rng.randrange(1 << 63, 1 << 64):016x}"
        payload = V(rng.randrange(-8, 9), -81)
        vector = tuple(rng.randrange(K) for _ in range(N))
        _, stages = forward_values(operand, payload, vector, mask)
        reference = rational_forward(operand, payload, vector, mask)
        for stage in stages:
            assert graph.unpack(stage["selected_result"]).fraction() == reference[stage["node"]]
            graph_checks += 1
        # If the selected square and fourth are themselves exact, every
        # raw/materialized fan-out choice must collapse to the old graph.
        vector = (K-1, K-1, *vector[2:])
        correction, _ = forward_values(operand, payload, vector, mask)
        state = graph.initial(operand)
        for node, choice in zip(graph.NODES, vector):
            state[node[0]] = base.selected(graph.operation(state, node, payload), node[4], choice)
        assert correction.fraction() == state["correction"].fraction()
        exact_checks += 1
    # Check variable pinning independently against exhaustive small grids.
    pin_checks = 0
    for _ in range(12):
        mdd = fixed.MDD(4, 3)
        values = [rng.randrange(2) for _ in range(81)]
        def build(level, start):
            if level == 4:
                return values[start]
            stride = 3**(3-level)
            return mdd.node(level, tuple(build(level+1, start+i*stride) for i in range(3)))
        root = build(0, 0)
        pins = {0: rng.randrange(3), 2: rng.randrange(3)}
        pinned = cofactor(mdd, root, pins)
        for index in range(81):
            vector = tuple((index // 3**(3-level)) % 3 for level in range(4))
            modified = tuple(pins.get(level, value) for level, value in enumerate(vector))
            assert mdd.evaluate(pinned, vector) == mdd.evaluate(root, modified)
            pin_checks += 1
    return {"inherited_tests": tests, "rational_routing_stage_checks": graph_checks,
            "all_route_exact_power_boundary_checks": exact_checks, "cofactor_truth_table_checks": pin_checks,
            "status": "PASS"}


def make_control_row(control) -> dict:
    observations = [{"mode": mode, "hardware": control.hardware(mode)} for mode in fixed.rc.MODES]
    interval = fixed.rc.inverse(observations[0]["hardware"], observations[0]["mode"])
    for row in observations[1:]:
        interval = interval.intersect(fixed.rc.inverse(row["hardware"], row["mode"]))
    return {"operand": control.operand, "authenticated_observations": observations, "actual_C1_constraints": [],
            "joint_RC_inverse": interval.json(), "joint_RC_C1_inverse": interval.json(),
            "variants": {"omitted": {"frozen_payload_signed": V(0, 0).record()}}}


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
    for relative, expected in LOCKS.items():
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
    old_diagrams, old_row_indices = {}, {row["operand"]: i for i, row in enumerate(rows)}
    coupled_checks = 0
    for payload in ("omitted", "frozen_numeric"):
        relative = PARENT+f"/{payload}_diagram.json"
        expected = prior["results"][payload]["diagram_sha256"]
        assert digest(root/relative) == expected
        evidence[relative] = expected
        saved = json.loads((root/relative).read_text())
        old_diagrams[payload] = saved
        mdd = fixed.MDD(N, K)
        imported = base.import_nodes(mdd, saved["nodes"])
        for i, row in enumerate(rows):
            pair, _ = compile_operand(mdd, row, payload, 0)
            assert list(pair) == [imported[r] for r in saved["operand_roots"][i]]
            coupled_checks += 2
    output.mkdir(parents=True)
    raw_path = output/"routing_diagrams.jsonl.gz"
    rng, details, target_survivors, control_survivors = random.Random(0x161300), [], [], []
    direct_checks = exact_restrictions = 0
    wall = None
    with raw_path.open("xb") as raw_file, gzip.GzipFile(fileobj=raw_file, mode="wb", filename="", mtime=0) as raw:
        for mask in range(1 << len(ROUTES)):
            for payload in ("omitted", "frozen_numeric"):
                saved = old_diagrams[payload]
                mdd = fixed.MDD(N, K)
                imported = base.import_nodes(mdd, saved["nodes"])
                common, checked, roots = [1, 1], [], []
                for row in ordered:
                    pair, stats = compile_operand(mdd, row, payload, mask)
                    roots.append(pair)
                    common = [mdd.conjunction(common[kind], pair[kind]) for kind in (0, 1)]
                    old_pair = saved["operand_roots"][old_row_indices[row["operand"]]]
                    for kind in (0, 1):
                        assert cofactor(mdd, pair[kind], {0: K-1, 1: K-1}) == cofactor(mdd, imported[old_pair[kind]], {0: K-1, 1: K-1})
                        exact_restrictions += 1
                    vectors = [tuple(rng.randrange(K) for _ in range(N)) for _ in range(16)]
                    vectors.extend(value for value in (mdd.witness(pair[0]), mdd.witness(pair[1])) if value is not None)
                    for vector in vectors:
                        numerical = forward(row, payload, vector, mask)
                        assert mdd.evaluate(pair[0], vector) == numerical["RC_matches"]
                        assert mdd.evaluate(pair[1], vector) == numerical["RC_C1_matches"]
                        direct_checks += 1
                    checked.append({"operand": row["operand"], **stats,
                                    "output_only_prefix_assignments": mdd.count(common[0]),
                                    "joint_prefix_assignments": mdd.count(common[1])})
                    if common[1] == 0:
                        break
                identifier = f"route{mask:03d}:{payload}"
                record = {"id": identifier, "routing_mask": mask, "raw_consumer_routes": [ROUTES[i] for i in range(len(ROUTES)) if mask & (1 << i)],
                    "payload": payload, "checked_prefix": checked, "target_joint_assignments": mdd.count(common[1]),
                    "output_only_rejection_proved": common[0] == 0,
                    "rejection_uses_only_RD": common[0] == 0 and all({o["mode"] for o in row["authenticated_observations"]} == {"rd"} for row in ordered[:len(checked)]),
                    "status": "UNSAT_OBSERVED_PREFIX" if common[1] == 0 else "SAT_TARGETS_REQUIRES_CONTROLS"}
                control_checks = []
                if common[1]:
                    assert len(checked) == len(rows)
                    target_survivors.append(identifier)
                    vector = mdd.witness(common[1])
                    record["witness_policies"] = [POLICIES[i] for i in vector]
                    record["witness_replays"] = {row["operand"]: forward(row, payload, vector, mask) for row in rows}
                    assert all(item["RC_C1_matches"] for item in record["witness_replays"].values())
                    if payload == "frozen_numeric":
                        record["control_status"] = "NEEDS_AUTHENTICATED_ORIGINAL_NUMERIC_PAYLOAD_TRACES_NO_FABRICATION"
                    else:
                        if wall is None:
                            import h1603_direct_control_semantics_bank as controls
                            wall = controls.load_controls(root)
                            evidence.update(wall.evidence)
                        for control in wall.controls:
                            row = make_control_row(control)
                            pair, _ = compile_operand(mdd, row, payload, mask)
                            common = [mdd.conjunction(common[kind], pair[kind]) for kind in (0, 1)]
                            control_checks.append({"operand": control.operand, "roots": pair, "joint_assignments": mdd.count(common[1])})
                            if common[1] == 0:
                                break
                        survived = common[1] != 0
                        record["control_status"] = "PASS_CACHED_BANK_ONLY" if survived else "FALSIFIED_BY_CACHED_CONTROLS"
                        record["control_prefix_operands"] = len(control_checks)
                        if survived:
                            control_survivors.append(identifier)
                            record["control_surviving_policies"] = [POLICIES[i] for i in mdd.witness(common[1])]
                else:
                    record["control_status"] = "NOT_RUN_NO_TARGET_SURVIVOR"
                details.append(record)
                raw.write((json.dumps({"id": identifier, "routes": ROUTES, "routing_mask": mask, "policies": POLICIES,
                    "routed_graph": routed_nodes(mask), "operand_order": [row["operand"] for row in checked],
                    "nodes": mdd.nodes, "operand_roots": roots, "control_checks": control_checks,
                    "final_roots": common}, separators=(",", ":"))+"\n").encode())
                print(identifier, len(checked), record["target_joint_assignments"], record["control_status"], flush=True)
    report = {"experiment": "h1613_split_power_forwarding", "C_or_hardware_execution": "none", "selector_promotion": "none",
        "routes": ROUTES, "routing_programs_per_payload": 1 << len(ROUTES), "policies": POLICIES,
        "policy_vectors_per_routing_program": K**N, "named_programs_per_payload": (1 << len(ROUTES))*K**N,
        "observed_operands": len(rows), "actual_mode_rows": 64, "actual_C1_constraints": 27,
        "selftest": tests, "complete_coupled_H1608_function_checks": coupled_checks,
        "complete_exact_power_cofactor_checks": exact_restrictions, "direct_full_graph_replays": direct_checks,
        "target_survivors": target_survivors, "cached_control_survivors": control_survivors,
        "rejection_prefix_histogram": dict(sorted(Counter(len(row["checked_prefix"]) for row in details if not row["target_joint_assignments"]).items())),
        "all_routes_excluded_using_only_RD": all(row["rejection_uses_only_RD"] for row in details),
        "hypotheses": details,
        "scope": "seven independent raw/materialized power consumer routes, with common13node conventional-or-exact policies; raw fourth is square of the selected square source, both fourth input legs tied; fixed original widths/graph/constants, finalRC64, absent/frozen numeric payload",
        "claim_boundary": "not decoded physical bypass, arbitrary per-cut widths, RC/input-dependent routing or policies, mixed fourth input legs, different graphs/history/nonstandard arithmetic or regenerated payload; sufficient prefixes are not claimed full-bank scores or minimum cores",
        "sha256": {"script": digest(Path(__file__)), "evidence": evidence, "routing_diagrams": digest(raw_path)}}
    with (output/"report.json").open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"programs": len(details), "survivors": target_survivors,
                      "prefix_histogram": report["rejection_prefix_histogram"]}, sort_keys=True))


if __name__ == "__main__":
    main()
