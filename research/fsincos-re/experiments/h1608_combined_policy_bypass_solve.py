#!/usr/bin/env python3
"""Common five-policy OR exact-forwarding choices on the thirteen-cut graph.

This joins H1602 and H1607, rather than inferring the union of their negative
results excludes their combination. A node has six named choices, fixed
across inputs and RC. The diagram is a finite solver, never an input selector.
No C/hardware execution, fresh labels, payload fitting or emulator changes.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import random
from fractions import Fraction
from functools import lru_cache
from pathlib import Path

import h1602_fixed_operation_policy_solve as fixed
import h1607_exact_cut_bypass as bypass


graph, spec, V = fixed.graph, fixed.spec, fixed.V
CHOICES = (*fixed.POLICIES, "exact")
N, K = len(graph.NODES), len(CHOICES)
H1602 = "tmp/ledger33/current/h1602_fixed_operation_policy_solve"
H1607 = "tmp/ledger33/current/h1607_exact_cut_bypass_v2"
LOCKS = {
    fixed.REPORT: fixed.REPORT_SHA,
    "experiments/h1602_fixed_operation_policy_solve.py":
        "35c787a27bf25d750cf2f6f45cd29aaab6ceb5cf057ac46d8cd41227ead508da",
    "experiments/h1607_exact_cut_bypass.py":
        "7284102dccc49f891e02f698d24a067d10dfa36b79966e5089a53140b028a59d",
    H1602+"/report.json":
        "8fef73d4ff104dc7bc5d945f7c418a873f4ab6e08b3b1b660f7abdd28b1d76ba",
    H1602+"/omitted_diagram.json":
        "f8e7c984abb64735b537a1f595f25a0daaacdd98f2189a105bc61d9fdbc8e837",
    H1602+"/frozen_numeric_diagram.json":
        "ba72faa73025fb99c5812e03cd47aa59864ec10480be792663395274372a9f09",
    H1607+"/report.json":
        "11368cc368f62c54dd916b436f58dc31f70130945045fcece8c676449b7b1938",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def numerical_key(value: V) -> tuple[int, int]:
    """Drop only trailing zero bits and unused last-round metadata."""
    if not value.n:
        return 0, 0
    trailing = (abs(value.n) & -abs(value.n)).bit_length()-1
    return value.n >> trailing, value.e+trailing


def selected(exact: V, width: int, choice: int) -> V:
    return exact if choice == K-1 else fixed.rounded(exact, width, CHOICES[choice])


def live_names() -> tuple[tuple[str, ...], ...]:
    """Backward dataflow: keep every value consumed by an unexecuted node."""
    live = [set() for _ in range(N+1)]
    live[N] = {"correction"}
    for i in reversed(range(N)):
        name, _, left, right, _, _ = graph.NODES[i]
        live[i] = (live[i+1]-{name}) | {left, right}
    return tuple(tuple(sorted(names)) for names in live)


LIVE = live_names()


def compile_operand(mdd: fixed.MDD, row: dict, payload_name: str) -> tuple[tuple[int, int], dict]:
    """Exact dynamic programming over live dyadics, with all six labels kept.

    Numerical suffix memoization is valid only because this graph consumes
    values, not prior rounding metadata or operation-choice history. Those
    richer semantics are outside the family, not silently approximated here.
    """
    payload = graph.unpack(row["variants"][payload_name]["frozen_payload_signed"])
    intervals = [row["joint_RC_inverse"], row["joint_RC_C1_inverse"]]
    limits = [(Fraction(q["lower"]), Fraction(q["upper"]), q["lower_closed"], q["upper_closed"])
              for q in intervals]
    states_at_level = [0]*(N+1)
    max_numerator_bits = [0]*N
    local_branch_histograms = [{1: 0, 2: 0, 3: 0} for _ in range(N)]

    @lru_cache(None)
    def visit(level: int, values: tuple[tuple[int, int], ...]) -> tuple[int, int, int]:
        states_at_level[level] += 1
        state = {name: V(*value) for name, value in zip(LIVE[level], values)}
        if level == N:
            z = spec.exact_add(V(1, 0), state["correction"]).fraction()
            assert 0 < z < 1
            accepts = [int((z > lo or z == lo and lc) and (z < hi or z == hi and hc))
                       for lo, hi, lc, hc in limits]
            assert accepts[1] <= accepts[0]
            return accepts[0], accepts[1], 1
        node = graph.NODES[level]
        exact = graph.operation(state, node, payload)
        max_numerator_bits[level] = max(max_numerator_bits[level], abs(exact.n).bit_length())
        choice_keys = [numerical_key(selected(exact, node[4], choice)) for choice in range(K)]
        branches = {}
        for value in choice_keys:
            if value not in branches:
                state[node[0]] = V(*value)
                next_values = tuple(numerical_key(state[name]) for name in LIVE[level+1])
                branches[value] = visit(level+1, next_values)
        assert 1 <= len(branches) <= 3
        local_branch_histograms[level][len(branches)] += 1
        roots = [mdd.node(level, tuple(branches[value][kind] for value in choice_keys)) for kind in (0, 1)]
        # Suffix reuse does not erase distinct numerical prefixes. Sum once
        # per distinct local value, rather than once per equivalent policy.
        return roots[0], roots[1], sum(result[2] for result in branches.values())

    initial = graph.initial(row["operand"])
    result = visit(0, tuple(numerical_key(initial[name]) for name in LIVE[0]))
    info = visit.cache_info()
    detail = {"numerical_paths_with_common_prefix_sharing": result[2],
              "distinct_live_suffix_states": info.currsize, "reused_suffix_states": info.hits,
              "states_by_level": states_at_level, "local_numerical_branch_histograms": local_branch_histograms,
              "observed_exact_numerator_bits_not_physical_widths": max_numerator_bits,
              "output_only_assignments": mdd.count(result[0]),
              "output_and_C1_assignments": mdd.count(result[1])}
    visit.cache_clear()
    return (result[0], result[1]), detail


def project(source: fixed.MDD, root: int, target: fixed.MDD, maps: tuple[tuple[int, ...], ...]) -> int:
    """Exact per-variable choice restriction into a canonical target diagram."""
    assert len(maps) == source.variables == target.variables
    assert all(len(choices) == target.choices for choices in maps)
    @lru_cache(None)
    def visit(node):
        if node < 2:
            return node
        level, children = source.nodes[node]
        return target.node(level, tuple(visit(children[i]) for i in maps[level]))
    return visit(root)


def import_nodes(target: fixed.MDD, nodes: list) -> list[int]:
    mapping = [0, 1]
    assert nodes[:2] == [[target.variables, []], [target.variables, []]]
    for level, children in nodes[2:]:
        mapping.append(target.node(level, tuple(mapping[child] for child in children)))
    return mapping


def bypass_bitset(mdd: fixed.MDD, root: int) -> int:
    assert mdd.choices == 2 and mdd.variables == N
    accepted = 0
    for mask in range(1 << N):
        if mdd.evaluate(root, tuple((mask >> i) & 1 for i in range(N))):
            accepted |= 1 << mask
    return accepted


def forward(row: dict, payload_name: str, vector: tuple[int, ...]) -> dict:
    """Straight-line execution, without live-state memoization or diagrams."""
    assert len(vector) == N and all(0 <= choice < K for choice in vector)
    payload = graph.unpack(row["variants"][payload_name]["frozen_payload_signed"])
    state, stages = graph.initial(row["operand"]), []
    for node, choice in zip(graph.NODES, vector):
        exact = graph.operation(state, node, payload)
        value = selected(exact, node[4], choice)
        state[node[0]] = value
        stages.append({"node": node[0], "choice": CHOICES[choice], "chosen": value.record()})
    return {**bypass.constraints(row, state["correction"]), "stages": stages}


def rational_round(value: Fraction, bits: int, choice: str) -> Fraction:
    """Independent rational-grid reference for all six semantic choices."""
    if not value or choice == "exact":
        return value
    magnitude, sign = abs(value), (-1 if value < 0 else 1)
    exponent = magnitude.numerator.bit_length()-magnitude.denominator.bit_length()
    if magnitude < Fraction(2)**exponent:
        exponent -= 1
    unit = Fraction(2)**(exponent-bits+1)
    whole = magnitude // unit
    residue = magnitude-whole*unit
    up = False
    if residue:
        if choice == "away":
            up = True
        elif choice == "odd":
            up = not whole % 2
        elif choice in ("rn", "rn_away"):
            up = 2*residue > unit or (2*residue == unit and (choice == "rn_away" or whole % 2))
        else:
            assert choice == "chop"
    return sign*(whole+up)*unit


def rational_forward(operand: str, payload: V, vector: tuple[int, ...]) -> dict[str, Fraction]:
    state = {name: value.fraction() for name, value in graph.initial(operand).items()}
    for node, choice in zip(graph.NODES, vector):
        name, op, left, right, width, _ = node
        exact = state[left]*state[right] if op == "mul" else state[left]+state[right]
        if op == "add_payload":
            exact += payload.fraction()
        state[name] = rational_round(exact, width, CHOICES[choice])
    return state


def selftest() -> dict:
    tests = {"inherited_five_policy_solver": fixed.selftest()}
    checks = 0
    for n in range(-511, 512):
        for width in range(2, 9):
            value = V(n, -7)
            assert V(*numerical_key(value)).fraction() == value.fraction()
            for index, choice in enumerate(CHOICES):
                assert selected(value, width, index).fraction() == rational_round(value.fraction(), width, choice)
                checks += 1
    rng = random.Random(0x1608)
    stages_checked = 0
    for _ in range(128):
        operand = f"3ffc {rng.randrange(1 << 63, 1 << 64):016x}"
        payload = V(rng.randrange(-8, 9), -81)
        vector = tuple(rng.randrange(K) for _ in range(N))
        rational = rational_forward(operand, payload, vector)
        state = graph.initial(operand)
        for node, choice in zip(graph.NODES, vector):
            state[node[0]] = selected(graph.operation(state, node, payload), node[4], choice)
            assert state[node[0]].fraction() == rational[node[0]]
            stages_checked += 1
        all_exact = rational_forward(operand, payload, (K-1,)*N)
        x = spec.decode_external(operand).fraction()
        polynomial = sum(c.fraction()*x**(2*i) for i, c in spec.COEFFICIENTS.items())+payload.fraction()
        assert all_exact["correction"] == polynomial
    projection_checks = 0
    for _ in range(12):
        source = fixed.MDD(3, K)
        truth = {vector: rng.randrange(2) for vector in itertools.product(range(K), repeat=3)}
        def build(prefix=()):
            return (truth[prefix] if len(prefix) == 3 else
                    source.node(len(prefix), tuple(build((*prefix, choice)) for choice in range(K))))
        root = build()
        for size in (2, 5):
            target = fixed.MDD(3, size)
            maps = tuple(tuple(rng.sample(range(K), size)) for _ in range(3))
            restricted = project(source, root, target, maps)
            for assignment in itertools.product(range(size), repeat=3):
                expected = truth[tuple(maps[i][choice] for i, choice in enumerate(assignment))]
                assert target.evaluate(restricted, assignment) == bool(expected)
                projection_checks += 1
    tests.update(status="PASS", rational_quantizer_cases=checks, rational_graphs=128,
                 rational_graph_stage_cases=stages_checked, all_exact_polynomial_cases=128,
                 restriction_truth_table_cases=projection_checks)
    return tests


def core_certificate(mdd: fixed.MDD, roots: list[int], rows: list[dict], payload: str, field: str) -> dict:
    if mdd.all_of(roots):
        return {"exists": False}
    singles = [i for i, root in enumerate(roots) if root == 0]
    pair = next(((i, j) for i, j in itertools.combinations(range(len(rows)), 2)
                 if mdd.conjunction(roots[i], roots[j]) == 0), None) if not singles else None
    if singles:
        indices = [singles[0]]
    elif pair is not None:
        indices = list(pair)
    else:
        indices = list(range(len(rows)))
        for index in tuple(indices):
            trial = [i for i in indices if i != index]
            if mdd.all_of(roots[i] for i in trial) == 0:
                indices = trial
    witnesses = []
    for removed in indices:
        remaining = [i for i in indices if i != removed]
        vector = mdd.witness(mdd.all_of(roots[i] for i in remaining))
        assert vector is not None
        replays = {rows[i]["operand"]: forward(rows[i], payload, vector) for i in indices}
        assert all(replays[rows[i]["operand"]][field] for i in remaining)
        assert not replays[rows[removed]["operand"]][field]
        witnesses.append({"removed_operand": rows[removed]["operand"], "choices": [CHOICES[i] for i in vector],
                          "replays": replays})
    return {"exists": True, "operands": [rows[i]["operand"] for i in indices],
            "cardinality_minimum_proved": bool(singles) or pair is not None,
            "deletion_minimal": True, "deletion_witnesses": witnesses}


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
    prior = json.loads((root/fixed.REPORT).read_text())
    old_fixed = json.loads((root/H1602/"report.json").read_text())
    old_bypass = json.loads((root/H1607/"report.json").read_text())
    for old in (prior, old_fixed, old_bypass):
        for relative, expected in old["sha256"]["evidence"].items():
            assert digest(root/relative) == expected, relative
            assert evidence.get(relative, expected) == expected
            evidence[relative] = expected
    assert [(n[0], n[4], n[5]) for n in graph.NODES] == [(n[0], n[4], n[5]) for n in bypass.NODES]
    rows = prior["rows"]
    assert len(rows) == 36 and len({r["operand"] for r in rows}) == 36
    assert sum(len(r["authenticated_observations"]) for r in rows) == 64
    assert sum(len(r["actual_C1_constraints"]) for r in rows) == 27
    output.mkdir(parents=True)
    rng, results = random.Random(0x160800), {}
    for payload_name in ("omitted", "frozen_numeric"):
        mdd, five, binary = fixed.MDD(N, K), fixed.MDD(N, 5), fixed.MDD(N, 2)
        saved = json.loads((root/H1602/f"{payload_name}_diagram.json").read_text())
        assert saved["variables"] == list(graph.NAMES) and saved["policies"] == list(fixed.POLICIES)
        imported = import_nodes(five, saved["nodes"])
        by_operand = {r["operand"]: r for r in old_bypass["results"][payload_name]["rows"]}
        assert [r["operand"] for r in old_fixed["results"][payload_name]["rows"]] == [r["operand"] for r in rows]
        roots, details, prefix = [], [], []
        joint = [1, 1]
        replay_count = 0
        for i, row in enumerate(rows):
            pair, detail = compile_operand(mdd, row, payload_name)
            roots.append(pair)
            joint = [mdd.conjunction(joint[kind], pair[kind]) for kind in (0, 1)]
            # Canonical equality certifies every no-exact assignment, not
            # just agreement of counts or a sample of policy vectors.
            no_exact = project(mdd, pair[1], five, ((0, 1, 2, 3, 4),)*N)
            assert no_exact == imported[saved["operand_roots"][i]], row["operand"]
            ordinary_exact = tuple((fixed.POLICIES.index(node[5]), K-1) for node in graph.NODES)
            restricted_bits = []
            for kind, field in enumerate(("RC_acceptance_bitset_hex", "RC_C1_acceptance_bitset_hex")):
                restricted = project(mdd, pair[kind], binary, ordinary_exact)
                bits = bypass_bitset(binary, restricted)
                assert bits == int(by_operand[row["operand"]][field], 16), (row["operand"], field)
                restricted_bits.append(hashlib.sha256(bits.to_bytes((1 << N)//8, "little")).hexdigest())
            vectors = [tuple(rng.randrange(K) for _ in range(N)) for _ in range(64)]
            vectors.append((0,)*N)
            vectors.append((K-1,)*N)
            for candidate in (mdd.witness(pair[0]), mdd.witness(pair[1])):
                if candidate is not None:
                    vectors.append(candidate)
            for vector in vectors:
                direct = forward(row, payload_name, vector)
                assert mdd.evaluate(pair[0], vector) == direct["RC_matches"]
                assert mdd.evaluate(pair[1], vector) == direct["RC_C1_matches"]
                replay_count += 1
            detail.update(operand=row["operand"], roots=pair,
                          complete_H1602_restriction="IDENTICAL_CANONICAL_FUNCTION",
                          complete_H1607_restriction="IDENTICAL_OUTPUT_AND_OUTPUT_C1_BITSETS",
                          H1607_restriction_bitset_sha256=restricted_bits)
            details.append(detail)
            prefix.append({"operand": row["operand"], "output_only_survivors": mdd.count(joint[0]),
                           "output_and_C1_survivors": mdd.count(joint[1])})
            print(payload_name, row["operand"], detail["distinct_live_suffix_states"],
                  detail["numerical_paths_with_common_prefix_sharing"], *[mdd.count(r) for r in joint], flush=True)
        certificates = [core_certificate(mdd, [r[kind] for r in roots], rows, payload_name, field)
                        for kind, field in enumerate(("RC_matches", "RC_C1_matches"))]
        witness = mdd.witness(joint[1])
        witness_replays = None
        if witness is not None:
            witness_replays = {row["operand"]: forward(row, payload_name, witness) for row in rows}
            assert all(item["RC_C1_matches"] for item in witness_replays.values())
        diagram_path = output/f"{payload_name}_diagram.json"
        with diagram_path.open("x") as stream:
            json.dump({"choices": CHOICES, "variables": graph.NAMES, "nodes": mdd.nodes,
                       "operand_roots": roots, "joint_roots": joint}, stream, separators=(",", ":"))
            stream.write("\n")
        results[payload_name] = {"status": "UNSAT_FINITE_COMBINED_FAMILY" if joint[1] == 0 else "SAT_REQUIRES_CONTROLS",
            "output_only_common_assignments": mdd.count(joint[0]), "output_and_C1_common_assignments": mdd.count(joint[1]),
            "common_witness": None if witness is None else [CHOICES[i] for i in witness],
            "common_witness_replays": witness_replays, "rows": details, "prefix_intersections": prefix,
            "output_only_core": certificates[0], "output_and_C1_core": certificates[1],
            "diagram_nodes": len(mdd.nodes), "diagram_sha256": digest(diagram_path),
            "complete_H1602_restrictions_checked": len(rows), "complete_H1607_bitsets_checked": 2*len(rows),
            "straight_line_graph_replays": replay_count,
            "control_wall": "NOT_RUN_NO_COMMON_SURVIVOR" if witness is None else "PENDING_TARGET_SURVIVOR_NOT_A_VALIDATED_SOLUTION"}
    report = {"experiment": "h1608_combined_policy_bypass_solve", "hardware_and_C_execution": "none",
        "selector_promotion": "none", "choices": CHOICES, "nodes": graph.NODES,
        "named_assignments_per_payload": K**N, "observed_operands": len(rows),
        "actual_RC_rows": 64, "actual_C1_rows": 27, "live_values_per_level": LIVE,
        "selftest": tests, "results": results,
        "scope": "one shared six-choice vector for all inputs and RC, original finite widths or exact dyadic forwarded to all consumers, fixed graph/constants, final RC64, omitted or frozen original numeric payload",
        "claim_boundary": "finite common numerical semantics only; not arbitrary precision, edge-specific routing, changed operation graph, RC/input-dependent policies, hidden history, changed payload generation, physical forwarding recovery or general impossibility",
        "sha256": {"script": digest(Path(__file__)), "evidence": evidence}}
    with (output/"report.json").open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({name: {key: value[key] for key in ("status", "output_only_common_assignments",
                "output_and_C1_common_assignments", "diagram_nodes")} for name, value in results.items()}, sort_keys=True))


if __name__ == "__main__":
    main()
