#!/usr/bin/env python3
"""One changed materialization width, all common operation policies free.

Each hypothesis changes one cut to 64..72 bits or exact forwarding. All
thirteen per-node choices among the H1602 five policies are still globally
free, not fixed to their ordinary setting. A rejection prefix is sufficient
to falsify that hypothesis; no best-fit predicate or unseen label is used.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import random
from pathlib import Path

import h1602_fixed_operation_policy_solve as fixed


graph, spec, V = fixed.graph, fixed.spec, fixed.V
POLICIES = fixed.POLICIES
ORIGINAL = tuple(node[4] for node in graph.NODES)
LOCKS = {
    "experiments/h1602_fixed_operation_policy_solve.py":
        "35c787a27bf25d750cf2f6f45cd29aaab6ceb5cf057ac46d8cd41227ead508da",
    "tmp/ledger33/current/h1602_fixed_operation_policy_solve/report.json":
        "8fef73d4ff104dc7bc5d945f7c418a873f4ab6e08b3b1b660f7abdd28b1d76ba",
    "tmp/ledger33/current/h1600_joint_rc_c1_faithful_graph_v2/report.json":
        "e5d9c15ac734d6bc21d609890c3a31d581c3defe913ae8318354ab0cee8e2da6",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def forward(row: dict, payload_name: str, widths: tuple, vector: tuple[int, ...]) -> dict:
    payload = graph.unpack(row["variants"][payload_name]["frozen_payload_signed"])
    state = graph.initial(row["operand"])
    for node, width, choice in zip(graph.NODES, widths, vector):
        exact = graph.operation(state, node, payload)
        state[node[0]] = exact if width is None else fixed.rounded(exact, width, POLICIES[choice])
    z = spec.exact_add(V(1, 0), state["correction"]).fraction()
    outputs = {r["mode"]: spec.encode_external(spec.add(V(1, 0), state["correction"], 64, r["mode"]))
               for r in row["authenticated_observations"]}
    rc_ok = all(outputs[r["mode"]] == r["hardware"] for r in row["authenticated_observations"])
    c1_ok = all(int(spec.decode_external(r["hardware"]).fraction() > z) == r["c1"]
                for r in row["actual_C1_constraints"])
    good = rc_ok and c1_ok
    assert good == fixed.inverse(row).contains(z)
    return {"accepted": good, "prevalue": str(z), "outputs": outputs}


def compile_operand(mdd: fixed.MDD, row: dict, payload_name: str, widths: tuple) -> tuple[int, int]:
    state = graph.initial(row["operand"])
    payload = graph.unpack(row["variants"][payload_name]["frozen_payload_signed"])
    interval = fixed.inverse(row)
    leaves = 0

    def visit(index: int) -> int:
        nonlocal leaves
        if index == len(graph.NODES):
            leaves += 1
            z = spec.exact_add(V(1, 0), state["correction"]).fraction()
            return int(interval.contains(z))
        node = graph.NODES[index]
        width = widths[index]
        exact = graph.operation(state, node, payload)
        choices = [exact]*len(POLICIES) if width is None else [fixed.rounded(exact, width, p) for p in POLICIES]
        branches = {}
        for value in choices:
            key = graph.key(value)
            if key not in branches:
                state[node[0]] = value
                branches[key] = visit(index+1)
        assert len(branches) <= (1 if width is None else 2)
        del state[node[0]]
        return mdd.node(index, tuple(branches[graph.key(value)] for value in choices))

    return visit(0), leaves


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    assert not args.output_dir.exists(), "refusing existing output directory"
    reports, evidence = {}, {}
    for path, expected in LOCKS.items():
        assert digest(args.root/path) == expected
        evidence[path] = expected
        if path.endswith(".json"):
            reports[path] = json.loads((args.root/path).read_text())
    old = reports["tmp/ledger33/current/h1602_fixed_operation_policy_solve/report.json"]
    joint = reports["tmp/ledger33/current/h1600_joint_rc_c1_faithful_graph_v2/report.json"]
    for path, expected in old["sha256"]["evidence"].items():
        assert digest(args.root/path) == expected, path
        evidence[path] = expected
    rows = joint["rows"]
    first = ("3ffc de3ffffc8c13c97c", "3ffc e73ffffd2c52df71",
             "3ffc b0000000044ca2bf", "3ffc cdcc0585c940196f")
    ordered = sorted(rows, key=lambda r: (first.index(r["operand"]) if r["operand"] in first else 4, r["operand"]))
    tests = fixed.selftest()
    rng = random.Random(0x1606)
    # Before varying widths, this independent parameterized traversal must
    # reproduce every saved H1602 per-operand policy count at original widths.
    baseline = []
    for payload_name in ("omitted", "frozen_numeric"):
        mdd = fixed.MDD(len(ORIGINAL), len(POLICIES))
        counts = {r["operand"]: r["accepted_fixed_policy_assignments"] for r in old["results"][payload_name]["rows"]}
        for row in rows:
            root, _ = compile_operand(mdd, row, payload_name, ORIGINAL)
            assert mdd.count(root) == counts[row["operand"]]
            baseline.append((payload_name, row["operand"], counts[row["operand"]]))
    args.output_dir.mkdir(parents=True)
    raw_path = args.output_dir/"hypothesis_diagrams.jsonl.gz"
    details, survivors = [], []
    replay_count = 0
    with raw_path.open("xb") as raw_file, gzip.GzipFile(fileobj=raw_file, mode="wb", filename="", mtime=0) as raw:
        for index, node in enumerate(graph.NODES):
            for width in (*range(64, 73), None):
                if width == ORIGINAL[index]:
                    continue
                widths = list(ORIGINAL)
                widths[index] = width
                widths = tuple(widths)
                for payload_name in ("omitted", "frozen_numeric"):
                    mdd = fixed.MDD(len(ORIGINAL), len(POLICIES))
                    common = 1
                    checked, roots = [], []
                    total_leaves = 0
                    for row in ordered:
                        root, leaves = compile_operand(mdd, row, payload_name, widths)
                        total_leaves += leaves
                        roots.append(root)
                        common = mdd.conjunction(common, root)
                        checked.append({"operand": row["operand"], "accepted_assignments": mdd.count(root),
                                        "joint_prefix_assignments": mdd.count(common)})
                        vectors = [tuple(rng.randrange(len(POLICIES)) for _ in ORIGINAL) for _ in range(8)]
                        witness = mdd.witness(root)
                        if witness is not None:
                            vectors.append(witness)
                        for vector in vectors:
                            assert mdd.evaluate(root, vector) == forward(row, payload_name, widths, vector)["accepted"]
                            replay_count += 1
                        if common == 0:
                            break
                    identifier = f"{node[0]}:{'exact' if width is None else width}:{payload_name}"
                    record = {"id": identifier, "changed_node": node[0], "width": width, "payload": payload_name,
                              "checked_prefix": checked, "numeric_leaves": total_leaves,
                              "common_policy_assignments": mdd.count(common), "diagram_nodes": len(mdd.nodes),
                              "status": "UNSAT_PREFIX" if common == 0 else "SAT_TARGETS_REQUIRES_CONTROLS"}
                    if common != 0:
                        assert len(checked) == len(rows)
                        vector = mdd.witness(common)
                        record["witness_policies"] = [POLICIES[p] for p in vector]
                        record["witness_replays"] = {r["operand"]: forward(r, payload_name, widths, vector) for r in rows}
                        assert all(r["accepted"] for r in record["witness_replays"].values())
                        survivors.append(identifier)
                    details.append(record)
                    raw.write((json.dumps({"id": identifier, "widths": widths, "policies": POLICIES,
                        "operand_order": [r["operand"] for r in checked], "nodes": mdd.nodes,
                        "operand_roots": roots, "joint_root": common}, separators=(",", ":"))+"\n").encode())
                    print(identifier, len(checked), record["common_policy_assignments"], flush=True)
    assert len(details) == 234
    result = {"experiment": "h1606_single_width_policy_solve", "hardware_execution": "none", "C_execution": "none",
        "selector_promotion": "none", "observed_operands": len(rows), "actual_RC_rows": joint["authenticated_joint_RC_rows"],
        "actual_C1_rows": joint["actual_C1_rows"], "original_widths": ORIGINAL, "policies": POLICIES,
        "alternative_widths": [*range(64, 73), "exact"], "changed_width_hypotheses_per_payload": 117,
        "baseline_per_operand_count_checks": len(baseline), "selftest": tests,
        "independent_direct_policy_replays": replay_count, "survivors": survivors, "hypotheses": details,
        "scope": "one globally changed node width only; all other widths original but every per-node conventional policy free across inputs; exact forwards entire numerical value to every consumer; final RC64; absent or original numeric payload",
        "claim_boundary": "finite width/graph family; exact bypass is a mathematical retention hypothesis, not proven physical forwarding; no multiple simultaneous width changes, input-dependent control, changed coefficient values or novel graph",
        "sha256": {"script": digest(Path(__file__)), "evidence": evidence, "hypothesis_diagrams": digest(raw_path)}}
    with (args.output_dir/"report.json").open("x") as target:
        json.dump(result, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps({"hypotheses": len(details), "survivors": survivors}, sort_keys=True))


if __name__ == "__main__":
    main()
