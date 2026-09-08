#!/usr/bin/env python3
"""Independent numerical policy-box proof of H1609's two-output RD core.

No H1608/H1609 compiler, MDD, inverse interval, or liveness optimization is
imported. All numerical paths partition all six-choice vectors. Accepting
boxes are existentially projected onto four operation choices; disjoint
projections suffice to reject a shared vector without fitting an input rule.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
import math
from collections import Counter
from functools import lru_cache
from pathlib import Path

import h1604_fixed_policy_core_certificate as independent


spec, V, OPS = independent.arithmetic, independent.Value, independent.OPS
POLICIES = (*independent.POLICIES, "EXACT")
N, K = len(OPS), len(POLICIES)
CORE = ("3ffc e73ffffd2c52df71", "3ffc fcbfffffcee1bd36")
PROJECTED = (0, 5, 10, 12)
PARENT = "tmp/ledger33/current/h1609_rc_only_combined_semantics/report.json"
FACTS = "tmp/ledger33/current/h1600_joint_rc_c1_faithful_graph_v2/report.json"
LOCKS = {
    PARENT: "31d246bd667067e1d81a751acb935202071b11f0e19669b1cb48b099a89b1fb5",
    FACTS: "e5d9c15ac734d6bc21d609890c3a31d581c3defe913ae8318354ab0cee8e2da6",
    "experiments/h1604_fixed_policy_core_certificate.py":
        "0d24e387cf10a6b218fa45f7bca53c5c0b0dc7ba7cebab8c293e6410fabb5463",
    "experiments/h1592_independent_integer_spec.py":
        "0cc55ff4c0de1f957b30a5f48f5d63939ae22f2de99936f9bb41fe8543f80c82",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def numeric(value: V) -> tuple[int, int]:
    if not value.n:
        return 0, 0
    shift = (abs(value.n) & -abs(value.n)).bit_length()-1
    return value.n >> shift, value.e+shift


def choose(exact: V, width: int, policy: int) -> V:
    return exact if policy == 5 else independent.internal_round(exact, width, policy)


def observed_rd(row: dict) -> str:
    records = [r for r in row["authenticated_observations"] if r["mode"] == "rd"]
    assert len(records) == 1
    return records[0]["hardware"]


def rd_result(correction: V) -> str:
    prevalue = spec.exact_add(V(1, 0), correction)
    assert prevalue.n > 0
    # Positive RD is magnitude truncation. This uses the separate H1604
    # integer quantizer, not the H1608 final inverse or its acceptance roots.
    return spec.encode_external(independent.internal_round(prevalue, 64, 0))


@lru_cache(None)
def projected_bitset(masks: tuple[int, ...]) -> int:
    values = [[policy for policy in range(K) if mask & (1 << policy)] for mask in masks]
    bits = 0
    for vector in itertools.product(*values):
        index = 0
        for policy in vector:
            index = K*index+policy
        bits |= 1 << index
    assert bits.bit_count() == math.prod(mask.bit_count() for mask in masks)
    return bits


def certify(row: dict, payload_name: str, raw) -> dict:
    payload = independent.from_record(row["variants"][payload_name]["frozen_payload_signed"])
    state = independent.initial(row["operand"])
    wanted = observed_rd(row)
    projected_masks = [(1 << K)-1]*len(PROJECTED)
    projection = 0
    counts = Counter()
    volumes = Counter()
    aggregates = {}
    output_cache = {}
    first_witness = None
    policy_masks = []

    def visit(level: int, volume: int) -> None:
        nonlocal projection, first_witness
        if level == N:
            correction = state["correction"]
            key = numeric(correction)
            if key not in output_cache:
                output_cache[key] = rd_result(correction)
            accepted = output_cache[key] == wanted
            masks = tuple(projected_masks)
            group = aggregates.setdefault((masks, accepted), [0, 0])
            group[0] += 1
            group[1] += volume
            counts["numerical_leaf_boxes"] += 1
            volumes["accepted" if accepted else "rejected"] += volume
            if accepted:
                projection |= projected_bitset(masks)
                if first_witness is None:
                    first_witness = tuple((mask & -mask).bit_length()-1 for mask in policy_masks)
            return
        op = OPS[level]
        exact = independent.exact_operation(state, op, payload)
        partitions = {}
        for policy in range(K):
            value = choose(exact, op[4], policy)
            key = numeric(value)
            if key not in partitions:
                partitions[key] = [value, 0]
            partitions[key][1] |= 1 << policy
        masks = [item[1] for item in partitions.values()]
        assert sum(mask.bit_count() for mask in masks) == K
        assert sum(masks) == (1 << K)-1
        assert 1 <= len(partitions) <= 3
        counts["complete_local_partitions"] += 1
        # Every policy vector follows one and only one numeric branch at
        # each node. The full leaf boxes are therefore disjoint and complete.
        for value, mask in partitions.values():
            state[op[0]] = value
            if level in PROJECTED:
                projected_masks[PROJECTED.index(level)] = mask
            policy_masks.append(mask)
            visit(level+1, volume*mask.bit_count())
            policy_masks.pop()
        del state[op[0]]

    visit(0, 1)
    assert sum(volumes.values()) == K**N
    assert first_witness is not None
    # Re-execute a complete singleton witness independently of recursion.
    state = independent.initial(row["operand"])
    stages = []
    for op, policy in zip(OPS, first_witness):
        exact = independent.exact_operation(state, op, payload)
        state[op[0]] = choose(exact, op[4], policy)
        stages.append({"node": op[0], "policy": POLICIES[policy], "chosen": state[op[0]].record()})
    assert rd_result(state["correction"]) == wanted
    for (masks, accepted), (leaves, volume) in sorted(aggregates.items()):
        raw.write((json.dumps({"operand": row["operand"], "payload": payload_name,
            "projected_policy_masks": masks, "accepted": accepted, "leaf_boxes": leaves,
            "full_assignment_volume": volume}, sort_keys=True, separators=(",", ":"))+"\n").encode())
    return {"operand": row["operand"], "actual_RD_output": wanted, **counts,
        "covered_full_policy_vectors": sum(volumes.values()), "accepted_full_vectors": volumes["accepted"],
        "rejected_full_vectors": volumes["rejected"], "distinct_corrections": len(output_cache),
        "aggregated_projected_box_classes": len(aggregates),
        "existential_acceptance_projection_hex": f"{projection:x}",
        "existential_projection_assignments": projection.bit_count(),
        "singleton_witness": {"policies": [POLICIES[p] for p in first_witness], "stages": stages,
                              "actual_mode_output": rd_result(state["correction"])}}


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
    facts = json.loads((root/FACTS).read_text())
    parent = json.loads((root/PARENT).read_text())
    for relative, expected in facts["sha256"]["evidence"].items():
        assert digest(root/relative) == expected, relative
        assert evidence.get(relative, expected) == expected
        evidence[relative] = expected
    tests = independent.selftest()
    # Check the projection's positional encoding independently by scanning
    # every four-variable vector for many masks, including full/singletons.
    projection_checks = 0
    masks_to_test = [(63,)*4, (1, 2, 4, 8), (3, 12, 48, 21), (42, 21, 31, 32)]
    for masks in masks_to_test:
        bits = projected_bitset(masks)
        for index, vector in enumerate(itertools.product(range(K), repeat=4)):
            assert bool(bits & (1 << index)) == all(mask & (1 << policy) for mask, policy in zip(masks, vector))
            projection_checks += 1
    output.mkdir(parents=True)
    raw_path = output/"projected_policy_box_aggregates.jsonl.gz"
    results = {}
    with raw_path.open("xb") as raw_file, gzip.GzipFile(fileobj=raw_file, mode="wb", filename="", mtime=0) as raw:
        for payload in ("omitted", "frozen_numeric"):
            details = []
            for operand in CORE:
                row = next(r for r in facts["rows"] if r["operand"] == operand)
                detail = certify(row, payload, raw)
                # The independent proof above is complete before comparison
                # to the old solver's integer count; no diagram is read.
                saved = next(r for r in parent["results"][payload]["modes"]["rd"]["rows"] if r["operand"] == operand)
                assert detail["accepted_full_vectors"] == saved["output_only_assignments"]
                details.append(detail)
                print(payload, operand, detail["numerical_leaf_boxes"], detail["existential_projection_assignments"], flush=True)
            common = int(details[0]["existential_acceptance_projection_hex"], 16) & int(details[1]["existential_acceptance_projection_hex"], 16)
            assert common == 0
            results[payload] = {"rows": details, "common_projected_assignments": common.bit_count(),
                "common_full_vectors": 0, "minimum_core_cardinality": 2,
                "proof": "independently generated existential projections are disjoint; both singleton full witnesses succeed"}
    report = {"experiment": "h1611_independent_combined_rd_core", "status": "INDEPENDENT_NUMERICAL_CORE_VERIFIED",
        "hardware_or_C_execution": "none", "MDD_or_liveness_code_used": False, "observations_used": 2,
        "policies": POLICIES, "operation_schedule": OPS, "full_vectors_per_operand_payload": K**N,
        "projected_operations": [OPS[i][0] for i in PROJECTED], "projected_assignments": K**len(PROJECTED),
        "selftest": {"independent_quantizer_tests": tests, "projection_membership_cases": projection_checks},
        "results": results,
        "raw_artifact_scope": "aggregates over projected masks/verdict retain exact leaf counts and full-vector volumes; generated by complete no-liveness numerical traversal, not a raw copy of every arithmetic leaf",
        "independence_scope": "H1604 separate internal quantizer, explicit graph and direct positive-RD final rounding; H1592 exact dyadics/constants/encoding shared; H1608/H1609 solver not imported; old accepted counts compared only after independent construction",
        "claim_boundary": "only specified original-width conventional-or-exact family, even with RC-only policy selection because both observations RD; not a hardware gate, an operand selector or general closed-form impossibility",
        "sha256": {"script": digest(Path(__file__)), "evidence": evidence, "projected_box_aggregates": digest(raw_path)}}
    with (output/"report.json").open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")


if __name__ == "__main__":
    main()
