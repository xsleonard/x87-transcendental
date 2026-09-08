#!/usr/bin/env python3
"""Exhaust common ordinary-round/exact-bypass patterns on a thirteen-cut graph.

Bypass forwards the exact numerical dyadic to every consumer of the node.
This is an unbounded-precision mathematical hypothesis.
No C/hardware execution, input predicates, unobserved modes or payload refits.
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
from pathlib import Path

import h1592_independent_integer_spec as spec


Value = spec.Value
NODES = (
    ("square", "*", "x", "x", 67, "chop"),
    ("fourth", "*", "square", "square", 67, "chop"),
    ("negative_mul1", "*", "fourth", "C5", 67, "chop"),
    ("negative_add1", "+", "C3", "negative_mul1", 64, "rn"),
    ("negative_mul2", "*", "fourth", "negative_add1", 67, "chop"),
    ("negative_factor", "+", "C1", "negative_mul2", 64, "rn"),
    ("positive_mul1", "*", "fourth", "C6", 67, "chop"),
    ("positive_add1", "+", "C4", "positive_mul1", 64, "rn"),
    ("positive_mul2", "*", "fourth", "positive_add1", 67, "chop"),
    ("positive_factor", "+", "C2", "positive_mul2", 64, "rn"),
    ("left", "*", "square", "negative_factor", 67, "chop"),
    ("right", "*", "fourth", "positive_factor", 67, "chop"),
    ("correction", "+P", "left", "right", 67, "chop"),
)
PATTERNS = 1 << len(NODES)
ALL_PATTERNS = (1 << PATTERNS)-1
H1600 = "tmp/ledger33/current/h1600_joint_rc_c1_faithful_graph_v2/report.json"
LOCKS = {
    H1600: "e5d9c15ac734d6bc21d609890c3a31d581c3defe913ae8318354ab0cee8e2da6",
    "experiments/h1592_independent_integer_spec.py": "0cc55ff4c0de1f957b30a5f48f5d63939ae22f2de99936f9bb41fe8543f80c82",
    "experiments/h1603_direct_control_semantics_bank.py": "87283b4b84b921314ce892507d156b563e5354009f13f58145720aadd53fc5d0",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unpack(record: dict) -> Value:
    n = int(record["sig_hex"], 16)
    return Value(-n if record["sign"] else n, record["e2"])


def key(value: Value) -> tuple[int, int]:
    """Canonical numerical key, without inherited last-round metadata."""
    if not value.n:
        return 0, 0
    zeros = (abs(value.n) & -abs(value.n)).bit_length()-1
    return value.n >> zeros, value.e+zeros


def initial(operand: str) -> dict[str, Value]:
    x = spec.decode_external(operand)
    assert x.n > 0 and x.e+x.n.bit_length()-1 == -3
    return {"x": x, **{f"C{i}": v for i, v in spec.COEFFICIENTS.items()}}


def operation(state: dict[str, Value], node: tuple, payload: Value) -> Value:
    _, op, left, right, _, _ = node
    value = spec.exact_mul(state[left], state[right]) if op == "*" else spec.exact_add(state[left], state[right])
    return spec.exact_add(value, payload) if op == "+P" else value


def forward(operand: str, payload: Value, mask: int, trace: bool = False) -> tuple[Value, list]:
    assert 0 <= mask < PATTERNS
    state, stages = initial(operand), []
    for i, node in enumerate(NODES):
        exact = operation(state, node, payload)
        chosen = exact if mask & (1 << i) else spec.quantize(exact, node[4], node[5])
        state[node[0]] = chosen
        if trace:
            stages.append({"node": node[0], "bypassed": bool(mask & (1 << i)),
                           "exact": exact.record(), "chosen": chosen.record()})
    return state["correction"], stages


def in_interval(value: Fraction, record: dict) -> bool:
    lower, upper = Fraction(record["lower"]), Fraction(record["upper"])
    return (value > lower or value == lower and record["lower_closed"]) and (value < upper or value == upper and record["upper_closed"])


def constraints(row: dict, correction: Value) -> dict:
    prevalue = spec.exact_add(Value(1, 0), correction).fraction()
    assert 0 < prevalue < 1
    outputs = {r["mode"]: spec.encode_external(spec.add(Value(1, 0), correction, 64, r["mode"]))
               for r in row["authenticated_observations"]}
    rc_misses = [r["mode"] for r in row["authenticated_observations"] if outputs[r["mode"]] != r["hardware"]]
    # This is an observed-output inverse inequality, conditional on ordinary
    # positive final rounding. It is not a claim that every internal event
    # uses the architectural C1 convention, nor an invented status label.
    c1_misses = [r["mode"] for r in row["actual_C1_constraints"]
                 if int(spec.decode_external(r["hardware"]).fraction() > prevalue) != r["c1"]]
    assert in_interval(prevalue, row["joint_RC_inverse"]) == (not rc_misses)
    assert in_interval(prevalue, row["joint_RC_C1_inverse"]) == (not rc_misses and not c1_misses)
    return {"RC_matches": not rc_misses, "RC_C1_matches": not rc_misses and not c1_misses,
            "RC_mismatched_modes": rc_misses, "C1_inverse_mismatched_modes": c1_misses,
            "observed_mode_outputs": outputs, "common_prevalue": str(prevalue)}


def enumerate_row(row: dict, payload_name: str, raw, totals: dict) -> dict:
    payload = unpack(row["variants"][payload_name]["frozen_payload_signed"])
    state = initial(row["operand"])
    cache, maxima = {}, {}
    seen = set()
    accepted_rc = accepted_joint = 0

    def visit(level: int, mask: int) -> None:
        nonlocal accepted_rc, accepted_joint
        if level == len(NODES):
            assert mask not in seen
            seen.add(mask)
            correction = state["correction"]
            k = key(correction)
            if k not in cache:
                cache[k] = constraints(row, correction)
            result = cache[k]
            if result["RC_matches"]:
                accepted_rc |= 1 << mask
            if result["RC_C1_matches"]:
                accepted_joint |= 1 << mask
            totals["failed_operands"][mask] += not result["RC_C1_matches"]
            totals["failed_output_operands"][mask] += not result["RC_matches"]
            totals["failed_output_rows"][mask] += len(result["RC_mismatched_modes"])
            totals["failed_C1_inverses"][mask] += len(result["C1_inverse_mismatched_modes"])
            raw.write((f"{payload_name}\t{row['operand']}\t{mask}\t{k[0]:x}\t{k[1]}\t"
                       f"{int(result['RC_matches'])}\t{int(result['RC_C1_matches'])}\t"
                       f"{','.join(result['RC_mismatched_modes'])}\t{','.join(result['C1_inverse_mismatched_modes'])}\n").encode())
            return
        node = NODES[level]
        exact = operation(state, node, payload)
        info = maxima.setdefault(node[0], {"maximum_exact_numerator_bits": 0,
                                          "minimum_exact_exponent": exact.e, "maximum_exact_exponent": exact.e})
        info["maximum_exact_numerator_bits"] = max(info["maximum_exact_numerator_bits"], abs(exact.n).bit_length())
        info["minimum_exact_exponent"] = min(info["minimum_exact_exponent"], exact.e)
        info["maximum_exact_exponent"] = max(info["maximum_exact_exponent"], exact.e)
        # Both choices remain separate even if their values coincide. Thus
        # every one of the 8192 named masks occurs, not just distinct values.
        state[node[0]] = spec.quantize(exact, node[4], node[5])
        visit(level+1, mask)
        state[node[0]] = exact
        visit(level+1, mask | (1 << level))
        del state[node[0]]

    visit(0, 0)
    assert seen == set(range(PATTERNS))
    successful = [i for i in range(PATTERNS) if accepted_joint & (1 << i)]
    minimum = min((m.bit_count() for m in successful), default=None)
    witnesses = [m for m in successful if m.bit_count() == minimum]
    return {"operand": row["operand"], "frozen_payload_signed": payload.record(),
            "patterns_evaluated": len(seen), "distinct_correction_values": len(cache),
            "RC_matching_patterns": accepted_rc.bit_count(), "RC_C1_matching_patterns": accepted_joint.bit_count(),
            "RC_acceptance_bitset_hex": f"{accepted_rc:x}", "RC_C1_acceptance_bitset_hex": f"{accepted_joint:x}",
            "minimum_bypasses_for_individual_operand": minimum, "minimum_bypass_masks": witnesses,
            "observed_exact_integer_size_ranges_not_physical_widths": maxima}


def fraction_quantize(value: Fraction, bits: int, mode: str) -> Fraction:
    """Reference uses rational grid arithmetic, separate from bit-cut code."""
    if value == 0:
        return value
    sign, magnitude = (-1 if value < 0 else 1), abs(value)
    exponent = magnitude.numerator.bit_length()-magnitude.denominator.bit_length()
    power = Fraction(2)**exponent
    if magnitude < power:
        exponent -= 1
    unit = Fraction(2)**(exponent-bits+1)
    units = magnitude // unit
    remainder = magnitude-units*unit
    if mode == "rn" and (2*remainder > unit or 2*remainder == unit and units % 2):
        units += 1
    return sign*units*unit


def fraction_forward(operand: str, payload: Value, mask: int) -> dict[str, Fraction]:
    state = {name: value.fraction() for name, value in initial(operand).items()}
    for i, (name, op, left, right, width, mode) in enumerate(NODES):
        exact = state[left]*state[right] if op == "*" else state[left]+state[right]
        if op == "+P":
            exact += payload.fraction()
        state[name] = exact if mask & (1 << i) else fraction_quantize(exact, width, mode)
    return state


def selftest() -> dict:
    quantizer_checks = 0
    for n in range(-511, 512):
        for width in range(2, 9):
            for mode in ("chop", "rn"):
                value = Value(n, -7)
                assert spec.quantize(value, width, mode).fraction() == fraction_quantize(value.fraction(), width, mode)
                quantizer_checks += 1
    generator = random.Random(1607)
    masks = [0, PATTERNS-1]+[1 << i for i in range(len(NODES))]+[generator.randrange(PATTERNS) for _ in range(113)]
    stage_checks = 0
    for mask in masks:
        operand = f"3ffc {generator.randrange(1 << 63, 1 << 64):016x}"
        payload = Value(generator.randrange(-8, 1), -81)
        _, stages = forward(operand, payload, mask, True)
        reference = fraction_forward(operand, payload, mask)
        for stage in stages:
            assert unpack(stage["chosen"]).fraction() == reference[stage["node"]]
            stage_checks += 1
        # The all-bypass endpoint must equal the unrounded degree-twelve
        # polynomial, independently of the factored operation schedule.
        x = spec.decode_external(operand).fraction()
        polynomial = sum(c.fraction()*x**(2*i) for i, c in spec.COEFFICIENTS.items())+payload.fraction()
        exact_correction, _ = forward(operand, payload, PATTERNS-1)
        assert exact_correction.fraction() == polynomial
    return {"status": "PASS", "independent_rational_grid_quantizer_checks": quantizer_checks,
            "independent_rational_graph_replays": len(masks), "rational_graph_stage_checks": stage_checks,
            "all_bypass_direct_polynomial_checks": len(masks)}


def smallest_core(rows: list[dict], field: str) -> dict:
    """Exhaust size <=3; otherwise report deletion-minimal, not minimum."""
    def intersection(indices):
        keep = ALL_PATTERNS
        for i in indices:
            keep &= int(rows[i][field], 16)
        return keep
    if intersection(range(len(rows))):
        return {"exists": False}
    for size in (1, 2, 3):
        for indices in itertools.combinations(range(len(rows)), size):
            if not intersection(indices):
                return {"exists": True, "operands": [rows[i]["operand"] for i in indices],
                        "cardinality": size, "cardinality_minimum_proved": True}
    indices = list(range(len(rows)))
    for i in tuple(indices):
        reduced = [j for j in indices if j != i]
        if not intersection(reduced):
            indices = reduced
    return {"exists": True, "operands": [rows[i]["operand"] for i in indices],
            "cardinality": len(indices), "cardinality_minimum_proved": False, "deletion_minimal": True}


def certify_core(details: list[dict], observations: list[dict], payload: str, core: dict) -> dict:
    """Straight-line full replay verifies simple bypass-core predicates."""
    if not core["exists"]:
        return {}
    expected_ops = (["3ffc b72fd2547f8c2fef", "3ffc ba100000056e0a67"] if payload == "omitted"
                    else ["3ffc b0000000044ca2bf", "3ffc cdcc0585c940196f"])
    assert core["operands"] == expected_ops
    by_op, recorded = {r["operand"]: r for r in details}, {r["operand"]: r for r in observations}
    mode_sets, witnesses = {}, {}
    checks = 0
    for index, op in enumerate(expected_ops):
        row = recorded[op]
        bits = int(by_op[op]["RC_acceptance_bitset_hex"], 16)
        mode_sets[op] = {r["mode"]: 0 for r in row["authenticated_observations"]}
        for mask in range(PATTERNS):
            s, n, p, l, right = (bool(mask & (1 << bit)) for bit in (0, 5, 9, 10, 11))
            if payload == "omitted":
                accepted = (s or n or l) if index else not (s or n or l)
            else:
                accepted = (n or p or l) if index == 0 else not (n or p or l) and (s or right)
            assert accepted == bool(bits & (1 << mask))
            correction, _ = forward(op, unpack(by_op[op]["frozen_payload_signed"]), mask)
            outcome = constraints(row, correction)
            assert outcome["RC_matches"] == outcome["RC_C1_matches"] == accepted
            for observed in row["authenticated_observations"]:
                mode = observed["mode"]
                if outcome["observed_mode_outputs"][mode] == observed["hardware"]:
                    mode_sets[op][mode] |= 1 << mask
            if accepted and op not in witnesses:
                _, stages = forward(op, unpack(by_op[op]["frozen_payload_signed"]), mask, True)
                rational = fraction_forward(op, unpack(by_op[op]["frozen_payload_signed"]), mask)
                assert all(unpack(stage["chosen"]).fraction() == rational[stage["node"]] for stage in stages)
                witnesses[op] = {"mask": mask, "bypassed_nodes": [node[0] for i, node in enumerate(NODES) if mask & (1 << i)],
                                 **outcome, "stages": stages}
            checks += 1
    first, second = expected_ops
    single_mode_pairs = []
    for a, aset in mode_sets[first].items():
        for b, bset in mode_sets[second].items():
            if not aset & bset:
                single_mode_pairs.append({"first_mode": a, "second_mode": b, "same_RC": a == b})
    return {"straight_line_replays": checks, "individual_witnesses": witnesses,
            "all_actual_C1_redundant_on_core": True, "single_output_mode_contradictions": single_mode_pairs,
            "recorded_constraints": {op: {"outputs": recorded[op]["authenticated_observations"],
                                            "C1": recorded[op]["actual_C1_constraints"]} for op in expected_ops},
            "bypass_variables": {"S": "square", "N": "negative_factor", "P": "positive_factor", "L": "left", "R": "right"},
            "predicates_in_core_order": (["NOT(S OR N OR L)", "S OR N OR L"] if payload == "omitted"
                                           else ["N OR P OR L", "NOT(N OR P OR L) AND (S OR R)"])}


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
        raise SystemExit(f"refusing existing output directory: {output}")
    evidence = {}
    for relative, expected in LOCKS.items():
        assert digest(root/relative) == expected, relative
        evidence[relative] = expected
    prior = json.loads((root/H1600).read_text())
    for relative, expected in prior["sha256"]["evidence"].items():
        assert digest(root/relative) == expected, relative
        assert evidence.get(relative, expected) == expected
        evidence[relative] = expected
    rows = prior["rows"]
    assert len(rows) == 36 and len({r["operand"] for r in rows}) == 36
    assert sum(len(r["authenticated_observations"]) for r in rows) == 64
    assert sum(len(r["actual_C1_constraints"]) for r in rows) == 27
    # Check the no-payload, no-bypass boundary against the established full
    # ordinary replay in every actual mode; no C trace supplies arithmetic.
    ordinary_checks = 0
    for row in rows:
        correction, _ = forward(row["operand"], Value(0, 0), 0)
        for observed in row["authenticated_observations"]:
            old = spec.replay(row["operand"], observed["mode"])
            assert key(old["correction"]) == key(correction)
            assert key(old["result"]) == key(spec.add(Value(1, 0), correction, 64, observed["mode"]))
            ordinary_checks += 1
    output.mkdir(parents=True)
    raw_path, score_path = output/"all_bypass_outcomes.tsv.gz", output/"all_pattern_scores.tsv"
    results = {}
    with raw_path.open("xb") as raw_file, gzip.GzipFile(fileobj=raw_file, mode="wb", filename="", mtime=0) as raw:
        raw.write(b"payload\toperand\tbypass_mask\tcorrection_n_hex\tcorrection_e2\tRC_match\tRC_C1_match\tRC_bad_modes\tC1_inverse_bad_modes\n")
        with score_path.open("x") as scores:
            scores.write("payload\tmask\tfailed_operands\tfailed_output_operands\tfailed_output_rows\tfailed_C1_inverses\n")
            for payload in ("omitted", "frozen_numeric"):
                totals = {name: [0]*PATTERNS for name in ("failed_operands", "failed_output_operands", "failed_output_rows", "failed_C1_inverses")}
                details = []
                for i, row in enumerate(rows):
                    details.append(enumerate_row(row, payload, raw, totals))
                    if (i+1) % 9 == 0:
                        print(f"{payload}: fully enumerated {i+1}/36 operands", flush=True)
                common = [m for m in range(PATTERNS) if totals["failed_operands"][m] == 0]
                common_rc = [m for m in range(PATTERNS) if totals["failed_output_operands"][m] == 0]
                for m in range(PATTERNS):
                    scores.write(f"{payload}\t{m}\t"+"\t".join(str(totals[name][m]) for name in totals)+"\n")
                minimum = min(totals["failed_operands"])
                best = [m for m in range(PATTERNS) if totals["failed_operands"][m] == minimum]
                representative = min(best, key=lambda m: (totals["failed_output_rows"][m], m.bit_count(), m))
                witnesses = []
                for row in rows:
                    correction, stages = forward(row["operand"], unpack(row["variants"][payload]["frozen_payload_signed"]), representative, True)
                    result = constraints(row, correction)
                    if not result["RC_C1_matches"]:
                        witnesses.append({"operand": row["operand"], "mask": representative, **result, "stages": stages})
                results[payload] = {"patterns": PATTERNS, "complete_operand_pattern_evaluations": len(rows)*PATTERNS,
                    "common_RC_survivors": common_rc, "common_RC_C1_survivors": common,
                    "minimum_failed_operands": minimum, "best_pattern_masks": best,
                    "representative_best_mask": representative, "representative_failures": witnesses,
                    "failed_operand_histogram": dict(sorted(Counter(totals["failed_operands"]).items())),
                    "output_only_core": smallest_core(details, "RC_acceptance_bitset_hex"),
                    "output_and_C1_core": smallest_core(details, "RC_C1_acceptance_bitset_hex"),
                    "rows": details}
                results[payload]["core_certificate"] = certify_core(details, rows, payload, results[payload]["output_only_core"])
                print(payload, "common RC/C1 survivors", len(common), "best failed operands", minimum, flush=True)
    controls = {}
    omitted_survivors = results["omitted"]["common_RC_C1_survivors"]
    if omitted_survivors:
        import h1603_direct_control_semantics_bank as wall
        bank = wall.load_controls(root)
        evidence.update(bank.evidence)
        for mask in omitted_survivors:
            misses = []
            for row in bank.controls:
                correction, _ = forward(row.operand, Value(0, 0), mask)
                for mode in wall.MODES:
                    predicted = spec.encode_external(spec.add(Value(1, 0), correction, 64, mode))
                    if predicted != row.hardware(mode):
                        misses.append({"operand": row.operand, "mode": mode, "hardware": row.hardware(mode), "predicted": predicted})
            controls[str(mask)] = {"operands": len(bank.controls), "actual_RC_rows": len(bank.controls)*4,
                                   "misses": misses, "status": "PASS_CACHED_REGRESSION_ONLY" if not misses else "FALSIFIED"}
    report = {"experiment": "h1607_exact_cut_bypass", "status": "COMPLETE_FINITE_ENUMERATION",
        "source_or_hardware_execution": "none", "selftest": tests, "ordinary_boundary_checks": ordinary_checks,
        "nodes": NODES, "mask_bit_meaning": "1 exact dyadic forwarded to all consumers; 0 ordinary rounded materialization",
        "observed_operands": 36, "actual_RC_observations": 64, "actual_C1_constraints": 27,
        "patterns_per_payload": PATTERNS, "pattern_is_common_across_inputs_and_RC": True,
        "payload_policy": "omitted zero or signed original consumed numeric payload frozen at original scale, never regenerated",
        "arithmetic_precision": "unbounded Python integers; exact means numerical exactness, not a finite hardware forwarding width",
        "claim_boundary": "only binary ordinary-round/exact-bypass choices at these13cuts; not arbitrary widths, graph changes, edge-specific forwarding, RC/input-dependent patterns, or general closed-form impossibility",
        "results": results,
        "omitted_control_wall": controls or {"status": "NOT_RUN_NO_COMMON_OMITTED_SURVIVOR"},
        "frozen_control_wall": {"status": "NOT_RUN_NO_COMMON_FROZEN_SURVIVOR" if not results["frozen_numeric"]["common_RC_C1_survivors"] else "NEEDS_AUTHENTICATED_CONSUMED_PAYLOAD_TRACES_NO_FABRICATION"},
        "sha256": {"script": digest(Path(__file__)), "evidence": evidence,
                   "all_bypass_outcomes": digest(raw_path), "all_pattern_scores": digest(score_path)}}
    with (output/"report.json").open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")


if __name__ == "__main__":
    main()
