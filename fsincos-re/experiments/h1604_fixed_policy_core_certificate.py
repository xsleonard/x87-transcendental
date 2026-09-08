#!/usr/bin/env python3
"""Independent numeric/policy-box certificate for H1602's two-input core.

No H1602 solver code is imported or executed. This verifier explicitly spells
out the arithmetic schedule, implements all five internal rounding policies,
and recursively partitions their full Cartesian space by numeric results.
Every leaf policy box is checked against compact predicates. Projection then
exhausts all retained-variable assignments with direct integer arithmetic.
H1592 dyadic primitives and final architectural rounding are shared and named.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
import math
import random
from collections import Counter
from pathlib import Path

import h1592_independent_integer_spec as arithmetic


Value = arithmetic.Value
POLICIES = ("CHOP", "RN_even", "RN_away", "AWAY", "JAM")
ALL = 31
T = (1 << 1) | (1 << 2) | (1 << 3)
AJ = (1 << 3) | (1 << 4)
CHOP = 1
# This is the hypothesized schedule being audited, not a physical-recovery
# assertion. Every stage consumes only previously materialized named values.
OPS = (
    ("square", "*", "x", "x", 67),
    ("fourth", "*", "square", "square", 67),
    ("negative_mul1", "*", "fourth", "C5", 67),
    ("negative_add1", "+", "C3", "negative_mul1", 64),
    ("negative_mul2", "*", "fourth", "negative_add1", 67),
    ("negative_factor", "+", "C1", "negative_mul2", 64),
    ("positive_mul1", "*", "fourth", "C6", 67),
    ("positive_add1", "+", "C4", "positive_mul1", 64),
    ("positive_mul2", "*", "fourth", "positive_add1", 67),
    ("positive_factor", "+", "C2", "positive_mul2", 64),
    ("left", "*", "square", "negative_factor", 67),
    ("right", "*", "fourth", "positive_factor", 67),
    ("correction", "+P", "left", "right", 67),
)
NAMES = tuple(op[0] for op in OPS)
PROJECTED = {"omitted": (0, 5, 9, 10, 12), "frozen_numeric": (0, 1, 5, 9, 10, 11, 12)}
CORE = ("3ffc b0000000044ca2bf", "3ffc cdcc0585c940196f")
LOCKS = {
    "tmp/ledger33/current/h1602_fixed_operation_policy_solve/report.json": "8fef73d4ff104dc7bc5d945f7c418a873f4ab6e08b3b1b660f7abdd28b1d76ba",
    "experiments/h1602_fixed_operation_policy_solve.py": "35c787a27bf25d750cf2f6f45cd29aaab6ceb5cf057ac46d8cd41227ead508da",
    "tmp/ledger33/current/h1600_joint_rc_c1_faithful_graph_v2/report.json": "e5d9c15ac734d6bc21d609890c3a31d581c3defe913ae8318354ab0cee8e2da6",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def numeric(value: Value) -> tuple[int, int]:
    return value.n, value.e


def from_record(record: dict) -> Value:
    n = int(record["sig_hex"], 16)
    return Value(-n if record["sign"] else n, record["e2"])


def internal_round(exact: Value, width: int, policy: int) -> Value:
    """Independent normalized integer quantizer for the five listed rules."""
    if not exact.n:
        return Value(0, 0)
    negative = exact.n < 0
    n = abs(exact.n)
    cut = n.bit_length()-width
    if cut <= 0:
        return Value(-(n << -cut) if negative else n << -cut, exact.e+cut)
    q, remainder = divmod(n, 1 << cut)
    twice = 2*remainder
    if policy == 0:
        increment = False
    elif policy == 1:
        increment = twice > 1 << cut or (twice == 1 << cut and q % 2 == 1)
    elif policy == 2:
        increment = twice >= 1 << cut
    elif policy == 3:
        increment = remainder != 0
    elif policy == 4:
        increment = remainder != 0 and q % 2 == 0
    else:
        raise ValueError(policy)
    q += increment
    if q == 1 << width:
        q >>= 1
        cut += 1
    return Value(-q if negative else q, exact.e+cut)


def initial(operand: str) -> dict[str, Value]:
    value = arithmetic.decode_external(operand)
    assert value.n > 0 and value.e+value.n.bit_length()-1 == -3
    return {"x": value, **{f"C{i}": value for i, value in arithmetic.COEFFICIENTS.items()}}


def exact_operation(state: dict, op: tuple, payload: Value) -> Value:
    _, kind, a, b, _ = op
    if kind == "*":
        return arithmetic.exact_mul(state[a], state[b])
    out = arithmetic.exact_add(state[a], state[b])
    return arithmetic.exact_add(out, payload) if kind == "+P" else out


def acceptance(row: dict, correction: Value) -> dict:
    z = arithmetic.exact_add(Value(1, 0), correction).fraction()
    outputs = {r["mode"]: arithmetic.encode_external(arithmetic.add(Value(1, 0), correction, 64, r["mode"]))
               for r in row["authenticated_observations"]}
    sparse_mode = "rn" if row["operand"] == CORE[0] else "ru"
    required = {r["mode"]: r["hardware"] for r in row["authenticated_observations"]}
    sparse = outputs[sparse_mode] == required[sparse_mode]
    full_rc = outputs == required
    c1 = all(int(arithmetic.decode_external(r["hardware"]).fraction() > z) == r["c1"] for r in row["actual_C1_constraints"])
    return {"sparse_output": sparse, "all_actual_RC": full_rc, "all_actual_RC_C1": full_rc and c1,
            "prevalue": str(z), "outputs": outputs}


def b_predicate(vector: tuple[int, ...] | list[int]) -> bool:
    return vector[0] in (3, 4) or vector[5] in (3, 4) or vector[9] == 0 or vector[10] in (1, 2, 3) or vector[12] in (1, 2, 3)


def d_predicate(vector: tuple[int, ...] | list[int], payload_name: str) -> bool:
    return not b_predicate(vector) and (payload_name == "omitted" or vector[1] in (1, 2, 3) or vector[11] in (3, 4))


def or_range(box: tuple[int, ...], terms: tuple[tuple[int, int], ...]) -> tuple[bool, bool]:
    """Whether false/true is possible on this independent Cartesian box."""
    can_true = any(box[index] & wanted for index, wanted in terms)
    can_false = all(box[index] & (ALL ^ wanted) for index, wanted in terms)
    return bool(can_false), bool(can_true)


def predicate_range(box: tuple[int, ...], operand: str, payload_name: str) -> set[bool]:
    bf, bt = or_range(box, ((0, AJ), (5, AJ), (9, CHOP), (10, T), (12, T)))
    if operand == CORE[0]:
        return ({False} if bf else set()) | ({True} if bt else set())
    if payload_name == "omitted":
        return ({False} if bt else set()) | ({True} if bf else set())
    gf, gt = or_range(box, ((1, T), (11, AJ)))
    # The B and G terms involve disjoint variables, so all combinations of
    # their possible truth values occur within a Cartesian policy box.
    return ({False} if bt or gf else set()) | ({True} if bf and gt else set())


def forward(row: dict, payload: Value, vector: tuple[int, ...] | list[int]) -> dict:
    state = initial(row["operand"])
    stages = []
    for i, op in enumerate(OPS):
        exact = exact_operation(state, op, payload)
        state[op[0]] = internal_round(exact, op[4], vector[i])
        stages.append({"node": op[0], "exact": exact.record(), "policy": POLICIES[vector[i]], "rounded": state[op[0]].record()})
    return {**acceptance(row, state["correction"]), "stages": stages}


def certify_boxes(row: dict, payload_name: str, leaf_file) -> dict:
    payload = from_record(row["variants"][payload_name]["frozen_payload_signed"])
    state = initial(row["operand"])
    policy_box = []
    counts = Counter()
    volumes = Counter()
    cache = {}

    def visit(level: int) -> None:
        if level == len(OPS):
            box = tuple(policy_box)
            volume = math.prod(mask.bit_count() for mask in box)
            k = numeric(state["correction"])
            if k not in cache:
                cache[k] = acceptance(row, state["correction"])
            result = cache[k]
            assert result["sparse_output"] == result["all_actual_RC"] == result["all_actual_RC_C1"]
            verdict = result["all_actual_RC_C1"]
            # This checks *every* policy assignment in the box, not a sample
            # point and not just all-CHOP choices for the omitted variables.
            assert predicate_range(box, row["operand"], payload_name) == {verdict}, (row["operand"], payload_name, box)
            volumes["accepted" if verdict else "rejected"] += volume
            counts["leaf_boxes"] += 1
            counts["predicate_homogeneity_checks"] += 1
            leaf_file.write((json.dumps({"operand": row["operand"], "payload": payload_name,
                "policy_masks": box, "box_volume": volume, "accepted": verdict,
                "sparse_equals_all_RC_equals_C1": True, "signed_correction": state["correction"].record()}, sort_keys=True)+"\n").encode())
            return
        op = OPS[level]
        exact = exact_operation(state, op, payload)
        partitions = {}
        for policy in range(5):
            value = internal_round(exact, op[4], policy)
            k = numeric(value)
            if k not in partitions:
                partitions[k] = [value, 0]
            partitions[k][1] |= 1 << policy
        partition_masks = [item[1] for item in partitions.values()]
        assert sum(mask.bit_count() for mask in partition_masks) == 5
        assert sum(partition_masks) == ALL  # masks disjoint, union all policies
        assert len(partitions) in (1, 2)
        counts["locally_complete_policy_partitions"] += 1
        # Each full policy vector follows exactly one branch here. By
        # induction on depth the leaf boxes disjointly cover all 5**13 vectors.
        for value, mask in partitions.values():
            state[op[0]] = value
            policy_box.append(mask)
            visit(level+1)
            policy_box.pop()
        del state[op[0]]

    visit(0)
    assert sum(volumes.values()) == 5**13
    return {**counts, "policy_vector_coverage": sum(volumes.values()),
            "accepted_full_vectors": volumes["accepted"], "rejected_full_vectors": volumes["rejected"],
            "all_omitted_variables_proved_irrelevant_by_box_homogeneity": True,
            "extra_RC_and_C1_redundant_for_this_operand_over_full_policy_family": True}


def diagram_value(diagram: dict, root: int, vector: tuple[int, ...] | list[int]) -> bool:
    # A plain read-only interpretation used only as a comparison, never as
    # the arithmetic certificate or the source of the compact predicates.
    while root > 1:
        level, children = diagram["nodes"][root]
        root = children[vector[level]]
    return root == 1


def selftest() -> dict:
    checks = 0
    for n in range(-511, 512):
        if not n:
            continue
        exact = Value(n, -7)
        for width in range(2, 8):
            for policy, shared in ((0, "chop"), (1, "rn"), (3, "away"), (4, "odd")):
                assert numeric(internal_round(exact, width, policy)) == numeric(arithmetic.quantize(exact, width, shared))
                checks += 1
            lower = arithmetic.quantize(exact, width, "chop")
            upper = arithmetic.quantize(exact, width, "away")
            expected = min((lower, upper), key=lambda v: (abs(v.fraction()-exact.fraction()), -abs(v.fraction())))
            assert internal_round(exact, width, 2).fraction() == expected.fraction()
            checks += 1
    # Test the box-range logic independently against every assignment of
    # many small projected Cartesian boxes, including mixed truth values.
    range_checks = 0
    range_shapes = {(operand, payload): set() for operand in CORE for payload in PROJECTED}
    generator = random.Random(1604)
    relevant = PROJECTED["frozen_numeric"]
    boxes = [[1 << generator.randrange(5) for _ in relevant] for _ in range(125)]
    boxes += [[sum(1 << p for p in generator.sample(range(5), 2)) for _ in relevant]
              for _ in range(375)]
    for masks in boxes:
        box = [1]*13
        for i, mask in zip(relevant, masks):
            box[i] = mask
        for operand in CORE:
            for payload in ("omitted", "frozen_numeric"):
                expected = set()
                for choices in itertools.product(*[[p for p in range(5) if mask & (1 << p)] for mask in masks]):
                    vector = [0]*13
                    for i, p in zip(relevant, choices):
                        vector[i] = p
                    expected.add(b_predicate(vector) if operand == CORE[0] else d_predicate(vector, payload))
                assert predicate_range(tuple(box), operand, payload) == expected
                range_shapes[(operand, payload)].add(tuple(sorted(expected)))
                range_checks += 1
    assert all(shapes == {(False,), (True,), (False, True)} for shapes in range_shapes.values())
    return {"status": "PASS", "independent_internal_rounding_cases": checks, "box_range_cases": range_checks}


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
    if output.exists():
        raise SystemExit(f"refusing existing output: {output}")
    evidence, reports = {}, {}
    for relative, expected in LOCKS.items():
        assert digest(root/relative) == expected
        evidence[relative] = expected
        if relative.endswith(".json"):
            reports[relative] = json.loads((root/relative).read_text())
    parent = reports["tmp/ledger33/current/h1602_fixed_operation_policy_solve/report.json"]
    facts = reports["tmp/ledger33/current/h1600_joint_rc_c1_faithful_graph_v2/report.json"]
    for relative, expected in facts["sha256"]["evidence"].items():
        assert digest(root/relative) == expected
        evidence[relative] = expected
    rows = {r["operand"]: r for r in facts["rows"] if r["operand"] in CORE}
    assert len(rows) == 2
    assert NAMES == tuple(node[0] for node in parent["nodes"])
    assert tuple(node[4] for node in OPS) == tuple(node[4] for node in parent["nodes"])
    output.mkdir(parents=True)
    results = {}
    boxes_path, projected_path = output/"policy_boxes.jsonl.gz", output/"projected_assignments.tsv.gz"
    with boxes_path.open("xb") as boxes_raw, gzip.GzipFile(fileobj=boxes_raw, mode="wb", filename="", mtime=0) as boxes:
        with projected_path.open("xb") as proj_raw, gzip.GzipFile(fileobj=proj_raw, mode="wb", filename="", mtime=0) as proj:
            proj.write(b"payload\tprojected_policy_indices\tb000_accept\tcdcc_accept\n")
            for payload_name, indices in PROJECTED.items():
                relative = "tmp/ledger33/current/h1602_fixed_operation_policy_solve/"+payload_name+"_diagram.json"
                assert digest(root/relative) == parent["results"][payload_name]["diagram_sha256"]
                evidence[relative] = digest(root/relative)
                diagram = json.loads((root/relative).read_text())
                root_indices = {op: next(i for i, r in enumerate(facts["rows"]) if r["operand"] == op) for op in CORE}
                roots = {op: diagram["operand_roots"][i] for op, i in root_indices.items()}
                certificates = {op: certify_boxes(rows[op], payload_name, boxes) for op in CORE}
                counts = Counter()
                singleton_witnesses = {}
                for choices in itertools.product(range(5), repeat=len(indices)):
                    vector = [0]*13
                    for i, policy in zip(indices, choices):
                        vector[i] = policy
                    accepted = []
                    for op in CORE:
                        payload = from_record(rows[op]["variants"][payload_name]["frozen_payload_signed"])
                        numerical = forward(rows[op], payload, vector)
                        predicted = b_predicate(vector) if op == CORE[0] else d_predicate(vector, payload_name)
                        assert predicted == numerical["sparse_output"] == numerical["all_actual_RC"] == numerical["all_actual_RC_C1"]
                        assert diagram_value(diagram, roots[op], vector) == predicted
                        accepted.append(predicted)
                        counts[op+".projected_accepts"] += predicted
                        if predicted and op not in singleton_witnesses:
                            singleton_witnesses[op] = {"policies": [POLICIES[p] for p in vector], **numerical}
                    assert not all(accepted)
                    counts["projected_assignments"] += 1
                    counts["joint_accepts"] += all(accepted)
                    proj.write((f"{payload_name}\t{','.join(map(str,choices))}\t{int(accepted[0])}\t{int(accepted[1])}\n").encode())
                factor = 5**(13-len(indices))
                for op in CORE:
                    assert counts[op+".projected_accepts"]*factor == certificates[op]["accepted_full_vectors"]
                assert len(singleton_witnesses) == 2
                results[payload_name] = {"projected_nodes": [NAMES[i] for i in indices],
                    "unused_policy_dimensions": 13-len(indices), "unused_dimension_lift": factor,
                    "counts": dict(counts), "numeric_box_certificates": certificates,
                    "singleton_witnesses": singleton_witnesses, "core_is_cardinality_minimum": True,
                    "diagram_roots_read_only_comparison": roots}
                print(payload_name, dict(counts), flush=True)
    report = {"experiment": "h1604_fixed_policy_core_certificate", "status": "INDEPENDENT_FULL_FINITE_CORE_VERIFIED",
        "C_or_hardware_execution": "none", "H1602_MDD_code_imported_or_executed": False,
        "core_operands": list(CORE), "policies": list(POLICIES), "full_vectors_per_payload": 5**13,
        "operation_schedule": OPS,
        "core_constraints": {op: {"authenticated_observations": rows[op]["authenticated_observations"],
            "actual_C1_constraints": rows[op]["actual_C1_constraints"],
            "frozen_payload_signed": rows[op]["variants"]["frozen_numeric"]["frozen_payload_signed"]}
            for op in CORE},
        "selftest": tests, "results": results,
        "compact_predicates": {"B": "S in {AWAY,JAM} OR N in {AWAY,JAM} OR P=CHOP OR L in T OR C in T",
            "D_omitted": "NOT B", "D_frozen": "NOT B AND (F in T OR R in {AWAY,JAM})",
            "T": ["RN_even", "RN_away", "AWAY"], "variables": {"S": "square", "F": "fourth", "N": "negative_factor", "P": "positive_factor", "L": "left", "R": "right", "C": "correction"}},
        "constraint_minimality": "b000 original observed RN and cdcc observed RU output bits suffice; b000 extra RC observations and cdcc C1 are redundant over every tested full policy vector",
        "proof_of_omitted_variables": "numeric branches locally partition all five policies at every one of13 cuts; every leaf box is predicate-homogeneous, disjoint by first divergent partition, and total volume5^13; no policy choices at omitted nodes can change acceptance",
        "independence_scope": "own operation schedule, five-policy integer quantizer, numeric partition traversal, compact Boolean range checks and exhaustive projected replay; shared H1592 exact dyadic primitives/constants/final architectural rounding; H1602 diagrams interpreted only as cross-check",
        "claim_boundary": "two actual observed tuples exclude only one input-independent listed policy per node in the fixed13-cut width/sequence with omitted or frozen original payload; no global closed-form impossibility, no selector promotion",
        "sha256": {"script": digest(Path(__file__)), "evidence": evidence, "policy_boxes": digest(boxes_path), "projected_assignments": digest(projected_path)}}
    with (output/"report.json").open("x") as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write("\n")


if __name__ == "__main__":
    main()
