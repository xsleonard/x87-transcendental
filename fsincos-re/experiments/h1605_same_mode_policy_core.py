#!/usr/bin/env python3
"""Direct numerical-path/cube certificate for the same-RD policy conflict.

No MDD construction or conjunction is imported. Complete numeric paths
partition policy-vector space into disjoint Cartesian policy sets. A compact
four-policy-variable predicate is verified on every member of each projection.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path

import h1595_coupled_faithful_reachability as graph


spec, V = graph.spec, graph.Value
POLICIES = ("chop", "rn", "rn_away", "away", "odd")
T = {"rn", "rn_away", "away"}
Z = {"chop", "odd"}
OPERANDS = ("3ffc de3ffffc8c13c97c", "3ffc e73ffffd2c52df71")
ACTIVE = (0, 5, 10, 12)
LOCKS = {
    "tmp/ledger33/current/h1600_joint_rc_c1_faithful_graph_v2/report.json":
        "e5d9c15ac734d6bc21d609890c3a31d581c3defe913ae8318354ab0cee8e2da6",
    "tmp/ledger33/current/h1602_fixed_operation_policy_solve/report.json":
        "8fef73d4ff104dc7bc5d945f7c418a873f4ab6e08b3b1b660f7abdd28b1d76ba",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def policy_value(exact: V, bits: int, policy: str) -> V:
    if policy != "rn_away":
        return spec.quantize(exact, bits, policy)
    # Select between the two representable magnitude neighbors by exact
    # rational distance, breaking ties toward the larger magnitude.
    low = spec.quantize(exact, bits, "chop")
    high = spec.quantize(exact, bits, "away")
    dl = abs(exact.fraction()-low.fraction())
    dh = abs(exact.fraction()-high.fraction())
    return high if dh <= dl else low


def predicate(operand: str, policies: tuple[str, ...]) -> bool:
    square, negative, left, correction = policies
    if operand == OPERANDS[0]:
        return negative in Z or (square in Z and left in Z and correction == "chop")
    assert operand == OPERANDS[1]
    return negative in T and (square == "away" or left in T or correction != "chop")


def verify_operand(row: dict, payload_name: str, expected_count: int) -> dict:
    operand = row["operand"]
    observations = row["authenticated_observations"]
    assert len(observations) == 1 and observations[0]["mode"] == "rd"
    hardware = observations[0]["hardware"]
    statuses = row["actual_C1_constraints"]
    assert len(statuses) == 1 and statuses[0]["mode"] == "rd" and statuses[0]["c1"] == 0
    payload = graph.unpack(row["variants"][payload_name]["frozen_payload_signed"])
    state = graph.initial(operand)
    cube = [None]*len(graph.NODES)
    total_volume = accepted_volume = projection_checks = path_count = 0
    accepted_masks = set()
    witness = None

    def visit(index: int, mask: int) -> None:
        nonlocal total_volume, accepted_volume, projection_checks, path_count, witness
        if index == len(graph.NODES):
            path_count += 1
            output = spec.add(V(1, 0), state["correction"], 64, "rd")
            endpoint = spec.encode_external(output)
            before = spec.exact_add(V(1, 0), state["correction"])
            assert before.n > 0 and output.n > 0
            c1 = int(output.fraction() > before.fraction())
            assert c1 == 0
            good = endpoint == hardware
            volume = math.prod(len(options) for options in cube)
            assert volume > 0
            total_volume += volume
            accepted_volume += volume*good
            if good:
                accepted_masks.add(mask)
                if witness is None:
                    witness = {"policies": [options[0] for options in cube], "endpoint": endpoint,
                               "prevalue": str(before.fraction()), "departure_mask": mask}
            # Every unlisted policy variable is free within this full leaf
            # cube, so checking its four-variable projection covers them all.
            for policies in itertools.product(*(cube[i] for i in ACTIVE)):
                assert predicate(operand, policies) == good, (operand, payload_name, mask, policies)
                projection_checks += 1
            return
        node = graph.NODES[index]
        exact = graph.operation(state, node, payload)
        ordinary = spec.quantize(exact, node[4], node[5])
        choices = graph.neighbors(exact, node[4])
        policy_outputs = {p: graph.key(policy_value(exact, node[4], p)) for p in POLICIES}
        seen = set()
        for chosen in choices:
            key = graph.key(chosen)
            options = tuple(p for p in POLICIES if policy_outputs[p] == key)
            assert options and not seen.intersection(options)
            seen.update(options)
            cube[index] = options
            state[node[0]] = chosen
            visit(index+1, mask | (int(key != graph.key(ordinary)) << index))
        assert seen == set(POLICIES)
        del state[node[0]]

    visit(0, 0)
    expected_masks = row["variants"][payload_name]["stages"]["joint_RC_and_C1"]["all_graph"]["successful_masks"]
    assert accepted_masks == set(expected_masks)
    assert total_volume == 5**13 and accepted_volume == expected_count > 0
    return {"operand": operand, "payload": payload_name, "hardware": hardware,
            "actual_mode": "rd", "actual_C1": 0, "C1_changes_output_only_acceptance": False,
            "complete_numeric_paths": path_count, "policy_space_volume": total_volume,
            "accepted_policy_space_volume": accepted_volume,
            "projected_cube_predicate_checks": projection_checks, "individual_witness": witness}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    assert not args.output.exists(), "refusing existing output"
    reports = []
    for path, expected in LOCKS.items():
        assert digest(args.root/path) == expected
        reports.append(json.loads((args.root/path).read_text()))
    joint, fixed = reports
    evidence = dict(LOCKS)
    for path, expected in fixed["sha256"]["evidence"].items():
        assert digest(args.root/path) == expected, path
        evidence[path] = expected
    assert digest(args.root/"experiments/h1602_fixed_operation_policy_solve.py") == fixed["sha256"]["script"]
    evidence["experiments/h1602_fixed_operation_policy_solve.py"] = fixed["sha256"]["script"]
    rows = {row["operand"]: row for row in joint["rows"]}
    truth = [[*policies, int(predicate(OPERANDS[0], policies)), int(predicate(OPERANDS[1], policies))]
             for policies in itertools.product(POLICIES, repeat=4)]
    assert len(truth) == 625 and not any(row[-2] and row[-1] for row in truth)
    details = []
    for payload_name in ("omitted", "frozen_numeric"):
        counts = {row["operand"]: row["accepted_fixed_policy_assignments"] for row in fixed["results"][payload_name]["rows"]}
        for operand in OPERANDS:
            detail = verify_operand(rows[operand], payload_name, counts[operand])
            details.append(detail)
            print(operand, payload_name, detail["accepted_policy_space_volume"], flush=True)
    result = {"experiment": "h1605_same_mode_policy_core", "status": "SAME_RD_CONVENTIONAL_POLICY_CONTRADICTION",
        "hardware_execution": "none", "C_execution": "none", "MDD_logic_imported": False,
        "policies": POLICIES, "projected_variables": [graph.NAMES[i] for i in ACTIVE],
        "predicates": {OPERANDS[0]: "N in Z OR (S in Z AND L in Z AND C=CHOP)",
                       OPERANDS[1]: "N in T AND (S=AWAY OR L in T OR C!=CHOP)",
                       "T": sorted(T), "Z": sorted(Z)},
        "projected_truth_table": truth, "rows": details,
        "consequence": "even arbitrary architectural-RC-only choice among these policies at each cut cannot fit both operands, because both are RD; same fixed graph/width/payload assumptions remain essential",
        "scope_exclusions": ["input-dependent internal state", "different precision", "different graph or forwarding", "nonstandard rounding", "changed payload generation"],
        "sha256": {"script": digest(Path(__file__)), "evidence": evidence}}
    with args.output.open("x") as target:
        json.dump(result, target, indent=2, sort_keys=True)
        target.write("\n")


if __name__ == "__main__":
    main()
