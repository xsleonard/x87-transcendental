#!/usr/bin/env python3
"""Width-reduce H1518's unresolved g5.P[5] projection query.

H1518 represents equality by duplicating every nine-bit state word and adding
63 bit equalities.  H1521 constructs the same query from independent Boolean
coordinates: retained coordinates are single shared variables, omitted
extension-support coordinates have left/right copies, and H1517-proven absent
coordinates are fixed to zero.  This removes irrelevant high bits and equality
reasoning before either solver sees the circuit.

Two controls guard the reduction.  Retaining only H1517's 62 mandatory bits
must remain SAT; retaining all 87 extension-support bits must be UNSAT.  The
middle query adds H1518's unresolved g5.P[5] coordinate.

No x87 instruction or hardware capture is executed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

try:
    import z3
except ImportError as error:
    raise SystemExit("z3-solver 4.15.3.0 is required") from error

try:
    import cvc5
except ImportError as error:
    raise SystemExit("cvc5 1.3.1 is required") from error

from h1400_p5_representation_audit import tree_variants
from h1516_minimal_ordered_quartet_state import EXPECTED_A, EXPECTED_B, defect
from h1517_quartet_state_bit_support import (
    canonical_validity_constraints,
    coordinates,
    cvc5_terminal_crosscheck,
    decode_state,
    field_names,
)


CANDIDATE = ("g5.P", 5)


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def key(row):
    return row["field"], int(row["bit"])


def label(coordinate):
    return f"{coordinate[0].replace('.', '_')}_b{coordinate[1]}"


def word(bits):
    return z3.Concat(*(
        z3.If(bit, z3.BitVecVal(1, 1), z3.BitVecVal(0, 1))
        for bit in reversed(bits)
    ))


def reduced_states(prefix: str, retained, extension):
    retained = set(retained)
    extension = set(extension)
    shared = {
        coordinate: z3.Bool(f"{prefix}_shared_{label(coordinate)}")
        for coordinate in sorted(retained)
    }
    left_optional = {
        coordinate: z3.Bool(f"{prefix}_left_{label(coordinate)}")
        for coordinate in sorted(extension - retained)
    }
    right_optional = {
        coordinate: z3.Bool(f"{prefix}_right_{label(coordinate)}")
        for coordinate in sorted(extension - retained)
    }

    left = {}
    right = {}
    for field in field_names():
        left_bits = []
        right_bits = []
        for bit in range(9):
            coordinate = (field, bit)
            if coordinate in retained:
                left_bits.append(shared[coordinate])
                right_bits.append(shared[coordinate])
            elif coordinate in extension:
                left_bits.append(left_optional[coordinate])
                right_bits.append(right_optional[coordinate])
            else:
                left_bits.append(z3.BoolVal(False))
                right_bits.append(z3.BoolVal(False))
        left[field] = word(left_bits)
        right[field] = word(right_bits)
    return left, right, shared, left_optional, right_optional


def build_query(name: str, retained, extension, pair_a, pair_b):
    left, right, shared, left_optional, right_optional = reduced_states(
        name, retained, extension
    )
    left_defect = defect(decode_state(left), pair_a, pair_b)
    right_defect = defect(decode_state(right), pair_a, pair_b)
    assertion = z3.And(
        *canonical_validity_constraints(left),
        *canonical_validity_constraints(right),
        left_defect != right_defect,
    )
    return {
        "assertion": assertion,
        "left": left,
        "right": right,
        "shared": shared,
        "left_optional": left_optional,
        "right_optional": right_optional,
        "left_defect": left_defect,
        "right_defect": right_defect,
    }


def solve_query(graph, timeout_ms: int, crosscheck_timeout_ms: int):
    solver = z3.SolverFor("QF_BV")
    solver.set(timeout=timeout_ms)
    solver.add(graph["assertion"])
    status = solver.check()
    query = solver.to_smt2().replace(
        "(set-info :status unknown)",
        "(set-logic QF_BV)\n(set-info :status unknown)",
        1,
    )
    if status == z3.sat:
        return {
            "status": "sat",
            "solver": f"z3 {z3.get_version_string()}",
            "query": query,
            "model": solver.model(),
        }
    if status == z3.unsat:
        return {
            "status": "unsat",
            "solver": f"z3 {z3.get_version_string()}",
            "query": query,
        }
    crosscheck = cvc5_terminal_crosscheck(solver, crosscheck_timeout_ms)
    return {
        "status": crosscheck["status"],
        "solver": crosscheck["solver"],
        "query": crosscheck["query"],
        "z3_status": "unknown",
        "z3_reason_unknown": solver.reason_unknown(),
        "cvc5_reason": crosscheck["reason"],
    }


def result_record(result, path: Path):
    content = result["query"].encode()
    return {
        "status": result["status"],
        "solver": result["solver"],
        **({
            "z3_status": result["z3_status"],
            "z3_reason_unknown": result["z3_reason_unknown"],
            "cvc5_reason": result["cvc5_reason"],
        } if "z3_status" in result else {}),
        "query_artifact": path.name,
        "query_bytes": len(content),
        "query_sha256": sha256(content),
    }


def z3_counterexample_edge(graph, result, optional):
    if result["status"] != "sat" or "model" not in result:
        return None
    model = result["model"]
    edge = []
    for coordinate in optional:
        left = graph["left_optional"].get(coordinate)
        right = graph["right_optional"].get(coordinate)
        if left is None or right is None:
            continue
        if z3.is_true(model.eval(left, model_completion=True)) \
                != z3.is_true(model.eval(right, model_completion=True)):
            edge.append({"field": coordinate[0], "bit": coordinate[1]})
    return edge


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1517", type=Path)
    parser.add_argument("h1518", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout-ms", type=int, default=60_000)
    parser.add_argument("--crosscheck-timeout-ms", type=int, default=180_000)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    if z3.get_version_string() != "4.15.3" or cvc5.__version__ != "1.3.1":
        raise RuntimeError("validated solver versions changed")

    h1517 = json.loads(arguments.h1517.read_text())
    h1518 = json.loads(arguments.h1518.read_text())
    if h1517["status"] != "EXACT_EXTENSION_SUPPORT_WITH_REACHABILITY_GAP" \
            or h1518["status"] != "STOPPING_UNKNOWN":
        raise RuntimeError("H1517/H1518 boundary changed")
    if [key(row) for row in h1518["unresolved_candidate_optional"]] \
            != [CANDIDATE]:
        raise RuntimeError("H1518 candidate changed")

    extension = {key(row) for row in h1517["canonical_extension_support"]}
    mandatory = {key(row) for row in h1517["reachable_state_support"]}
    if (len(extension), len(mandatory), len(extension - mandatory)) \
            != (87, 62, 25):
        raise RuntimeError("H1517 support counts changed")

    layouts = {name: config for name, _, config in tree_variants()}
    pair_a = layouts[EXPECTED_A]
    pair_b = layouts[EXPECTED_B]
    cases = (
        ("lower_control", mandatory, "sat"),
        ("candidate", mandatory | {CANDIDATE}, None),
        ("upper_control", extension, "unsat"),
    )
    graphs = {}
    results = {}
    paths = {}
    for name, retained, expected in cases:
        path = arguments.output.with_name(
            arguments.output.stem + f"_{name}.smt2"
        )
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")
        graph = build_query(name, retained, extension, pair_a, pair_b)
        result = solve_query(
            graph, arguments.timeout_ms, arguments.crosscheck_timeout_ms
        )
        if expected is not None and result["status"] != expected:
            raise RuntimeError(
                f"{name} expected {expected}, got {result['status']}"
            )
        graph["retained"] = retained
        graphs[name] = graph
        results[name] = result
        paths[name] = path
        print(json.dumps({
            "case": name,
            "retained_coordinates": len(retained),
            "status": result["status"],
            "solver": result["solver"],
        }, sort_keys=True), flush=True)

    for name, path in paths.items():
        path.write_text(results[name]["query"])
    optional = tuple(sorted(extension - mandatory))
    candidate_edge = z3_counterexample_edge(
        graphs["candidate"], results["candidate"], optional
    )
    status = {
        "sat": "CANDIDATE_REFUTED",
        "unsat": "EXACT_63_COORDINATE_MINIMUM",
        "unknown": "STOPPING_UNKNOWN",
    }[results["candidate"]["status"]]
    report = {
        "experiment": "h1521_width_reduced_valid_projection",
        "status": status,
        "z3_version": z3.get_version_string(),
        "cvc5_version": cvc5.__version__,
        "construction": {
            "shared_retained_coordinates": 63,
            "left_right_optional_coordinates_each": 24,
            "h1517_absent_coordinates_fixed_zero": 21,
            "candidate": {"field": CANDIDATE[0], "bit": CANDIDATE[1]},
        },
        "lower_control": result_record(
            results["lower_control"], paths["lower_control"]
        ),
        "candidate_query": result_record(
            results["candidate"], paths["candidate"]
        ),
        "upper_control": result_record(
            results["upper_control"], paths["upper_control"]
        ),
        **({"candidate_counterexample_edge": candidate_edge}
           if candidate_edge is not None else {}),
        "interpretation": (
            "The SAT lower control proves the reduction preserves known "
            "counterexamples; the UNSAT upper control proves it preserves "
            "H1517's exact sufficient projection. The candidate result alone "
            "decides whether g5.P[5] closes the 63-coordinate quotient."
        ),
        "claim_boundary": (
            "This is an exact width-reduction of H1518's abstract-state "
            "query. It does not choose the physical Skylake orientation or "
            "validate a silicon selector. UNKNOWN remains UNKNOWN."
        ),
        "hardware_execution": "none",
        "hardware_labels_opened": "none",
        "capture_manifest": "none",
        "emulator_change": "none",
        "paper_change": "none",
        "sha256": {
            "h1517": sha256(arguments.h1517.read_bytes()),
            "h1518": sha256(arguments.h1518.read_bytes()),
        },
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(text)
    print(json.dumps({
        "output": str(arguments.output),
        "report_sha256": sha256(text.encode()),
        "status": status,
        "candidate_status": results["candidate"]["status"],
        "candidate_solver": results["candidate"]["solver"],
        **({"candidate_counterexample_edge": candidate_edge}
           if candidate_edge is not None else {}),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
