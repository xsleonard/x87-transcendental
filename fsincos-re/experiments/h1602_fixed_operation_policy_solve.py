#!/usr/bin/env python3
"""Exhaust common operation-wide rounding policies, not per-input masks.

The five policies are fixed independently at each of H1595's thirteen cuts.
A reduced ordered multi-valued decision diagram is an exact finite solver,
not a selector to ship. No model C, hardware or unobserved label is used.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import random
from functools import lru_cache
from pathlib import Path

import h1595_coupled_faithful_reachability as graph
import h1596_rounding_mode_feasibility as rc


V, spec = graph.Value, graph.spec
POLICIES = ("chop", "rn", "rn_away", "away", "odd")
K, N = len(POLICIES), len(graph.NODES)
REPORT = "tmp/ledger33/current/h1600_joint_rc_c1_faithful_graph_v2/report.json"
REPORT_SHA = "e5d9c15ac734d6bc21d609890c3a31d581c3defe913ae8318354ab0cee8e2da6"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rounded(exact: V, bits: int, policy: str) -> V:
    if policy != "rn_away":
        return spec.quantize(exact, bits, policy)
    # RN with exact half-way cases taken away from zero. All non-ties use
    # the independently tested nearest-even quantizer unchanged.
    shift = abs(exact.n).bit_length()-bits
    if shift > 0 and abs(exact.n) % (1 << shift) == 1 << (shift-1):
        return spec.quantize(exact, bits, "away")
    return spec.quantize(exact, bits, "rn")


class MDD:
    """Canonical ordered diagram with terminals false=0 and true=1."""
    def __init__(self, variables: int, choices: int):
        self.variables, self.choices = variables, choices
        self.nodes = [(variables, ()), (variables, ())]
        self.unique = {}
        self.and_cache = {}

    def node(self, level: int, children: tuple[int, ...]) -> int:
        assert len(children) == self.choices and 0 <= level < self.variables
        if len(set(children)) == 1:
            return children[0]
        assert all(self.nodes[child][0] > level for child in children)
        key = level, children
        if key not in self.unique:
            self.unique[key] = len(self.nodes)
            self.nodes.append(key)
        return self.unique[key]

    def conjunction(self, a: int, b: int) -> int:
        a, b = sorted((a, b))
        if a == 0 or a == b:
            return a
        if a == 1:
            return b
        key = a, b
        if key in self.and_cache:
            return self.and_cache[key]
        level = min(self.nodes[a][0], self.nodes[b][0])
        ac = self.nodes[a][1] if self.nodes[a][0] == level else (a,)*self.choices
        bc = self.nodes[b][1] if self.nodes[b][0] == level else (b,)*self.choices
        result = self.node(level, tuple(self.conjunction(x, y) for x, y in zip(ac, bc)))
        self.and_cache[key] = result
        return result

    def all_of(self, roots) -> int:
        current = 1
        for root in roots:
            current = self.conjunction(current, root)
        return current

    def count(self, root: int) -> int:
        @lru_cache(None)
        def visit(node: int, start: int) -> int:
            if node < 2:
                return node*self.choices**(self.variables-start)
            level, children = self.nodes[node]
            return self.choices**(level-start)*sum(visit(child, level+1) for child in children)
        return visit(root, 0)

    def evaluate(self, root: int, values: tuple[int, ...]) -> bool:
        assert len(values) == self.variables
        while root >= 2:
            level, children = self.nodes[root]
            root = children[values[level]]
        return bool(root)

    def witness(self, root: int) -> tuple[int, ...] | None:
        if root == 0:
            return None
        values = [0]*self.variables
        while root >= 2:
            level, children = self.nodes[root]
            choice = next(i for i, child in enumerate(children) if child != 0)
            values[level], root = choice, children[choice]
        return tuple(values)


def inverse(row: dict) -> rc.Interval:
    data = row["joint_RC_C1_inverse"]
    return rc.Interval(rc.F(data["lower"]), rc.F(data["upper"]), data["lower_closed"], data["upper_closed"])


def forward(row: dict, payload_name: str, policy_vector: tuple[int, ...]) -> dict:
    payload = graph.unpack(row["variants"][payload_name]["frozen_payload_signed"])
    state = graph.initial(row["operand"])
    mask, steps = 0, []
    for index, node in enumerate(graph.NODES):
        exact = graph.operation(state, node, payload)
        chosen = rounded(exact, node[4], POLICIES[policy_vector[index]])
        ordinary = spec.quantize(exact, node[4], node[5])
        mask |= int(graph.key(chosen) != graph.key(ordinary)) << index
        state[node[0]] = chosen
        steps.append(chosen.record())
    z = spec.exact_add(V(1, 0), state["correction"]).fraction()
    outputs = {r["mode"]: spec.encode_external(spec.add(V(1, 0), state["correction"], 64, r["mode"]))
               for r in row["authenticated_observations"]}
    rc_ok = all(outputs[r["mode"]] == r["hardware"] for r in row["authenticated_observations"])
    c1_ok = all(int(spec.decode_external(r["hardware"]).fraction() > z) == r["c1"]
                for r in row["actual_C1_constraints"])
    good = rc_ok and c1_ok
    assert inverse(row).contains(z) == good
    assert good == (mask in row["variants"][payload_name]["stages"]["joint_RC_and_C1"]["all_graph"]["successful_masks"])
    return {"satisfies_RC_and_C1": good, "departure_mask": mask, "prevalue": str(z),
            "predicted_actual_modes": outputs, "stages": steps}


def compile_operand(mdd: MDD, row: dict, payload_name: str) -> tuple[int, dict]:
    payload = graph.unpack(row["variants"][payload_name]["frozen_payload_signed"])
    state = graph.initial(row["operand"])
    interval = inverse(row)
    accepted, seen = set(), set()
    signs = [set() for _ in graph.NODES]
    exact_halves = [0]*N

    def visit(index: int, mask: int) -> int:
        if index == N:
            assert mask not in seen
            seen.add(mask)
            z = spec.exact_add(V(1, 0), state["correction"]).fraction()
            good = interval.contains(z)
            if good:
                accepted.add(mask)
            return int(good)
        node = graph.NODES[index]
        name, _, _, _, bits, policy = node
        exact = graph.operation(state, node, payload)
        signs[index].add((exact.n > 0)-(exact.n < 0))
        shift = abs(exact.n).bit_length()-bits
        exact_halves[index] += int(shift > 0 and abs(exact.n) % (1 << shift) == 1 << (shift-1))
        ordinary = spec.quantize(exact, bits, policy)
        choices = [rounded(exact, bits, rule) for rule in POLICIES]
        branches = {}
        for chosen in choices:
            key = graph.key(chosen)
            if key in branches:
                continue
            state[name] = chosen
            departure = int(key != graph.key(ordinary)) << index
            branches[key] = visit(index+1, mask | departure)
        # CHOP and AWAY span both faithful numerical neighbors, even for
        # negative results. Thus policy traversal covers every H1595 path.
        assert set(branches) == {graph.key(value) for value in graph.neighbors(exact, bits)}
        del state[name]
        return mdd.node(index, tuple(branches[graph.key(chosen)] for chosen in choices))

    root = visit(0, 0)
    expected = row["variants"][payload_name]["stages"]["joint_RC_and_C1"]["all_graph"]["successful_masks"]
    assert accepted == set(expected), row["operand"]
    return root, {"faithful_paths": len(seen), "accepted_faithful_paths": len(accepted),
                  "accepted_masks_sha256": hashlib.sha256(json.dumps(sorted(accepted), separators=(",", ":")).encode()).hexdigest(),
                  "signs_by_node": [sorted(x) for x in signs], "exact_half_visits_by_node": exact_halves,
                  "accepted_fixed_policy_assignments": mdd.count(root)}


def selftest() -> dict:
    rng = random.Random(0x1602)
    checks = 0
    for _ in range(30):
        diagram = MDD(4, 3)
        grids = [[rng.randrange(2) for _ in range(81)] for _ in range(2)]
        def build(values, level=0):
            if level == 4:
                return values[0]
            size = len(values)//3
            return diagram.node(level, tuple(build(values[i*size:(i+1)*size], level+1) for i in range(3)))
        roots = [build(values) for values in grids]
        intersection = diagram.conjunction(*roots)
        assert diagram.count(roots[0]) == sum(grids[0])
        assert diagram.count(intersection) == sum(a and b for a, b in zip(*grids))
        for i, assignment in enumerate(itertools.product(range(3), repeat=4)):
            assert diagram.evaluate(intersection, assignment) == bool(grids[0][i] and grids[1][i])
            checks += 1
        witness = diagram.witness(intersection)
        assert (witness is None) == (intersection == 0)
        if witness is not None:
            assert diagram.evaluate(intersection, witness)
    tie_checks = 0
    for n in range(-511, 512):
        if n == 0:
            continue
        exact = V(n, -7)
        for bits in range(2, 8):
            low = spec.quantize(exact, bits, "chop")
            high = spec.quantize(exact, bits, "away")
            dl, dh = abs(exact.fraction()-low.fraction()), abs(exact.fraction()-high.fraction())
            expected = high if dh <= dl else low
            assert rounded(exact, bits, "rn_away").fraction() == expected.fraction()
            tie_checks += 1
    return {"status": "PASS", "MDD_truth_table_cases": checks, "independent_RN_away_neighbor_cases": tie_checks}


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
    assert not args.output_dir.exists(), "refusing existing output directory"
    assert digest(args.root/REPORT) == REPORT_SHA
    report = json.loads((args.root/REPORT).read_text())
    evidence = {REPORT: REPORT_SHA}
    for path, expected in report["sha256"]["evidence"].items():
        assert digest(args.root/path) == expected, path
        evidence[path] = expected
    assert digest(args.root/"experiments/h1600_joint_rc_c1_faithful_graph.py") == report["sha256"]["script"]
    evidence["experiments/h1600_joint_rc_c1_faithful_graph.py"] = report["sha256"]["script"]
    args.output_dir.mkdir(parents=True)
    rows = report["rows"]
    rng = random.Random(0x160200)
    results = {}
    for payload_name in ("omitted", "frozen_numeric"):
        mdd = MDD(N, K)
        roots, details, prefix = [], [], []
        joint = 1
        direct_checks = 0
        for row in rows:
            root, detail = compile_operand(mdd, row, payload_name)
            assert root != 0
            roots.append(root)
            joint = mdd.conjunction(joint, root)
            detail.update(operand=row["operand"], root=root)
            details.append(detail)
            prefix.append({"operand": row["operand"], "surviving_assignments": mdd.count(joint)})
            # Independent straight-line replay against actual outputs/C1,
            # as well as the previously authenticated successful path set.
            for _ in range(128):
                vector = tuple(rng.randrange(K) for _ in range(N))
                direct = forward(row, payload_name, vector)
                assert mdd.evaluate(root, vector) == direct["satisfies_RC_and_C1"]
                direct_checks += 1
            print(payload_name, row["operand"], detail["accepted_fixed_policy_assignments"], mdd.count(joint), flush=True)
        pairs = [(i, j) for i in range(len(rows)) for j in range(i+1, len(rows))
                 if mdd.conjunction(roots[i], roots[j]) == 0]
        core, deletion_witnesses = [], []
        if joint == 0:
            if pairs:
                core = list(pairs[0])
            else:
                core = list(range(len(rows)))
                for index in list(core):
                    trial = [i for i in core if i != index]
                    if mdd.all_of(roots[i] for i in trial) == 0:
                        core = trial
            assert mdd.all_of(roots[i] for i in core) == 0
            for removed in core:
                remaining = [i for i in core if i != removed]
                witness = mdd.witness(mdd.all_of(roots[i] for i in remaining))
                assert witness is not None
                replays = {rows[i]["operand"]: forward(rows[i], payload_name, witness) for i in core}
                assert all(replays[rows[i]["operand"]]["satisfies_RC_and_C1"] for i in remaining)
                assert not replays[rows[removed]["operand"]]["satisfies_RC_and_C1"]
                deletion_witnesses.append({"removed_operand": rows[removed]["operand"],
                    "policies": [POLICIES[x] for x in witness], "replays": replays})
        witness = mdd.witness(joint)
        if witness is not None:
            assert all(forward(row, payload_name, witness)["satisfies_RC_and_C1"] for row in rows)
        diagram_path = args.output_dir/f"{payload_name}_diagram.json"
        with diagram_path.open("x") as target:
            json.dump({"policies": POLICIES, "variables": graph.NAMES, "nodes": mdd.nodes,
                       "operand_roots": roots, "joint_root": joint}, target, separators=(",", ":"))
            target.write("\n")
        results[payload_name] = {"common_fixed_policy_assignments": mdd.count(joint),
            "status": "UNSAT_FINITE_POLICY_FAMILY" if joint == 0 else "SAT_REQUIRES_CONTROL_WALL",
            "common_witness": None if witness is None else [POLICIES[x] for x in witness],
            "rows": details, "prefix_intersections": prefix,
            "contradictory_pairs": [[rows[i]["operand"], rows[j]["operand"]] for i, j in pairs],
            "irreducible_core": [rows[i]["operand"] for i in core],
            "core_is_cardinality_minimum": bool(pairs), "core_deletion_witnesses": deletion_witnesses,
            "diagram_nodes": len(mdd.nodes), "diagram_sha256": digest(diagram_path),
            "independent_full_graph_policy_replays": direct_checks}
    result = {"experiment": "h1602_fixed_operation_policy_solve", "hardware_execution": "none",
        "C_execution": "none", "selector_promotion": "none", "policies": POLICIES,
        "nodes": graph.NODES, "assignments_per_payload": K**N,
        "observed_operands": len(rows), "actual_RC_rows": report["authenticated_joint_RC_rows"],
        "actual_C1_rows": report["actual_C1_rows"], "selftest": checks, "results": results,
        "claim_boundary": "fixed thirteen-cut graph and widths, one fixed listed rounding policy per operation across all inputs and RC, omitted or original numeric payload; does not exclude input/control-dependent policies, different widths, graph, payload or silicon semantics",
        "sha256": {"script": digest(Path(__file__)), "evidence": evidence}}
    with (args.output_dir/"report.json").open("x") as target:
        json.dump(result, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps({name: {key: data[key] for key in ("status", "common_fixed_policy_assignments", "irreducible_core", "diagram_nodes")}
                      for name, data in results.items()}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
