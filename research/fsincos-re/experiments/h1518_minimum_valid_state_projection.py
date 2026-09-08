#!/usr/bin/env python3
"""Solve the minimum valid-state coordinate projection after H1517.

H1517 proves 62 coordinates individually necessary on the valid redundant-pair
image, 21 coordinates absent even from the unconstrained canonical extension,
and a 25-coordinate reachability gap.  This experiment uses exact CEGIS over
those 25 optional coordinates.  Every opposite-defect pair contributes the set
of optional coordinates on which it differs; any exact projection must hit
that set.  A cardinality-minimum hitting set proposes the next projection, and
an exact two-copy QF_BV query either rejects it or proves it sufficient.

When a proposed projection is UNSAT, its cardinality is globally minimum
inside H1516's named coordinate family: the accumulated counterexamples prove
that every smaller set misses at least one required edge.

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
    cvc5_bv_value,
    cvc5_terminal_crosscheck,
    decode_state,
    field_names,
    free_state,
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def coordinate_key(row):
    return row["field"], int(row["bit"])


def render_coordinate(key):
    return {"field": key[0], "bit": key[1]}


def minimum_hitting_set(edges, optional_count: int):
    variables = [z3.Bool(f"hit_{index}") for index in range(optional_count)]
    edge_constraints = [
        z3.Or(*(variables[index] for index in edge))
        for edge in edges
    ]
    for cardinality in range(optional_count + 1):
        solver = z3.Solver()
        solver.add(*edge_constraints)
        solver.add(z3.PbEq(
            [(variable, 1) for variable in variables], cardinality
        ))
        if solver.check() != z3.sat:
            continue

        # Canonicalize the optimum by preferring each lower coordinate when
        # doing so is compatible with an exact-cardinality solution.
        chosen = []
        fixed = []
        for index, variable in enumerate(variables):
            if len(chosen) == cardinality:
                fixed.append(z3.Not(variable))
                continue
            solver.push()
            solver.add(*fixed, variable)
            can_include = solver.check() == z3.sat
            solver.pop()
            if can_include:
                fixed.append(variable)
                chosen.append(index)
            else:
                fixed.append(z3.Not(variable))
        solver.add(*fixed)
        if solver.check() != z3.sat or len(chosen) != cardinality:
            raise RuntimeError("canonical hitting-set solve failed")
        return tuple(chosen)
    raise RuntimeError("no hitting set exists")


def z3_state_values(model, state):
    return {
        name: model.eval(state[name], model_completion=True).as_long()
        for name in field_names()
    }


def cvc5_state_values(declared_model, state):
    return {
        name: cvc5_bv_value(declared_model[str(state[name])])
        for name in field_names()
    }


def verify_projection(pair_a, pair_b, mandatory, retained_optional,
                      optional, timeout_ms: int,
                      crosscheck_timeout_ms: int):
    left = free_state("projection_left")
    right = free_state("projection_right")
    left_pairs = decode_state(left)
    right_pairs = decode_state(right)
    left_defect = defect(left_pairs, pair_a, pair_b)
    right_defect = defect(right_pairs, pair_a, pair_b)
    retained = sorted(set(mandatory) | set(retained_optional))

    solver = z3.SolverFor("QF_BV")
    solver.set(timeout=timeout_ms)
    solver.add(*canonical_validity_constraints(left))
    solver.add(*canonical_validity_constraints(right))
    for field, bit in retained:
        solver.add(
            z3.Extract(bit, bit, left[field])
            == z3.Extract(bit, bit, right[field])
        )
    solver.add(left_defect != right_defect)
    status = solver.check()
    solver_name = f"z3 {z3.get_version_string()}"
    query = solver.to_smt2()
    if status == z3.sat:
        model = solver.model()
        left_values = z3_state_values(model, left)
        right_values = z3_state_values(model, right)
    elif status == z3.unsat:
        return {
            "status": "unsat",
            "solver": solver_name,
            "query": query,
            "query_bytes": len(query.encode()),
            "query_sha256": hashlib.sha256(query.encode()).hexdigest(),
        }
    else:
        crosscheck = cvc5_terminal_crosscheck(
            solver, crosscheck_timeout_ms
        )
        if crosscheck["status"] == "unsat":
            return {
                "status": "unsat",
                "solver": crosscheck["solver"],
                "query": crosscheck["query"],
                "query_bytes": crosscheck["query_bytes"],
                "query_sha256": crosscheck["query_sha256"],
                "z3_status": "unknown",
                "z3_reason_unknown": solver.reason_unknown(),
            }
        if crosscheck["status"] != "sat":
            return {
                "status": "unknown",
                "solver": crosscheck["solver"],
                "reason_unknown": (
                    f"z3={solver.reason_unknown()}; "
                    f"cvc5={crosscheck['reason']}"
                ),
                "query": crosscheck["query"],
                "query_bytes": crosscheck["query_bytes"],
                "query_sha256": crosscheck["query_sha256"],
            }
        solver_name = crosscheck["solver"]
        left_values = cvc5_state_values(crosscheck["declared_model"], left)
        right_values = cvc5_state_values(crosscheck["declared_model"], right)

    differing_optional = [
        key for key in optional
        if ((left_values[key[0]] >> key[1]) & 1)
        != ((right_values[key[0]] >> key[1]) & 1)
    ]
    if not differing_optional:
        raise RuntimeError(
            "opposite-defect witness differs on no optional coordinate"
        )
    return {
        "status": "sat",
        "solver": solver_name,
        "difference_edge": differing_optional,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("h1516", type=Path)
    parser.add_argument("h1517", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout-ms", type=int, default=10_000)
    parser.add_argument("--crosscheck-timeout-ms", type=int, default=60_000)
    parser.add_argument("--max-iterations", type=int, default=256)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit(f"refusing to overwrite {arguments.output}")
    query_path = arguments.output.with_name(
        arguments.output.stem + "_terminal.smt2"
    )
    if query_path.exists():
        raise SystemExit(f"refusing to overwrite {query_path}")
    if z3.get_version_string() != "4.15.3":
        raise RuntimeError(f"unexpected Z3 version {z3.get_version_string()}")
    if cvc5.__version__ != "1.3.1":
        raise RuntimeError(f"unexpected CVC5 version {cvc5.__version__}")

    h1516 = json.loads(arguments.h1516.read_text())
    h1517 = json.loads(arguments.h1517.read_text())
    if h1516["status"] != "EXACT_WORD_MINIMAL_ORDERED_QUARTET_STATE":
        raise RuntimeError("H1516 representation changed")
    if h1517["status"] != "EXACT_EXTENSION_SUPPORT_WITH_REACHABILITY_GAP":
        raise RuntimeError("H1517 support boundary changed")

    all_coordinates = set(coordinates())
    extension = {
        coordinate_key(row) for row in h1517["canonical_extension_support"]
    }
    mandatory = {
        coordinate_key(row) for row in h1517["reachable_state_support"]
    }
    absent = all_coordinates - extension
    optional = tuple(sorted(extension - mandatory))
    if (len(all_coordinates), len(extension), len(mandatory), len(absent),
            len(optional)) != (108, 87, 62, 21, 25):
        raise RuntimeError("H1517 support partition changed")

    layouts = {name: config for name, _, config in tree_variants()}
    pair_a = layouts[EXPECTED_A]
    pair_b = layouts[EXPECTED_B]

    edges = []
    iterations = []
    terminal = None
    retained_optional = ()
    for iteration in range(arguments.max_iterations):
        retained_indices = minimum_hitting_set(edges, len(optional))
        retained_optional = tuple(optional[index] for index in retained_indices)
        result = verify_projection(
            pair_a,
            pair_b,
            mandatory,
            retained_optional,
            optional,
            arguments.timeout_ms,
            arguments.crosscheck_timeout_ms,
        )
        if result["status"] == "unknown":
            iterations.append({
                "iteration": iteration,
                "candidate_optional": [
                    render_coordinate(key) for key in retained_optional
                ],
                "candidate_optional_count": len(retained_optional),
                "status": "unknown",
                "solver": result["solver"],
                "reason_unknown": result["reason_unknown"],
            })
            query_path.write_text(result["query"])
            stopping_report = {
                "experiment": "h1518_minimum_valid_state_projection",
                "status": "STOPPING_UNKNOWN",
                "z3_version": z3.get_version_string(),
                "cvc5_version": cvc5.__version__,
                "timeout_ms_per_z3_check": arguments.timeout_ms,
                "crosscheck_timeout_ms": arguments.crosscheck_timeout_ms,
                "support_partition": {
                    "candidate_coordinates": len(all_coordinates),
                    "mandatory_from_h1517": len(mandatory),
                    "optional_reachability_gap": len(optional),
                    "absent_from_extension": len(absent),
                },
                "cegis_iterations": iterations,
                "counterexample_edge_count": len(edges),
                "current_hitting_set_lower_bound": len(retained_optional),
                "unresolved_candidate_optional": [
                    render_coordinate(key) for key in retained_optional
                ],
                "stopping_query": {
                    "status": "unknown",
                    "reason_unknown": result["reason_unknown"],
                    "artifact": query_path.name,
                    "bytes": result["query_bytes"],
                    "sha256": result["query_sha256"],
                },
                "interpretation": (
                    "The four SAT counterexamples prove that retaining no "
                    "optional coordinate is insufficient and propose a "
                    "one-coordinate hitting set. UNKNOWN does not establish "
                    "that candidate's sufficiency or failure, so no minimum "
                    "projection is claimed."
                ),
                "claim_boundary": (
                    "This is a solver stopping result inside H1516's named "
                    "state encoding. It is not a selector, a closed solution, "
                    "or an impossibility proof."
                ),
                "hardware_execution": "none",
                "hardware_labels_opened": "none",
                "capture_manifest": "none",
                "emulator_change": "none",
                "paper_change": "none",
                "sha256": {
                    "h1516": digest(arguments.h1516),
                    "h1517": digest(arguments.h1517),
                },
            }
            text = json.dumps(
                stopping_report, indent=2, sort_keys=True
            ) + "\n"
            arguments.output.parent.mkdir(parents=True, exist_ok=True)
            arguments.output.write_text(text)
            print(json.dumps({
                "iteration": iteration,
                "retained_optional": len(retained_optional),
                "unresolved_candidate_optional": stopping_report[
                    "unresolved_candidate_optional"
                ],
                "output": str(arguments.output),
                "report_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "query_sha256": result["query_sha256"],
                "status": result["status"],
                "solver": result["solver"],
                "reason_unknown": result["reason_unknown"],
            }, sort_keys=True), flush=True)
            return
        if result["status"] == "unsat":
            terminal = result
            iterations.append({
                "iteration": iteration,
                "candidate_optional": [
                    render_coordinate(key) for key in retained_optional
                ],
                "candidate_optional_count": len(retained_optional),
                "status": "unsat",
                "solver": result["solver"],
            })
            break

        edge = tuple(optional.index(key) for key in result["difference_edge"])
        edge = tuple(sorted(set(edge)))
        if not edge or edge in edges:
            raise RuntimeError("CEGIS produced an empty or duplicate edge")
        edges.append(edge)
        iterations.append({
            "iteration": iteration,
            "candidate_optional": [
                render_coordinate(key) for key in retained_optional
            ],
            "candidate_optional_count": len(retained_optional),
            "status": "sat",
            "solver": result["solver"],
            "counterexample_edge": [
                render_coordinate(optional[index]) for index in edge
            ],
        })
        print(json.dumps({
            "iteration": iteration,
            "candidate_optional_count": len(retained_optional),
            "counterexample_edge_size": len(edge),
            "solver": result["solver"],
        }, sort_keys=True), flush=True)
    if terminal is None:
        raise RuntimeError("CEGIS iteration bound exhausted")

    minimum_size = len(retained_optional)
    lower_bound_check = minimum_hitting_set(edges, len(optional))
    if tuple(optional[index] for index in lower_bound_check) != retained_optional:
        raise RuntimeError("terminal candidate stopped being canonical-minimum")
    if minimum_size:
        smaller = z3.Solver()
        choices = [z3.Bool(f"lower_{index}") for index in range(len(optional))]
        for edge in edges:
            smaller.add(z3.Or(*(choices[index] for index in edge)))
        smaller.add(z3.PbLe(
            [(choice, 1) for choice in choices], minimum_size - 1
        ))
        if smaller.check() != z3.unsat:
            raise RuntimeError("counterexample edges do not prove minimum size")

    query_path.write_text(terminal["query"])
    report = {
        "experiment": "h1518_minimum_valid_state_projection",
        "status": "EXACT_MINIMUM_COORDINATE_PROJECTION",
        "z3_version": z3.get_version_string(),
        "cvc5_version": cvc5.__version__,
        "support_partition": {
            "candidate_coordinates": len(all_coordinates),
            "mandatory_from_h1517": len(mandatory),
            "optional_reachability_gap": len(optional),
            "absent_from_extension": len(absent),
        },
        "cegis_iterations": iterations,
        "counterexample_edge_count": len(edges),
        "minimum_optional_count": minimum_size,
        "minimum_total_coordinate_count": len(mandatory) + minimum_size,
        "retained_mandatory": [
            render_coordinate(key) for key in sorted(mandatory)
        ],
        "retained_optional": [
            render_coordinate(key) for key in retained_optional
        ],
        "omitted_absent": [
            render_coordinate(key) for key in sorted(absent)
        ],
        "omitted_optional": [
            render_coordinate(key) for key in optional
            if key not in set(retained_optional)
        ],
        "minimum_certificate": {
            "method": (
                "each stored opposite-defect edge must intersect every exact "
                "projection; no hitting set of smaller cardinality exists"
            ),
            "smaller_hitting_set_status": "unsat",
            "terminal_projection_status": "unsat",
            "terminal_solver": terminal["solver"],
            **({
                "z3_status": terminal["z3_status"],
                "z3_reason_unknown": terminal["z3_reason_unknown"],
            } if "z3_status" in terminal else {}),
            "terminal_query_artifact": query_path.name,
            "terminal_query_bytes": terminal["query_bytes"],
            "terminal_query_sha256": terminal["query_sha256"],
        },
        "claim_boundary": (
            "This is cardinality-minimum among projections that retain raw "
            "coordinates of H1516's named state. It does not prove a global "
            "minimum over arbitrary derived Boolean encodings, choose the "
            "physical Skylake orientation, or validate a selector."
        ),
        "hardware_execution": "none",
        "hardware_labels_opened": "none",
        "capture_manifest": "none",
        "emulator_change": "none",
        "paper_change": "none",
        "sha256": {
            "h1516": digest(arguments.h1516),
            "h1517": digest(arguments.h1517),
        },
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(text)
    print(json.dumps({
        "output": str(arguments.output),
        "report_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "status": report["status"],
        "cegis_iterations": len(iterations),
        "counterexample_edges": len(edges),
        "minimum_optional_count": minimum_size,
        "minimum_total_coordinate_count": report[
            "minimum_total_coordinate_count"
        ],
        "retained_optional": report["retained_optional"],
        "terminal_solver": terminal["solver"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
